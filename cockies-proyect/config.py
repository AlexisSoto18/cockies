"""
Configuración central del monitor de productividad.
Crea un archivo .env en la raíz del proyecto con tus credenciales.
"""
import os
import json
from pathlib import Path

# Rutas del proyecto
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
ENCRYPTED_DIR = DATA_DIR / "encrypted"
ENCRYPTED_DIR.mkdir(exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"

# Valores por defecto
DEFAULTS = {
    "telegram_token": "",
    "telegram_chat_id": "",
    "encryption_key": "",
    # Intervalos en segundos
    "report_interval": 1800,        # Reporte cada 30 min
    "activity_check_interval": 5,   # Chequeo de ventana activa cada 5s
    "browser_check_interval": 300,  # Chequeo de historial cada 5 min
    "daily_report_hour": 22,        # Hora del reporte diario (10 PM)
    # Umbrales de notificación
    "idle_threshold": 600,          # 10 min sin actividad = notificación
    "long_session_threshold": 5400, # 90 min continuo = notificación de descanso
    # Categorías de apps (para clasificar productividad)
    "productive_apps": [
        "code", "terminal", "vim", "nvim", "emacs",
        "libreoffice", "gimp", "blender", "kdenlive"
    ],
    "unproductive_apps": [
        "firefox", "chromium", "chrome", "brave",
        "discord", "telegram", "slack"
    ],
    "productive_urls": [
        "github.com", "stackoverflow.com", "docs.python.org",
        "developer.mozilla.org", "learn.microsoft.com"
    ],
    "unproductive_urls": [
        "youtube.com", "reddit.com", "twitter.com", "x.com",
        "facebook.com", "instagram.com", "tiktok.com"
    ],
}


def load_config() -> dict:
    """Carga configuración desde config.json, creando valores por defecto si no existe."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            saved = json.load(f)
        # Merge con defaults para nuevas keys
        merged = {**DEFAULTS, **saved}
        return merged
    return DEFAULTS.copy()


def save_config(config: dict):
    """Guarda configuración en config.json."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_config() -> dict:
    """Obtiene la configuración actual."""
    return load_config()
