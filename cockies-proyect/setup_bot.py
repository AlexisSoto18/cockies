"""
Asistente de configuración interactivo.

Guía al usuario para:
1. Crear un bot de Telegram
2. Obtener el chat_id
3. Generar la clave de encriptación
4. Guardar todo en config.json
"""
import sys
import os

from config import load_config, save_config
from encryption import generate_key
from telegram_bot import TelegramBot


def setup():
    print("=" * 50)
    print("🍪 COCKIES — Configuración del Monitor")
    print("=" * 50)
    print()

    config = load_config()

    # Paso 1: Token del bot
    print("📱 PASO 1: Bot de Telegram")
    print("-" * 30)
    print("Para crear un bot de Telegram:")
    print("  1. Abre Telegram y busca @BotFather")
    print("  2. Envía /newbot")
    print("  3. Dale un nombre (ej: 'Mi Monitor Personal')")
    print("  4. Dale un username (ej: 'mi_monitor_bot')")
    print("  5. BotFather te dará un TOKEN")
    print()

    current_token = config.get("telegram_token", "")
    if current_token:
        print(f"  Token actual: {current_token[:10]}...{current_token[-5:]}")
        change = input("  ¿Cambiar token? (s/N): ").strip().lower()
        if change == "s":
            config["telegram_token"] = input("  Nuevo token: ").strip()
    else:
        config["telegram_token"] = input("  Pega tu token aquí: ").strip()

    if not config["telegram_token"]:
        print("❌ Token requerido. Ejecuta setup de nuevo cuando lo tengas.")
        return

    # Paso 2: Chat ID
    print()
    print("💬 PASO 2: Chat ID")
    print("-" * 30)
    print("Para obtener tu Chat ID:")
    print("  1. Abre Telegram y busca tu bot por su username")
    print("  2. Envíale cualquier mensaje (ej: 'hola')")
    print("  3. Presiona ENTER aquí y lo detectaré automáticamente")
    print()

    current_chat_id = config.get("telegram_chat_id", "")
    if current_chat_id:
        print(f"  Chat ID actual: {current_chat_id}")
        change = input("  ¿Cambiar? (s/N): ").strip().lower()
        if change != "s":
            pass
        else:
            _detect_chat_id(config)
    else:
        _detect_chat_id(config)

    if not config.get("telegram_chat_id"):
        print("❌ Chat ID requerido.")
        return

    # Paso 3: Encriptación
    print()
    print("🔐 PASO 3: Clave de Encriptación")
    print("-" * 30)

    current_key = config.get("encryption_key", "")
    if current_key:
        print("  Ya tienes una clave de encriptación configurada.")
        change = input("  ¿Generar nueva clave? (s/N): ").strip().lower()
        if change == "s":
            config["encryption_key"] = generate_key()
            print(f"  ✅ Nueva clave generada")
    else:
        config["encryption_key"] = generate_key()
        print(f"  ✅ Clave de encriptación generada automáticamente")

    # Paso 4: Configuración adicional
    print()
    print("⚙️  PASO 4: Preferencias (ENTER para usar valores por defecto)")
    print("-" * 30)

    interval = input(f"  Intervalo de reportes en minutos [{config.get('report_interval', 1800)//60}]: ").strip()
    if interval.isdigit():
        config["report_interval"] = int(interval) * 60

    hour = input(f"  Hora del reporte diario (0-23) [{config.get('daily_report_hour', 22)}]: ").strip()
    if hour.isdigit() and 0 <= int(hour) <= 23:
        config["daily_report_hour"] = int(hour)

    # Guardar
    save_config(config)
    print()
    print("✅ Configuración guardada en data/config.json")

    # Probar conexión
    print()
    print("🔌 Probando conexión con Telegram...")
    bot = TelegramBot(config["telegram_token"], config["telegram_chat_id"])
    if bot.test_connection():
        print("✅ ¡Conexión exitosa! Revisa tu Telegram.")
    else:
        print("❌ No se pudo conectar. Verifica token y chat_id.")

    print()
    print("=" * 50)
    print("🚀 Para iniciar el monitor ejecuta:")
    print(f"   python {os.path.dirname(os.path.abspath(__file__))}/main.py")
    print("=" * 50)


def _detect_chat_id(config: dict):
    """Detecta el chat_id automáticamente desde los mensajes recibidos."""
    print("  ⚠️  IMPORTANTE: Abre Telegram, busca tu bot y envíale /start")
    input("  Cuando lo hayas hecho, presiona ENTER aquí...")

    try:
        import requests
        url = f"https://api.telegram.org/bot{config['telegram_token']}/getUpdates"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get("ok") and data.get("result"):
            # Tomar el último mensaje
            last_update = data["result"][-1]
            message = last_update.get("message", last_update.get("my_chat_member", {}))
            chat_id = str(message.get("chat", {}).get("id", ""))
            username = message.get("chat", {}).get("username", "")
            first_name = message.get("chat", {}).get("first_name", "")

            if chat_id:
                print(f"  ✅ Detectado: {first_name} (@{username}) — Chat ID: {chat_id}")
                config["telegram_chat_id"] = chat_id
            else:
                print("  ❌ No se encontró chat_id. Introdúcelo manualmente:")
                config["telegram_chat_id"] = input("  Chat ID: ").strip()
        else:
            print("  ❌ No hay mensajes. Envía un mensaje al bot primero.")
            config["telegram_chat_id"] = input("  Chat ID manual: ").strip()

    except Exception as e:
        print(f"  ❌ Error: {e}")
        config["telegram_chat_id"] = input("  Chat ID manual: ").strip()


if __name__ == "__main__":
    setup()
