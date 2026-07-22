#!/usr/bin/env python3
"""
Ute2MQTT - Punto de Entrada Principal.

Obtiene datos de consumo eléctrico del Proveedor de Energía y los publica vía MQTT.
Soporta modo addon (Home Assistant) y modo standalone (Docker/compose).
"""

import json
import os
import sys
import logging
import signal
from datetime import datetime
from typing import Optional

from ute.session import UTESession
from ute.mqtt import MQTTPublisher
from scheduler import CronScheduler, DailyScheduler
from ute.credentials import CredentialsManager
from ute.tariffs import TariffProcessor

# Configuración de logging
log_level = os.environ.get("PYTHON_LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_ute_config(storage_path: str) -> dict:
    """Carga configuración UTE desde archivo JSON (modo addon)."""
    config_file = os.path.join(storage_path, "ute_config.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error al cargar config UTE: {e}")
    return {}


class Ute2MQTT:
    """Clase principal que orquesta la recolección de datos del Proveedor y publicación MQTT."""

    def __init__(self):
        """Inicializa el cliente con la configuración del entorno o archivo."""
        # Configuración de almacenamiento de credenciales
        storage_path = os.environ.get("CREDENTIALS_PATH", "./credentials")
        self.creds_manager = CredentialsManager(storage_path)

        # Intentar cargar configuración desde archivo (modo addon) o variables de entorno
        file_config = load_ute_config(storage_path)

        self.account_id = file_config.get("account_id") or os.environ.get("UTE_ACCOUNT_ID")
        self.service_id = file_config.get("service_id") or os.environ.get("UTE_SERVICE_ID")
        self.service_point_id = file_config.get("service_point_id") or os.environ.get("UTE_SERVICE_POINT_ID")
        self.tariff = file_config.get("tariff") or os.environ.get("UTE_TARIFF")
        self.schedule_code = file_config.get("schedule_code") or os.environ.get("UTE_SCHEDULE_CODE")

        if not all([self.account_id, self.service_id, self.service_point_id, self.tariff]):
            logger.error("Faltan datos de configuración UTE. Configurá desde la Web UI.")
            sys.exit(1)

        self.tariff = self.tariff.upper()

        # Configuración MQTT
        self.mqtt_broker = os.environ.get("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.environ.get("MQTT_PORT", "1883"))
        self.mqtt_username = os.environ.get("MQTT_USERNAME")
        self.mqtt_password = os.environ.get("MQTT_PASSWORD")
        self.mqtt_topic_prefix = os.environ.get("MQTT_TOPIC_PREFIX", "UTE")
        self.mqtt_client_id = os.environ.get("MQTT_CLIENT_ID")
        self.mqtt_discovery_prefix = os.environ.get("MQTT_DISCOVERY_PREFIX", "homeassistant")

        # Configuración del planificador (cron o AM/PM)
        cron_schedule = os.environ.get("CRON_SCHEDULE")
        time_window = os.environ.get("SCHEDULE_TIME", "AM").upper()

        if cron_schedule:
            self.scheduler_class = "cron"
            self.cron_schedule = cron_schedule
        else:
            self.scheduler_class = "daily"
            self.time_window = time_window

        # Inicializar Sesión
        try:
            self.session = UTESession(self.creds_manager)
        except ValueError as e:
            logger.error(str(e))
            logger.error("Configurá credenciales desde la Web UI del addon")
            sys.exit(1)

        if self.tariff in ("TRT", "TRD") and not self.schedule_code:
            logger.warning(f"Para tarifa {self.tariff} se recomienda UTE_SCHEDULE_CODE (ej. TRIPLERES19)")

        self.mqtt: Optional[MQTTPublisher] = None
        self.scheduler = None

    def fetch_and_publish(self):
        """Tarea principal: obtener datos y publicar a MQTT."""
        logger.info("Iniciando obtención de datos...")

        client = self.session.get_client()
        if not client:
            logger.error("No se pudo establecer sesión con el Proveedor")
            return

        consumption = client.get_current_consumption(self.account_id)
        if not consumption:
            logger.error("Falló al obtener consumo")
            return

        debt = client.get_total_debt(self.account_id)

        state = {
            "current_consumption": consumption.get("currentConsumption", 0),
            "current_spending": consumption.get("currentSpending", 0),
            "total_debt": debt or 0,
            "tariff": self.tariff,
            "period_start": consumption.get("initialDate"),
            "period_end": consumption.get("finalDate"),
        }

        if self.schedule_code and state["period_start"] and state["period_end"]:
            band_data = client.get_consumption_by_band(
                self.service_point_id,
                self.schedule_code,
                state["period_start"],
                state["period_end"]
            )

            if band_data:
                processed_bands = TariffProcessor.process_bands(self.tariff, band_data)
                state.update(processed_bands)

        logger.info(f"Datos recolectados: {state}")

        try:
            self.mqtt = MQTTPublisher(
                broker=self.mqtt_broker,
                port=self.mqtt_port,
                username=self.mqtt_username,
                password=self.mqtt_password,
                topic_prefix=self.mqtt_topic_prefix,
                client_id=self.mqtt_client_id,
                discovery_prefix=self.mqtt_discovery_prefix
            )

            if self.mqtt.connect():
                self.mqtt.publish_discovery(self.service_id, self.account_id, self.tariff)
                self.mqtt.publish_state(self.service_id, state)
                self.mqtt.disconnect()
            else:
                logger.error("No se pudo conectar al broker MQTT")

        except Exception as e:
            logger.error(f"Error durante la publicación MQTT: {e}")
        finally:
            self.mqtt = None

    def run(self):
        """Ejecuta el cliente con planificador."""
        logger.info("Iniciando Ute2MQTT...")
        logger.info(f"Cuenta: {self.account_id}")
        logger.info(f"Servicio: {self.service_id} | Tarifa: {self.tariff}")

        def signal_handler(sig, frame):
            logger.info("Apagado solicitado...")
            if self.scheduler:
                self.scheduler.stop()
            if self.mqtt:
                self.mqtt.disconnect()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        if self.scheduler_class == "cron":
            logger.info(f"Usando scheduler cron: {self.cron_schedule}")
            self.scheduler = CronScheduler(
                task=self.fetch_and_publish,
                cron_expression=self.cron_schedule,
                run_on_start=True
            )
        else:
            logger.info(f"Usando scheduler diario ventana: {self.time_window}")
            self.scheduler = DailyScheduler(
                task=self.fetch_and_publish,
                time_window=self.time_window,
                run_on_start=True
            )

        self.scheduler.start()


def main():
    app = Ute2MQTT()
    app.run()


if __name__ == "__main__":
    main()
