import requests
from datetime import datetime, timedelta
from config import TENANT_ID, PRODUCT_ID, BASE_URL


def fetch_locations() -> list[dict]:
    url = f"{BASE_URL}/products/{PRODUCT_ID}/locations"
    try:
        r = requests.get(url, params={"tenantId": TENANT_ID}, timeout=10)
        r.raise_for_status()
        return [loc for loc in r.json() if not loc.get("unAvailableForRetail")]
    except Exception:
        return []


def fetch_available_days(location_id: str, start: datetime, end: datetime) -> list[str]:
    params = {
        "startDate":             start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endDate":               end.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "tenantId":              TENANT_ID,
        "productId":             PRODUCT_ID,
        "locationId":            location_id,
        "selectedProductIdList": PRODUCT_ID,
    }
    try:
        r = requests.get(f"{BASE_URL}/availabledays", params=params, timeout=10)
        r.raise_for_status()
        return [d["date"] for d in r.json() if d.get("isAvailable")]
    except Exception:
        return []


def fetch_time_slots(location_id: str, day_date: str) -> list[dict]:
    """Obtiene slots disponibles para un día específico (day_date = ISO date string del availabledays)."""
    # El día en UTC+0 06:00 → medianoche CR, end = siguiente día 05:59:59
    start_dt = datetime.fromisoformat(day_date.replace("Z", "+00:00"))
    end_dt   = start_dt + timedelta(hours=23, minutes=59, seconds=59)

    payload = {
        "isRetail":         True,
        "tenantId":         TENANT_ID,
        "locationId":       location_id,
        "productIds":       [PRODUCT_ID],
        "selectedTimeslots": [],
        "startDate":        start_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endDate":          end_dt.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
    }
    try:
        r = requests.post(f"{BASE_URL}/filter-time-slots", json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def confirm_timeslot(location_id: str, slot: dict) -> bool:
    """Bloquea temporalmente el slot antes de confirmar la reserva."""
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
        r = requests.post(
            f"{BASE_URL}/{location_id}/confirm-booking-timeslots",
            json=payload, timeout=10
        )
        return r.ok
    except Exception:
        return False


def create_booking(location_id: str, slot: dict, customer: dict) -> dict | None:
    """Crea la reserva. Devuelve el resultado o None si falla."""
    item = {
        "locationId":      location_id,
        "availableTime":   False,
        "productDuration": slot["productDuration"],
        "productId":       PRODUCT_ID,
        "productIndex":    slot["productIndex"],
        "productName":     slot["productName"],
        "resourceIds":     slot["resourceIds"],
        "time":            slot["time"],
    }
    payload = {
        "locationId":                    location_id,
        "availableTime":                 False,
        "vehicleRego":                   customer["vehicle_rego"],
        "vehicleRego0":                  customer["vehicle_rego"],
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
        "resourceIds":                   slot["resourceIds"],
        "shortTenantName":               "CR",
        "startDateTime":                 slot["time"].replace(".0000000Z", ".000Z"),
        "tenantId":                      TENANT_ID,
    }
    try:
        r = requests.post(BASE_URL, json=payload, timeout=15)
        r.raise_for_status()
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
        r = requests.post(
            f"{BASE_URL}/{location_id}/release-resource-timeslots",
            json=payload, timeout=10
        )
        return r.ok
    except Exception:
        return False
