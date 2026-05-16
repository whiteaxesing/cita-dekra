import threading
import platform
import subprocess
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from api import fetch_available_days, fetch_time_slots, confirm_timeslot, create_booking

TZ_CR = ZoneInfo("America/Costa_Rica")


def _play_glass(times: int = 1):
    subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"]).wait()


def _speak(msg: str):
    subprocess.Popen(["say", "-v", "Paulina", msg]).wait()


def _notify_windows(title: str, msg: str):
    try:
        from plyer import notification
        notification.notify(title=title, message=msg, timeout=10)
    except Exception:
        pass


def _notify_linux(title: str, msg: str):
    try:
        subprocess.Popen(["notify-send", title, msg])
    except Exception:
        pass


def trigger_alert(location_name: str, sound_times: int):
    msg = f"Hay disponibilidad en {location_name}. ¡Agendá ya!"
    system = platform.system()
    if system == "Darwin":
        _play_glass(sound_times)
        _speak(msg)
    elif system == "Windows":
        _notify_windows("DEKRA — Cita disponible", msg)
    elif system == "Linux":
        _notify_linux("DEKRA — Cita disponible", msg)


def trigger_booked_alert(location_name: str, slot_time: str, reservation: str, sound_times: int):
    msg = f"Cita agendada en {location_name}. Número {reservation}. Revisá tu correo."
    system = platform.system()
    if system == "Darwin":
        _play_glass(sound_times)
        _speak(msg)
    elif system == "Windows":
        _notify_windows("DEKRA — ¡Cita confirmada!", msg)
    elif system == "Linux":
        _notify_linux("DEKRA — ¡Cita confirmada!", msg)


def format_date(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ_CR)
    dias  = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
             "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    return f"{dias[dt.weekday()]} {dt.day} {meses[dt.month - 1]} {dt.year} {dt.strftime('%H:%M')}"


def _filter_by_hour(slots: list[dict], hour_range: tuple[int, int] | None) -> list[dict]:
    if not hour_range:
        return slots
    h_from, h_to = hour_range
    result = []
    for s in slots:
        dt = datetime.fromisoformat(s["time"].replace("Z", "+00:00")).astimezone(TZ_CR)
        if h_from <= dt.hour <= h_to:
            result.append(s)
    return result


def auto_book(location_id: str, location_name: str, available_days: list[str],
              customer: dict, sound_times: int,
              hour_range: tuple[int, int] | None = None) -> dict | None:
    """Toma el primer día disponible, agarra el primer slot y reserva. Devuelve resultado o None."""
    for day in available_days:
        slots = _filter_by_hour(fetch_time_slots(location_id, day), hour_range)
        if not slots:
            continue

        for slot in slots[:3]:
            all_slots = fetch_time_slots(location_id, day, selected_slot=slot)
            selected  = next((s for s in all_slots if s.get("isFirstSelected")), slot)
            confirm_timeslot(location_id, selected)
            result = create_booking(location_id, selected, all_slots, customer)
            if result and result.get("isSuccess"):
                items = result.get("bookingResultItems", [])
                reservation = items[0].get("reservationNumber", "?") if items else "?"
                trigger_booked_alert(location_name, slot["time"], reservation, sound_times)
                return {
                    "reservationNumber": reservation,
                    "bookingId":         items[0].get("bookingId") if items else None,
                    "slot":              selected,
                    "day":               day,
                }

    return None


class Monitor:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self.running          = False
        self.last_check       = None
        self.connection_error = False
        self.available_days: list[str] = []
        self.new_days:       list[str] = []
        self._previous_days: set[str]  = set()
        self.booking_result: dict | None = None

        self.location_id    = ""
        self.location_name  = ""
        self.start_date     = datetime.now(timezone.utc)
        self.end_date       = datetime.now(timezone.utc) + timedelta(days=30)
        self.interval_min   = 5
        self.sound_enabled     = True
        self.sound_times       = 1
        self.auto_book_enabled = False
        self.customer: dict    = {}
        self.hour_range: tuple[int, int] | None = None

    def configure(self, location_id: str, location_name: str,
                  start_date: datetime, end_date: datetime,
                  interval_min: int, sound_enabled: bool, sound_times: int,
                  auto_book_enabled: bool, customer: dict,
                  hour_range: tuple[int, int] | None = None):
        self.location_id       = location_id
        self.location_name     = location_name
        self.start_date        = start_date
        self.end_date          = end_date
        self.interval_min      = interval_min
        self.sound_enabled     = sound_enabled
        self.sound_times       = sound_times
        self.auto_book_enabled = auto_book_enabled
        self.customer          = customer
        self.hour_range        = hour_range

    def start(self):
        if self.running:
            return
        self._stop_event.clear()
        self._previous_days  = set()
        self._first_check    = True
        self.booking_result  = None
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.running = True

    def stop(self):
        self._stop_event.set()
        self.running = False

    def _loop(self):
        while not self._stop_event.is_set():
            self._check()
            # Si reservó exitosamente, detiene el monitor solo
            if self.booking_result:
                self.running = False
                return
            self._stop_event.wait(timeout=self.interval_min * 60)

    def _check(self):
        days = fetch_available_days(self.location_id, self.start_date, self.end_date)
        self.last_check = datetime.now(TZ_CR)

        if days is None:
            self.connection_error = True
            return

        self.connection_error = False
        curr = set(days)

        self.new_days       = [] if self._first_check else sorted(curr - self._previous_days)
        self._previous_days = curr
        self._first_check   = False
        self.available_days = sorted(days)

        if days and self.sound_enabled and not self.auto_book_enabled:
            trigger_alert(self.location_name, self.sound_times)

        if days and self.auto_book_enabled and not self.booking_result:
            result = auto_book(self.location_id, self.location_name, days, self.customer, self.sound_times, self.hour_range)
            if result:
                self.booking_result = result


monitor = Monitor()
