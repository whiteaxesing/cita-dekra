import requests
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from config import TENANT_ID, PRODUCT_ID, BASE_URL

LOG_FILE = Path(__file__).parent / "dekra-http.log"

def _log(method: str, url: str, req_body, status: int, res_body: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = (
        f"\n{'='*60}\n"
        f"[{ts}] {method} {url}\n"
        f"REQUEST: {json.dumps(req_body, ensure_ascii=False) if req_body else '-'}\n"
        f"RESPONSE ({status}): {res_body[:500]}\n"
    )
    LOG_FILE.open("a").write(entry)

# Sesión compartida — mantiene cookies entre filter-time-slots → confirm → booking
_session = requests.Session()
_session.headers.update({
    "Origin":  "https://booking.dekra.com",
    "Referer": "https://booking.dekra.com/",
})


def fetch_locations() -> list[dict]:
    url = f"{BASE_URL}/products/{PRODUCT_ID}/locations"
    try:
        r = _session.get(url, params={"tenantId": TENANT_ID}, timeout=10)
        r.raise_for_status()
        return [loc for loc in r.json() if not loc.get("unAvailableForRetail")]
    except Exception:
        return []


def fetch_available_days(location_id: str, start: datetime, end: datetime) -> list[str] | None:
    """Devuelve lista de días disponibles, o None si hay error de conexión."""
    params = {
        "startDate":             start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endDate":               end.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "tenantId":              TENANT_ID,
        "productId":             PRODUCT_ID,
        "locationId":            location_id,
        "selectedProductIdList": PRODUCT_ID,
    }
    try:
        r = _session.get(f"{BASE_URL}/availabledays", params=params, timeout=10)
        r.raise_for_status()
        return [d["date"] for d in r.json() if d.get("isAvailable")]
    except Exception:
        return None


def fetch_time_slots(location_id: str, day_date: str, selected_slot: dict | None = None) -> list[dict]:
    """Obtiene slots disponibles. Si se pasa selected_slot, lo incluye en selectedTimeslots para reservarlo."""
    start_dt = datetime.fromisoformat(day_date.replace("Z", "+00:00"))
    end_dt   = start_dt + timedelta(hours=23, minutes=59, seconds=59)

    selected = []
    if selected_slot:
        selected = [{
            "time":            selected_slot["time"],
            "resourceIds":     selected_slot["resourceIds"],
            "locationId":      location_id,
            "productDuration": selected_slot["productDuration"],
            "productId":       PRODUCT_ID,
            "productIndex":    selected_slot["productIndex"],
            "productName":     selected_slot["productName"],
        }]

    payload = {
        "isRetail":          True,
        "tenantId":          TENANT_ID,
        "locationId":        location_id,
        "productIds":        [PRODUCT_ID],
        "selectedTimeslots": selected,
        "startDate":         start_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endDate":           end_dt.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
    }
    try:
        url = f"{BASE_URL}/filter-time-slots"
        r = _session.post(url, json=payload, timeout=10)
        _log("POST", url, payload, r.status_code, r.text)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def confirm_timeslot(location_id: str, slot: dict) -> bool:
    """Bloquea temporalmente el slot. slot debe ser el objeto completo devuelto por filter-time-slots."""
    payload = [slot]
    try:
        url = f"{BASE_URL}/{location_id}/confirm-booking-timeslots"
        r = _session.post(url, json=payload, timeout=10)
        _log("POST", url, payload, r.status_code, r.text)
        body = r.json()
        return r.ok and isinstance(body, list) and len(body) > 0
    except Exception as e:
        return False


def create_booking(location_id: str, selected_slot: dict, all_slots: list[dict], customer: dict) -> dict | None:
    """Crea la reserva. selected_slot es el slot con isFirstSelected=True; all_slots es la lista completa del día."""
    t = selected_slot["time"].replace(".0000000Z", ".000Z")
    rego = customer["vehicle_rego"]

    # El item lleva selectedTimeSlot con la lista completa de slots del día
    item = {
        "locationId":   location_id,
        "availableTime": False,
        "productId":    PRODUCT_ID,
        "selectedTimeSlot": {
            "productId":       PRODUCT_ID,
            "productName":     selected_slot["productName"],
            "productFullName": selected_slot.get("productFullName", selected_slot["productName"]),
            "timeslots":       all_slots,
        },
        "vehicleRego":              rego,
        "customerFirstName":        customer["first_name"],
        "customerLastName":         customer["last_name"],
        "customerEmailAddress":     customer["email"],
        "countryPhoneCode":         customer["country_code"],
        "customerPhoneNumber":      customer["phone"],
        "acceptMarketingInformation": False,
        "vehicleRegos":             [],
        "note":                     "",
        "customerStreet":           "",
        "customerCity":             "",
        "customerPostalCode":       "",
        "reminderMethod":           1,
        "vehicleRego0":             rego,
        "regoValue":                rego,
        "startDateTime":            selected_slot["time"],
        "resourceIds":              selected_slot["resourceIds"],
        "productExtendedParameterModels": [],
        "hasBeenConfirm":           True,
    }
    payload = {
        "locationId":                    location_id,
        "availableTime":                 False,
        "vehicleRego":                   rego,
        "vehicleRego0":                  rego,
        "vehicleRegos":                  [],
        "acceptMarketingInformation":    False,
        "countryPhoneCode":              customer["country_code"],
        "customerCity":                  "",
        "customerEmailAddress":          customer["email"],
        "customerFirstName":             customer["first_name"],
        "customerLastName":              customer["last_name"],
        "customerPhoneNumber":           customer["phone"],
        "customerPostalCode":            "",
        "customerStreet":                "",
        "hasBeenConfirm":                False,
        "languageCode":                  "es-cr",
        "note":                          "",
        "notifyUser":                    True,
        "productBookingCreateItems":     [item],
        "productExtendedParameterModels": [],
        "productId":                     PRODUCT_ID,
        "reminderMethod":                1,
        "resourceIds":                   selected_slot["resourceIds"],
        "shortTenantName":               "CR",
        "startDateTime":                 t,
        "tenantId":                      TENANT_ID,
    }
    try:
        r = _session.post(BASE_URL, json=payload, timeout=15)
        _log("POST", BASE_URL, payload, r.status_code, r.text)
        return r.json()
    except Exception:
        return None


def release_timeslot(location_id: str, slot: dict) -> bool:
    """Libera/cancela un slot."""
    payload = [{
        "time":            slot["time"],
        "resourceIds":     slot["resourceIds"],
        "locationId":      location_id,
        "productDuration": slot["productDuration"],
        "productId":       PRODUCT_ID,
        "productIndex":    slot["productIndex"],
        "productName":     slot["productName"],
    }]
    try:
        r = _session.post(
            f"{BASE_URL}/{location_id}/release-resource-timeslots",
            json=payload, timeout=10
        )
        return r.ok
    except Exception:
        return False


def fetch_booking(vehicle_rego: str, email: str, phone: str) -> dict | None:
    """Busca la reserva activa por placa + correo + teléfono."""
    try:
        r = _session.get(
            f"{BASE_URL}/booking/{vehicle_rego}/param/true",
            params={"customerEmailAddress": email, "customerPhoneNumber": phone},
            timeout=10,
        )
        if not r.ok or not r.text.strip() or r.text.strip() == "null":
            return None
        return r.json()
    except Exception:
        return None


def check_update_allowed(booking_id: str) -> bool:
    """Verifica si la reserva puede ser modificada."""
    try:
        r = _session.get(f"{BASE_URL}/check-update-leadtime/{booking_id}", timeout=10)
        return r.ok and r.json().get("valid", False)
    except Exception:
        return False


def delete_booking(booking_id: str) -> bool:
    """Cancela la reserva."""
    try:
        r = _session.delete(f"{BASE_URL}/{booking_id}/{TENANT_ID}", timeout=10)
        return r.ok
    except Exception:
        return False
