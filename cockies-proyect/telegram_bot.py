"""
Integración con Telegram Bot API.

Envía notificaciones y reportes al usuario vía Telegram.
Los mensajes con datos sensibles se pueden enviar encriptados.
"""
import requests
import time
import threading
from datetime import datetime


class TelegramBot:
    """Cliente para enviar mensajes vía Telegram Bot API."""

    BASE_URL = "https://api.telegram.org/bot{token}"

    def __init__(self, token: str, chat_id: str):
        self._token = token
        self._chat_id = chat_id
        self._base_url = self.BASE_URL.format(token=token)
        self._message_queue = []
        self._lock = threading.Lock()

    def _make_request(self, method: str, data: dict, retries: int = 3) -> dict | None:
        """Hace una petición a la API de Telegram con reintentos."""
        url = f"{self._base_url}/{method}"
        for attempt in range(retries):
            try:
                response = requests.post(url, json=data, timeout=30)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    # Rate limited, esperar
                    retry_after = response.json().get("parameters", {}).get("retry_after", 5)
                    time.sleep(retry_after)
                else:
                    print(f"⚠️  Telegram API error {response.status_code}: {response.text[:200]}")
                    return None
            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    print(f"⚠️  Error de conexión con Telegram: {e}")
                    return None
        return None

    def send_message(self, text: str, parse_mode: str = "HTML",
                     disable_notification: bool = False) -> bool:
        """Envía un mensaje de texto."""
        # Telegram tiene límite de 4096 caracteres
        if len(text) > 4096:
            # Dividir en múltiples mensajes
            chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
            success = True
            for chunk in chunks:
                result = self._make_request("sendMessage", {
                    "chat_id": self._chat_id,
                    "text": chunk,
                    "parse_mode": parse_mode,
                    "disable_notification": disable_notification,
                })
                if not result:
                    success = False
                time.sleep(0.5)  # Respetar rate limits
            return success

        result = self._make_request("sendMessage", {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification,
        })
        return result is not None

    def send_document(self, file_path: str, caption: str = "") -> bool:
        """Envía un archivo como documento."""
        url = f"{self._base_url}/sendDocument"
        try:
            with open(file_path, "rb") as f:
                response = requests.post(
                    url,
                    data={"chat_id": self._chat_id, "caption": caption[:1024]},
                    files={"document": f},
                    timeout=60,
                )
            return response.status_code == 200
        except Exception as e:
            print(f"⚠️  Error enviando documento: {e}")
            return False

    def send_notification(self, title: str, message: str):
        """Envía una notificación formateada."""
        text = f"🔔 <b>{title}</b>\n\n{message}"
        self.send_message(text)

    def send_alert(self, message: str):
        """Envía una alerta importante (con notificación sonora)."""
        text = f"⚠️ <b>ALERTA</b>\n\n{message}"
        self.send_message(text, disable_notification=False)

    def send_report(self, report_text: str):
        """Envía un reporte de productividad."""
        self.send_message(report_text, disable_notification=True)

    def test_connection(self) -> bool:
        """Verifica que el bot puede enviar mensajes."""
        result = self._make_request("getMe", {})
        if not result or not result.get("ok"):
            return False
        bot_name = result["result"].get("username", "desconocido")
        sent = self.send_message(
            f"✅ <b>Cockies Monitor Activo</b>\n\n"
            f"Bot: @{bot_name}\n"
            f"Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"El monitor de productividad está funcionando."
        )
        if not sent:
            print(f"  ℹ️  Bot válido (@{bot_name}) pero no se pudo enviar mensaje al chat.")
            print(f"  ℹ️  Asegúrate de enviar /start al bot en Telegram primero.")
        return sent

    def get_updates(self, offset: int = 0) -> list[dict]:
        """Obtiene mensajes nuevos (para comandos del usuario)."""
        result = self._make_request("getUpdates", {
            "offset": offset,
            "timeout": 5,
        })
        if result and result.get("ok"):
            return result.get("result", [])
        return []
