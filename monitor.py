import threading
import time
import platform
import subprocess
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from api import fetch_available_days

TZ_CR = ZoneInfo("America/Costa_Rica")


def _play_sound_mac(sound: str, times: int):
    for _ in range(times):
        subprocess.Popen(["afplay", f"/System/Library/Sounds/{sound}.aiff"]).wait()


def _speak_mac(message: str, voice: str = "Paulina"):
    subprocess.Popen(["say", "-v", voice, message]).wait()


def _notify_windows(title: str, message: str):
    try:
        from plyer import notification
        notification.notify(title=title, message=message, timeout=10)
    except Exception:
        pass


def _notify_linux(title: str, message: str):
    try:
        subprocess.Popen(["notify-send", title, message])
    except Exception:
        pass


def trigger_alert(location_name: str, dates: list[str], sound_enabled: bool, sound_times: int):
    msg = f"Hay disponibilidad en {location_name}. ¡Agendá ya!"
    system = platform.system()

    if system == "Darwin" and sound_enabled:
        _play_sound_mac("Glass", sound_times)
        _speak_mac(msg)
    elif system == "Windows":
        _notify_windows("DEKRA — Cita disponible", msg)
    elif system == "Linux":
        _notify_linux("DEKRA — Cita disponible", msg)


def format_date(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ_CR)
    dias  = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
             "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    return f"{dias[dt.weekday()]} {dt.day} {meses[dt.month - 1]} {dt.year}"


class Monitor:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Estado compartido (leído por la UI)
        self.running        = False
        self.last_check     = None
        self.available_days: list[str] = []
        self.new_days:       list[str] = []
        self._previous_days: set[str]  = set()

        # Configuración (seteada desde la UI)
        self.location_id    = ""
        self.location_name  = ""
        self.start_date     = datetime.now(timezone.utc)
        self.end_date       = datetime.now(timezone.utc) + timedelta(days=30)
        self.interval_min   = 5
        self.sound_enabled  = True
        self.sound_times    = 5

    def configure(self, location_id: str, location_name: str,
                  start_date: datetime, end_date: datetime,
                  interval_min: int, sound_enabled: bool, sound_times: int):
        self.location_id   = location_id
        self.location_name = location_name
        self.start_date    = start_date
        self.end_date      = end_date
        self.interval_min  = interval_min
        self.sound_enabled = sound_enabled
        self.sound_times   = sound_times

    def start(self):
        if self.running:
            return
        self._stop_event.clear()
        self._previous_days = set()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.running = True

    def stop(self):
        self._stop_event.set()
        self.running = False

    def _loop(self):
        while not self._stop_event.is_set():
            self._check()
            self._stop_event.wait(timeout=self.interval_min * 60)

    def _check(self):
        days = fetch_available_days(self.location_id, self.start_date, self.end_date)
        curr = set(days)
        self.new_days       = sorted(curr - self._previous_days)
        self._previous_days = curr
        self.available_days = sorted(days)
        self.last_check     = datetime.now(TZ_CR)

        if self.new_days:
            trigger_alert(self.location_name, self.new_days,
                          self.sound_enabled, self.sound_times)


# Instancia global compartida entre rerenders de Streamlit
monitor = Monitor()
