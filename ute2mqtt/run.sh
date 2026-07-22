#!/usr/bin/with-contenv bashio
# ==============================================================================
# Ute2MQTT Home Assistant Add-on
# ==============================================================================

# --- Leer configuración del addon ---
TOPIC_PREFIX=$(bashio::config 'mqtt_topic_prefix')
DISCOVERY_PREFIX=$(bashio::config 'mqtt_discovery_prefix')
CRON_SCHEDULE=$(bashio::config 'cron_schedule')
LOG_LEVEL=$(bashio::config 'log_level')

# --- Auto-detectar MQTT desde Home Assistant ---
bashio::log.info "Detectando configuración MQTT de Home Assistant..."

# Primero intentar auto-detectar de los servicios de HA
if bashio::services.available mqtt ; then
    MQTT_HOST=$(bashio::services mqtt 'host')
    MQTT_PORT=$(bashio::services mqtt 'port')
    MQTT_USER=$(bashio::services mqtt 'username')
    MQTT_PASS=$(bashio::services mqtt 'password')
    bashio::log.info "MQTT auto-detectado: ${MQTT_HOST}:${MQTT_PORT}"
else
    bashio::log.warning "Servicio MQTT no disponible, verificando configuración manual..."
    # Intentar usar configuración manual del usuario
    if bashio::config.has_value 'mqtt_host' ; then
        MQTT_HOST=$(bashio::config 'mqtt_host')
        MQTT_PORT=$(bashio::config 'mqtt_port')
        MQTT_USER=$(bashio::config 'mqtt_username')
        MQTT_PASS=$(bashio::config 'mqtt_password')
        bashio::log.info "MQTT desde configuración: ${MQTT_HOST}:${MQTT_PORT}"
    else
        bashio::log.error "No se encontró configuración MQTT."
        bashio::log.error "Instalá el addon Mosquitto o configurá MQTT manualmente."
        bashio::exit.nok
    fi
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

# Timezone
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

bashio::log.info "========================================="
bashio::log.info "Ute2MQTT Add-on"
bashio::log.info "========================================="
bashio::log.info "MQTT Broker: ${MQTT_BROKER}:${MQTT_PORT}"
bashio::log.info "MQTT User: ${MQTT_USERNAME}"
bashio::log.info "Topic Prefix: ${MQTT_TOPIC_PREFIX}"
bashio::log.info "Discovery Prefix: ${MQTT_DISCOVERY_PREFIX}"
bashio::log.info "Cron: ${CRON_SCHEDULE}"
bashio::log.info "Log Level: ${LOG_LEVEL}"
bashio::log.info "========================================="

# --- Verificar si hay configuración UTE ---
if [ -f "${CREDENTIALS_PATH}/ute_config.json" ]; then
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
