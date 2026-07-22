#!/usr/bin/with-contenv bashio
# ==============================================================================
# Ute2MQTT Home Assistant Add-on
# ==============================================================================

# --- Leer configuración del addon ---
TOPIC_PREFIX=$(bashio::config 'mqtt_topic_prefix')
CRON_SCHEDULE=$(bashio::config 'cron_schedule')
LOG_LEVEL=$(bashio::config 'log_level')

# --- Auto-detectar MQTT desde Home Assistant ---
bashio::log.info "Detectando configuración MQTT de Home Assistant..."

if bashio::services.has_service 'mqtt'; then
    MQTT_HOST=$(bashio::services mqtt "host")
    MQTT_PORT=$(bashio::services mqtt "port")
    MQTT_USER=$(bashio::services mqtt "username")
    MQTT_PASS=$(bashio::services mqtt "password")
    bashio::log.info "MQTT detectado: ${MQTT_HOST}:${MQTT_PORT}"
else
    bashio::log.fatal "No se encontró servicio MQTT en Home Assistant."
    bashio::log.fatal "Instalá el addon Mosquitto o configurá la integración MQTT."
    bashio::exit.nok
fi

# --- Exportar variables de entorno ---
export MQTT_BROKER="${MQTT_HOST}"
export MQTT_PORT="${MQTT_PORT}"
export MQTT_USERNAME="${MQTT_USER}"
export MQTT_PASSWORD="${MQTT_PASS}"
export MQTT_TOPIC_PREFIX="${TOPIC_PREFIX}"
export MQTT_DISCOVERY_PREFIX="homeassistant"
export CRON_SCHEDULE="${CRON_SCHEDULE}"
export LOG_LEVEL="${LOG_LEVEL}"
export CREDENTIALS_PATH="/config/ute2mqtt"
export TZ=$(bashio::config 'timezone' 2>/dev/null || echo "America/Montevideo")

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

# --- Verificar si hay configuración UTE ---
if [ -f "${CREDENTIALS_PATH}/ute_config.enc" ]; then
    bashio::log.info "Configuración UTE encontrada. Iniciando daemon..."
    python3 /app/main.py &
    MAIN_PID=$!
else
    bashio::log.warning "No se encontró configuración UTE."
    bashio::log.warning "Abrí la Web UI para completar la configuración inicial."
fi

# --- Iniciar Web UI para configuración ---
bashio::log.info "Iniciando Web UI en puerto 8099..."
python3 /app/web_ui/app.py &
WEB_PID=$!

# --- Capturar señales para cleanup ---
cleanup() {
    bashio::log.info "Deteniendo Ute2MQTT..."
    [ -n "$MAIN_PID" ] && kill "$MAIN_PID" 2>/dev/null
    [ -n "$WEB_PID" ] && kill "$WEB_PID" 2>/dev/null
    exit 0
}

trap cleanup SIGTERM SIGINT

# --- Esperar ---
wait
