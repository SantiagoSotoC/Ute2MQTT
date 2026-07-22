#!/bin/sh
# ==============================================================================
# Ute2MQTT Home Assistant Add-on
# ==============================================================================

set -e

# --- Leer TODA la configuración desde options.json de HA ---
OPTIONS_FILE="/data/options.json"
CONFIG_FILE="/data/ute2mqtt/ute_config.json"

# Función para leer valor del JSON con python
read_json() {
    python3 -c "
import json, sys
try:
    with open('$OPTIONS_FILE') as f:
        d = json.load(f)
    val = d.get('$1', '$2')
    print(val if val is not None else '$2')
except:
    print('$2')
"
}

if [ -f "$OPTIONS_FILE" ]; then
    echo "Leyendo configuración desde $OPTIONS_FILE"
    MQTT_HOST=$(read_json 'mqtt_broker' 'core-mosquitto')
    MQTT_PORT=$(read_json 'mqtt_port' '1883')
    MQTT_USER=$(read_json 'mqtt_username' '')
    MQTT_PASS=$(read_json 'mqtt_password' '')
    TOPIC_PREFIX=$(read_json 'mqtt_topic_prefix' 'UTE')
    DISCOVERY_PREFIX=$(read_json 'mqtt_discovery_prefix' 'homeassistant')
    CRON_SCHEDULE=$(read_json 'cron_schedule' '0 8 * * *')
    LOG_LEVEL=$(read_json 'log_level' 'info')
else
    echo "Archivo de configuración no encontrado, usando defaults"
    MQTT_HOST="core-mosquitto"
    MQTT_PORT="1883"
    MQTT_USER=""
    MQTT_PASS=""
    TOPIC_PREFIX="UTE"
    DISCOVERY_PREFIX="homeassistant"
    CRON_SCHEDULE="0 8 * * *"
    LOG_LEVEL="info"
fi

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
echo "MQTT User: ${MQTT_USERNAME}"
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
