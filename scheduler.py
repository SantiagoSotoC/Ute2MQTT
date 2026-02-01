import logging
import random
import threading
from datetime import datetime, timedelta, time, date
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class DailyScheduler:
    """
    Planificador diario que ejecuta una tarea específica una vez al día,
    seleccionando un horario aleatorio dentro de una ventana de tiempo definida.
    """

    def __init__(self, task: Callable, time_window: str = "AM", run_on_start: bool = True):
        self.task = task
        self.time_window = time_window.upper()
        self.run_on_start = run_on_start
        self._stop_event = threading.Event()
        self._last_run_date: Optional[date] = None  # <-- clave

    def _window_bounds(self):
        if self.time_window == "AM":
            return 6, 12   # 06:00 inclusive, 12:00 exclusivo
        return 12, 18      # 12:00 inclusive, 18:00 exclusivo

    def _random_time_in_window(self) -> time:
        start_hour, end_hour = self._window_bounds()
        hour = random.randint(start_hour, end_hour - 1)
        minute = random.randint(0, 59)
        return time(hour=hour, minute=minute, second=0, microsecond=0)

    def _get_next_run_time(self) -> datetime:
        """
        Calcula la próxima fecha y hora de ejecución:
        - Si la tarea ya se ejecutó hoy, se programa para mañana.
        - Si no se ejecutó hoy, se intenta programar para hoy.
        - Si el horario aleatorio generado para hoy ya pasó, se programa para mañana.
        """
        now = datetime.now()
        today = now.date()

        if self._last_run_date == today:
            target_date = today + timedelta(days=1)
        else:
            target_date = today

        # Intentar fecha objetivo; si queda en el pasado, mover a mañana
        t = self._random_time_in_window()
        next_run = datetime.combine(target_date, t)

        if next_run <= now:
            target_date = today + timedelta(days=1)
            t = self._random_time_in_window()
            next_run = datetime.combine(target_date, t)

        return next_run

    def _run_task(self):
        try:
            self.task()
        except Exception as e:
            logger.exception("Ejecución de tarea fallida: %s", e)
        finally:
            self._last_run_date = datetime.now().date()

    def start(self):
        self._stop_event.clear()

        if self.run_on_start:
            logger.info("Ejecutando tarea inicial...")
            self._run_task()

        while not self._stop_event.is_set():
            next_run = self._get_next_run_time()
            wait_seconds = (next_run - datetime.now()).total_seconds()

            logger.info("Próxima ejecución programada para: %s", next_run.strftime('%Y-%m-%d %H:%M:%S'))
            logger.info("Esperando %.1f horas...", max(0, wait_seconds) / 3600)

            if self._stop_event.wait(timeout=max(0, wait_seconds)):
                break

            logger.info("Ejecutando tarea programada...")
            self._run_task()

    def stop(self):
        logger.info("Deteniendo planificador...")
        self._stop_event.set()
