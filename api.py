import requests
from datetime import datetime
from config import TENANT_ID, PRODUCT_ID, BASE_URL


def fetch_locations() -> list[dict]:
    """Obtiene todas las agencias disponibles para el producto DEKRA CR."""
    url = f"{BASE_URL}/products/{PRODUCT_ID}/locations"
    params = {"tenantId": TENANT_ID}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return [loc for loc in r.json() if not loc.get("unAvailableForRetail")]
    except Exception as e:
        return []


def fetch_available_days(location_id: str, start: datetime, end: datetime) -> list[str]:
    """Devuelve lista de date strings disponibles para la agencia y rango dado."""
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
