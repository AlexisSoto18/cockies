"""
Monitor de historial de navegación.

Lee el historial de los navegadores instalados (Firefox, Chrome, Brave, Chromium, Edge)
para detectar qué sitios se visitaron. Los archivos de historial son bases de datos
SQLite que se pueden leer sin modificar.

Soporta Linux, Windows y WSL.
"""
import os
import sys
import subprocess
import sqlite3
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

IS_WINDOWS = sys.platform == "win32"
IS_WSL = False
if not IS_WINDOWS:
    try:
        with open("/proc/version", "r") as f:
            IS_WSL = "microsoft" in f.read().lower()
    except (FileNotFoundError, PermissionError):
        pass


def _detect_win_user_from_wsl() -> str:
    """Detecta el usuario de Windows desde WSL."""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", "echo $env:USERNAME"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    # Fallback: buscar en /mnt/c/Users
    try:
        for entry in Path("/mnt/c/Users").iterdir():
            if entry.is_dir() and entry.name not in ("Public", "Default", "Default User", "All Users"):
                return entry.name
    except Exception:
        pass
    return ""


def _build_browser_paths() -> dict:
    """Construye rutas de historial según la plataforma."""
    if IS_WINDOWS:
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        roaming = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return {
            "firefox": roaming / "Mozilla" / "Firefox" / "Profiles",
            "chrome": local / "Google" / "Chrome" / "User Data" / "Default" / "History",
            "chromium": local / "Chromium" / "User Data" / "Default" / "History",
            "brave": local / "BraveSoftware" / "Brave-Browser" / "User Data" / "Default" / "History",
            "edge": local / "Microsoft" / "Edge" / "User Data" / "Default" / "History",
        }
    elif IS_WSL:
        win_user = _detect_win_user_from_wsl()
        if not win_user:
            return {}
        base = Path(f"/mnt/c/Users/{win_user}")
        local = base / "AppData" / "Local"
        roaming = base / "AppData" / "Roaming"
        return {
            "firefox": roaming / "Mozilla" / "Firefox" / "Profiles",
            "chrome": local / "Google" / "Chrome" / "User Data" / "Default" / "History",
            "chromium": local / "Chromium" / "User Data" / "Default" / "History",
            "brave": local / "BraveSoftware" / "Brave-Browser" / "User Data" / "Default" / "History",
            "edge": local / "Microsoft" / "Edge" / "User Data" / "Default" / "History",
        }
    else:
        return {
            "firefox": Path.home() / ".mozilla" / "firefox",
            "chrome": Path.home() / ".config" / "google-chrome" / "Default" / "History",
            "chromium": Path.home() / ".config" / "chromium" / "Default" / "History",
            "brave": Path.home() / ".config" / "BraveSoftware" / "Brave-Browser" / "Default" / "History",
        }


BROWSER_HISTORY_PATHS = _build_browser_paths()


class BrowserTracker:
    """Rastrea historial de navegación de múltiples navegadores."""

    def __init__(self):
        self._last_check = datetime.now()
        self._history_cache = set()  # URLs ya reportadas

    def _find_firefox_history(self) -> Path | None:
        """Busca el archivo de historial de Firefox (places.sqlite)."""
        firefox_dir = BROWSER_HISTORY_PATHS["firefox"]
        if not firefox_dir.exists():
            return None
        # En Windows el path apunta a Profiles/, en Linux a .mozilla/firefox/
        # Ambos contienen subdirectorios con los perfiles
        search_dir = firefox_dir
        for profile_dir in search_dir.iterdir():
            if profile_dir.is_dir():
                history_file = profile_dir / "places.sqlite"
                if history_file.exists():
                    return history_file
        return None

    def _copy_db_safely(self, db_path: Path) -> Path | None:
        """
        Copia la base de datos a un archivo temporal para evitar
        problemas de bloqueo con el navegador abierto.
        """
        if not db_path.exists():
            return None
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
            tmp.close()
            shutil.copy2(db_path, tmp.name)
            return Path(tmp.name)
        except (PermissionError, OSError):
            return None

    def _get_firefox_history(self, since: datetime) -> list[dict]:
        """Lee historial de Firefox desde una fecha."""
        history_path = self._find_firefox_history()
        if not history_path:
            return []

        tmp_db = self._copy_db_safely(history_path)
        if not tmp_db:
            return []

        entries = []
        try:
            # Firefox usa microsegundos desde epoch
            since_ts = int(since.timestamp() * 1_000_000)
            conn = sqlite3.connect(f"file:{tmp_db}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT url, title, last_visit_date, visit_count
                FROM moz_places
                WHERE last_visit_date > ?
                ORDER BY last_visit_date DESC
                LIMIT 200
            """, (since_ts,))

            for row in cursor.fetchall():
                url, title, visit_date, visit_count = row
                visit_dt = datetime.fromtimestamp(visit_date / 1_000_000) if visit_date else None
                entries.append({
                    "browser": "Firefox",
                    "url": url,
                    "title": title or "",
                    "visited_at": visit_dt.isoformat() if visit_dt else "",
                    "visit_count": visit_count,
                })
            conn.close()
        except Exception:
            pass
        finally:
            try:
                os.unlink(tmp_db)
            except OSError:
                pass
        return entries

    def _get_chromium_history(self, browser_name: str, db_path: Path, since: datetime) -> list[dict]:
        """Lee historial de navegadores basados en Chromium."""
        if not db_path.exists():
            return []

        tmp_db = self._copy_db_safely(db_path)
        if not tmp_db:
            return []

        entries = []
        try:
            # Chrome usa microsegundos desde 1601-01-01
            chrome_epoch = datetime(1601, 1, 1)
            since_chrome = int((since - chrome_epoch).total_seconds() * 1_000_000)

            conn = sqlite3.connect(f"file:{tmp_db}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.url, u.title, v.visit_time
                FROM urls u
                JOIN visits v ON u.id = v.url
                WHERE v.visit_time > ?
                ORDER BY v.visit_time DESC
                LIMIT 200
            """, (since_chrome,))

            for row in cursor.fetchall():
                url, title, visit_time = row
                visit_dt = chrome_epoch + timedelta(microseconds=visit_time) if visit_time else None
                entries.append({
                    "browser": browser_name,
                    "url": url,
                    "title": title or "",
                    "visited_at": visit_dt.isoformat() if visit_dt else "",
                })
            conn.close()
        except Exception:
            pass
        finally:
            try:
                os.unlink(tmp_db)
            except OSError:
                pass
        return entries

    def get_recent_history(self, minutes: int = 30) -> list[dict]:
        """Obtiene el historial de todos los navegadores en los últimos N minutos."""
        since = datetime.now() - timedelta(minutes=minutes)
        all_entries = []

        # Firefox
        all_entries.extend(self._get_firefox_history(since))

        # Chromium-based browsers
        chromium_browsers = ["chrome", "chromium", "brave"]
        if IS_WINDOWS or IS_WSL:
            chromium_browsers.append("edge")
        for name in chromium_browsers:
            path = BROWSER_HISTORY_PATHS.get(name)
            if path:
                all_entries.extend(self._get_chromium_history(name.capitalize(), path, since))

        # Filtrar duplicados ya reportados
        new_entries = []
        for entry in all_entries:
            key = f"{entry['url']}_{entry['visited_at']}"
            if key not in self._history_cache:
                self._history_cache.add(key)
                new_entries.append(entry)

        # Limpiar cache viejo (mantener solo últimas 1000 entradas)
        if len(self._history_cache) > 1000:
            self._history_cache = set(list(self._history_cache)[-500:])

        return new_entries

    def get_domain_summary(self, minutes: int = 30) -> dict:
        """Resumen de dominios visitados con conteo."""
        from urllib.parse import urlparse
        history = self.get_recent_history(minutes)
        domains = defaultdict(int)
        for entry in history:
            try:
                domain = urlparse(entry["url"]).netloc
                if domain:
                    domains[domain] += 1
            except Exception:
                pass
        return {
            "total_visits": len(history),
            "domains": dict(sorted(domains.items(), key=lambda x: -x[1])),
            "period_minutes": minutes,
            "timestamp": datetime.now().isoformat(),
        }

    def classify_urls(self, history: list[dict], productive_urls: list[str],
                      unproductive_urls: list[str]) -> dict:
        """Clasifica URLs visitadas como productivas o improductivas."""
        from urllib.parse import urlparse
        productive = []
        unproductive = []
        neutral = []

        for entry in history:
            try:
                domain = urlparse(entry["url"]).netloc.lower()
                if any(p in domain for p in productive_urls):
                    productive.append(entry)
                elif any(u in domain for u in unproductive_urls):
                    unproductive.append(entry)
                else:
                    neutral.append(entry)
            except Exception:
                neutral.append(entry)

        return {
            "productive": productive,
            "unproductive": unproductive,
            "neutral": neutral,
            "productive_count": len(productive),
            "unproductive_count": len(unproductive),
            "neutral_count": len(neutral),
        }
