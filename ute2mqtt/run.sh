#!/bin/sh
# ==============================================================================
# Ute2MQTT Home Assistant Add-on
# ==============================================================================

set -e

# --- Leer configuración desde options.json de HA ---
OPTIONS_FILE="/data/options.json"

if [ -f "$OPTIONS_FILE" ]; then
    echo "Leyendo configuración desde $OPTIONS_FILE"

    # Usar python para parsear JSON (disponible en la imagen base)
    TOPIC_PREFIX=$(python3 -c "import json; f=open('$OPTIONS_FILE'); d=json.load(f); print(d.get('mqtt_topic_prefix', 'UTE'))")
    DISCOVERY_PREFIX=$(python3 -c "import json; f=open('$OPTIONS_FILE'); d=json.load(f); print(d.get('mqtt_discovery_prefix', 'homeassistant'))")
    CRON_SCHEDULE=$(python3 -c "import json; f=open('$OPTIONS_FILE'); d=json.load(f); print(d.get('cron_schedule', '0 8 * * *'))")
    LOG_LEVEL=$(python3 -c "import json; f=open('$OPTIONS_FILE'); d=json.load(f); print(d.get('log_level', 'info'))")
else
    echo "Archivo de configuración no encontrado, usando defaults"
    TOPIC_PREFIX="UTE"
    DISCOVERY_PREFIX="homeassistant"
    CRON_SCHEDULE="0 8 * * *"
    LOG_LEVEL="info"
fi

# --- Obtener configuración MQTT ---
# En HA addon, MQTT se obtiene de /data/options.json o del servicio MQTT
# Buscar en /share/mosquitto o usar defaults

if [ -f "/share/mosquitto/mosquitto.conf" ]; then
    echo "Configuración MQTT encontrada en /share/mosquitto"
fi

# Default MQTT config (el usuario debe configurar en options.json)
MQTT_HOST="${MQTT_BROKER:-core-mosquitto}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_USER="${MQTT_USERNAME:-}"
MQTT_PASS="${MQTT_PASSWORD:-}"

# --- Exportar variables de entorno ---
export MQTT_BROKER="${MQTT_HOST}"
export MQTT_PORT="${MQTT_PORT}"
export MQTT_USERNAME="${MQTT_USER}"
export MQTT_PASSWORD="${MQTT_PASS}"
export MQTT_TOPIC_PREFIX="${TOPIC_PREFIX}"
export MQTT_DISCOVERY_PREFIX="${DISCOVERY_PREFIX}"
export CRON_SCHEDULE="${CRON_SCHEDULE}"
export LOG_LEVEL="${LOG_LEVEL}"
export CREDENTIALS_PATH="/data/ute2mqtt"

# Timezone
export TZ="${TZ:-America/Montevideo}"

# --- Asegurar directorio de datos ---
mkdir -p "${CREDENTIALS_PATH}"

# --- Mapear nivel de log ---
case "${LOG_LEVEL}" in
    debug)   export PYTHON_LOG_LEVEL="DEBUG" ;;
    info)    export PYTHON_LOG_LEVEL="INFO" ;;
    warning) export PYTHON_LOG_LEVEL="WARNING" ;;
    error)   export PYTHON_LOG_LEVEL="ERROR" ;;
    *)       export PYTHON_LOG_LEVEL="INFO" ;;
esac

echo "========================================="
echo "Ute2MQTT Add-on"
echo "========================================="
echo "MQTT Broker: ${MQTT_BROKER}:${MQTT_PORT}"
echo "Topic Prefix: ${MQTT_TOPIC_PREFIX}"
echo "Discovery Prefix: ${MQTT_DISCOVERY_PREFIX}"
echo "Cron: ${CRON_SCHEDULE}"
echo "Log Level: ${LOG_LEVEL}"
echo "========================================="

# --- Verificar si hay configuración UTE ---
if [ -f "${CREDENTIALS_PATH}/ute_config.json" ]; then
    echo "Configuración UTE encontrada. Iniciando daemon..."
    python3 /app/main.py &
    MAIN_PID=$!
else
    echo "No se encontró configuración UTE."
    echo "Abrí la Web UI para completar la configuración inicial."
fi

# --- Iniciar Web UI para configuración ---
echo "Iniciando Web UI en puerto 8099..."
python3 /app/web_ui/app.py &
WEB_PID=$!

# --- Capturar señales para cleanup ---
cleanup() {
    echo "Deteniendo Ute2MQTT..."
    [ -n "$MAIN_PID" ] && kill "$MAIN_PID" 2>/dev/null
    [ -n "$WEB_PID" ] && kill "$WEB_PID" 2>/dev/null
    exit 0
}

trap cleanup SIGTERM SIGINT

# --- Esperar ---
wait
