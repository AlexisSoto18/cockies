"""
Monitor de uso de aplicaciones.

Rastrea qué aplicación/ventana está activa y cuánto tiempo se pasa en cada una.
Soporta Linux (xdotool) y Windows (ctypes/win32).
"""
import time
import threading
from collections import defaultdict
from datetime import datetime
from platform_utils import get_active_window_info


class AppTracker:
    """Rastrea el uso de aplicaciones midiendo tiempo en cada ventana."""

    def __init__(self, check_interval: int = 5):
        self._check_interval = check_interval
        self._is_running = False
        self._thread = None
        self._lock = threading.Lock()

        # Acumuladores
        self._app_time = defaultdict(float)      # {app_name: seconds}
        self._window_time = defaultdict(float)    # {window_title: seconds}
        self._app_switches = 0                    # Número de cambios de ventana
        self._current_app = ""
        self._current_window = ""
        self._last_check_time = None
        self._session_start = None
        self._timeline = []  # Lista de (timestamp, app, window, duration)

    def start(self):
        """Inicia el monitoreo de aplicaciones en un hilo."""
        if self._is_running:
            return
        self._is_running = True
        self._session_start = datetime.now()
        self._last_check_time = time.time()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Detiene el monitoreo."""
        self._is_running = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None

    def _get_active_window_info(self) -> tuple[str, str]:
        """Obtiene el nombre de la app y título de la ventana activa."""
        try:
            return get_active_window_info()
        except Exception:
            return "desconocido", "desconocido"

    def _monitor_loop(self):
        """Loop principal de monitoreo."""
        while self._is_running:
            try:
                now = time.time()
                elapsed = now - self._last_check_time
                self._last_check_time = now

                app_name, window_title = self._get_active_window_info()

                with self._lock:
                    # Registrar tiempo en la app/ventana anterior
                    if self._current_app:
                        self._app_time[self._current_app] += elapsed
                        self._window_time[self._current_window] += elapsed

                    # Detectar cambio de ventana
                    if app_name != self._current_app or window_title != self._current_window:
                        if self._current_app:
                            self._app_switches += 1
                            # Agregar a timeline
                            self._timeline.append({
                                "time": datetime.now().isoformat(),
                                "app": app_name,
                                "window": window_title[:100],
                            })
                            # Mantener timeline manejable
                            if len(self._timeline) > 500:
                                self._timeline = self._timeline[-250:]

                        self._current_app = app_name
                        self._current_window = window_title

            except Exception:
                pass

            time.sleep(self._check_interval)

    def get_stats(self) -> dict:
        """Obtiene estadísticas de uso de apps."""
        with self._lock:
            # Top apps por tiempo
            sorted_apps = sorted(
                self._app_time.items(), key=lambda x: -x[1]
            )
            top_apps = [
                {"app": app, "minutes": round(secs / 60, 1)}
                for app, secs in sorted_apps[:15]
            ]

            # Top ventanas por tiempo
            sorted_windows = sorted(
                self._window_time.items(), key=lambda x: -x[1]
            )
            top_windows = [
                {"window": win[:80], "minutes": round(secs / 60, 1)}
                for win, secs in sorted_windows[:10]
            ]

            total_time = sum(self._app_time.values())

            return {
                "total_tracked_minutes": round(total_time / 60, 1),
                "top_apps": top_apps,
                "top_windows": top_windows,
                "app_switches": self._app_switches,
                "current_app": self._current_app,
                "current_window": self._current_window[:80],
                "session_start": self._session_start.isoformat() if self._session_start else None,
                "timestamp": datetime.now().isoformat(),
            }

    def classify_apps(self, productive_apps: list[str], unproductive_apps: list[str]) -> dict:
        """Clasifica el tiempo como productivo/improductivo."""
        with self._lock:
            productive_time = 0
            unproductive_time = 0
            neutral_time = 0

            for app, secs in self._app_time.items():
                app_lower = app.lower()
                if any(p in app_lower for p in productive_apps):
                    productive_time += secs
                elif any(u in app_lower for u in unproductive_apps):
                    unproductive_time += secs
                else:
                    neutral_time += secs

            total = productive_time + unproductive_time + neutral_time
            return {
                "productive_minutes": round(productive_time / 60, 1),
                "unproductive_minutes": round(unproductive_time / 60, 1),
                "neutral_minutes": round(neutral_time / 60, 1),
                "productivity_score": round(
                    (productive_time / total * 100) if total > 0 else 0, 1
                ),
            }

    def reset_stats(self):
        """Resetea estadísticas para un nuevo período."""
        with self._lock:
            self._app_time.clear()
            self._window_time.clear()
            self._app_switches = 0
            self._timeline.clear()
            self._session_start = datetime.now()

    def get_recent_timeline(self, n: int = 20) -> list[dict]:
        """Obtiene los últimos N cambios de ventana."""
        with self._lock:
            return list(self._timeline[-n:])
