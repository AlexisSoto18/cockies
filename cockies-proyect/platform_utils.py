"""
Utilidades multiplataforma para detección de ventana activa.
Soporta Linux (X11 con xdotool), WSL (PowerShell) y Windows nativo (ctypes).
"""
import sys
import subprocess
import os

IS_WINDOWS = sys.platform == "win32"
IS_WSL = False
if not IS_WINDOWS:
    try:
        with open("/proc/version", "r") as f:
            IS_WSL = "microsoft" in f.read().lower()
    except (FileNotFoundError, PermissionError):
        pass


def get_active_window_title() -> str:
    """Obtiene el título de la ventana activa."""
    if IS_WINDOWS:
        return _win_get_title()
    if IS_WSL:
        _, title = _wsl_get_info()
        return title
    return _linux_get_title()


def get_active_window_app() -> str:
    """Obtiene el nombre del proceso de la ventana activa."""
    if IS_WINDOWS:
        return _win_get_app()
    if IS_WSL:
        app, _ = _wsl_get_info()
        return app
    return _linux_get_app()


def get_active_window_info() -> tuple[str, str]:
    """Retorna (app_name, window_title) de la ventana activa."""
    if IS_WINDOWS:
        return _win_get_app(), _win_get_title()
    if IS_WSL:
        return _wsl_get_info()
    return _linux_get_info()


# ── WSL (PowerShell → Windows API) ─────────────────────────

_WSL_PS_SCRIPT = r"""
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public class WinAPI {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
'@
$hwnd = [WinAPI]::GetForegroundWindow()
$sb = New-Object System.Text.StringBuilder 256
[WinAPI]::GetWindowText($hwnd, $sb, 256) | Out-Null
$procId = [uint32]0
[WinAPI]::GetWindowThreadProcessId($hwnd, [ref]$procId) | Out-Null
$proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
Write-Output "$($proc.ProcessName)|$($sb.ToString())"
"""

# Cache para no llamar a PowerShell en cada tecla
_wsl_cache = {"result": ("desconocido", "desconocido"), "time": 0}
_WSL_CACHE_TTL = 2  # segundos


def _wsl_get_info() -> tuple[str, str]:
    """Obtiene (app, titulo) de la ventana activa en Windows desde WSL."""
    import time
    now = time.time()
    if now - _wsl_cache["time"] < _WSL_CACHE_TTL:
        return _wsl_cache["result"]

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", _WSL_PS_SCRIPT],
            capture_output=True, text=True, timeout=5,
            env={**os.environ, "WSLENV": ""},
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            # Puede tener múltiples líneas, nos interesa la última
            last_line = output.split("\n")[-1].strip()
            if "|" in last_line:
                app_name, window_title = last_line.split("|", 1)
                app_name = app_name.strip() or "desconocido"
                window_title = window_title.strip() or "desconocido"
                _wsl_cache["result"] = (app_name, window_title)
                _wsl_cache["time"] = now
                return app_name, window_title
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    _wsl_cache["time"] = now
    return "desconocido", "desconocido"


# ── Linux (X11 / xdotool) ──────────────────────────────────

def _linux_get_title() -> str:
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, Exception):
        pass
    return "desconocido"


def _linux_get_app() -> str:
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode != 0:
            return "desconocido"
        window_id = result.stdout.strip()

        result = subprocess.run(
            ["xdotool", "getwindowpid", window_id],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode != 0:
            return "desconocido"
        pid = result.stdout.strip()

        result = subprocess.run(
            ["ps", "-p", pid, "-o", "comm="],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, Exception):
        pass
    return "desconocido"


def _linux_get_info() -> tuple[str, str]:
    app_name = "desconocido"
    window_title = "desconocido"
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode != 0:
            return app_name, window_title
        window_id = result.stdout.strip()

        result = subprocess.run(
            ["xdotool", "getwindowname", window_id],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            window_title = result.stdout.strip()

        result = subprocess.run(
            ["xdotool", "getwindowpid", window_id],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            pid = result.stdout.strip()
            result = subprocess.run(
                ["ps", "-p", pid, "-o", "comm="],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                app_name = result.stdout.strip()
    except (FileNotFoundError, Exception):
        pass
    return app_name, window_title


# ── Windows nativo (ctypes / win32) ────────────────────────

def _win_get_title() -> str:
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value if buf.value else "desconocido"
    except Exception:
        return "desconocido"


def _win_get_app() -> str:
    try:
        import ctypes
        from ctypes import wintypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()

        # Obtener PID de la ventana
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        # Obtener nombre del proceso
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
        )
        if handle:
            buf = ctypes.create_unicode_buffer(512)
            size = wintypes.DWORD(512)
            ctypes.windll.kernel32.QueryFullProcessImageNameW(
                handle, 0, buf, ctypes.byref(size)
            )
            ctypes.windll.kernel32.CloseHandle(handle)
            if buf.value:
                import os
                return os.path.basename(buf.value).replace(".exe", "")
    except Exception:
        pass
    return "desconocido"
