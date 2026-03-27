# 🍪 Cockies — Monitor Personal de Productividad

Monitor de actividad para laptop que rastrea uso de aplicaciones, navegación web y actividad de teclado (solo estadísticas, no keylogger). Envía reportes y notificaciones a tu celular vía **Telegram**.

## Características

- 💻 **Monitor de aplicaciones** — Rastrea tiempo en cada app/ventana
- 🌐 **Historial de navegación** — Lee historial de Firefox, Chrome, Brave, Chromium
- ⌨️ **Actividad de teclado** — Cuenta pulsaciones por app (NO registra teclas individuales)
- 📱 **Notificaciones Telegram** — Reportes periódicos y alertas en tu celular
- 🔐 **Encriptación** — Datos locales protegidos con AES (Fernet/cryptography)
- 📊 **Clasificación** — Identifica tiempo productivo vs improductivo
- 💡 **Recomendaciones** — Sugerencias automáticas de productividad
- 🛡️ **Seguro para antivirus** — No usa técnicas de keylogger, solo estadísticas

## Requisitos

- Python 3.10+
- Linux con X11 (para detección de ventana activa)
- `xdotool` instalado: `sudo apt install xdotool`

## Instalación

```bash
# 1. Instalar xdotool (requerido para detectar ventana activa)
sudo apt install xdotool

# 2. Instalar dependencias Python
pip install -r requirements.txt

# 3. Configurar bot de Telegram
python setup_bot.py
```

## Configurar Telegram

1. Abre Telegram y busca **@BotFather**
2. Envía `/newbot` y sigue las instrucciones
3. Guarda el **TOKEN** que te da
4. Ejecuta `python setup_bot.py` y sigue el asistente

## Uso

```bash
# Iniciar monitor
python main.py

# Configurar
python main.py --setup

# Enviar mensaje de prueba
python main.py --test
```

## Comandos de Telegram

Una vez activo, envía estos comandos a tu bot:

| Comando    | Descripción              |
|------------|--------------------------|
| `/status`  | Estado actual            |
| `/report`  | Reporte inmediato        |
| `/apps`    | Top aplicaciones         |
| `/sites`   | Sitios visitados         |
| `/pause`   | Pausar monitor           |
| `/resume`  | Reanudar monitor         |
| `/stop`    | Detener monitor          |
| `/help`    | Lista de comandos        |

## Estructura

```
cockies/
├── main.py              # Orquestador principal
├── setup_bot.py         # Asistente de configuración
├── config.py            # Configuración central
├── encryption.py        # Encriptación AES de datos
├── telegram_bot.py      # Cliente de Telegram Bot API
├── keyboard_tracker.py  # Estadísticas de teclado
├── browser_tracker.py   # Historial de navegación
├── app_tracker.py       # Uso de aplicaciones
├── reports.py           # Generación de reportes
├── requirements.txt     # Dependencias Python
└── data/                # Datos (auto-generado)
    ├── config.json      # Tu configuración
    └── encrypted/       # Datos encriptados
```

## Seguridad y Privacidad

- **NO es un keylogger**: Solo cuenta pulsaciones, nunca registra qué teclas presionas
- **Encriptación**: Todos los datos guardados localmente están cifrados con AES (Fernet)
- **Solo tú**: Los reportes solo se envían a tu chat de Telegram
- **Sin red externa**: Solo se comunica con la API de Telegram, nada más
- **Antivirus safe**: No usa hooks de bajo nivel ni técnicas que activen alertas
