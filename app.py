import streamlit as st
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo

from api import fetch_locations
from monitor import monitor, format_date
from config import CHECK_INTERVAL_MINUTES, DAYS_AHEAD_DEFAULT
import customer

TZ_CR = ZoneInfo("America/Costa_Rica")

st.set_page_config(page_title="Cita DEKRA", page_icon="🚗", layout="centered")

st.title("🚗 Cita DEKRA — Monitor de disponibilidad")
st.caption("Revisa automáticamente si hay citas disponibles y las agenda por vos.")

# ─── Cargar agencias ──────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_locations():
    return fetch_locations()

locations = get_locations()
if not locations:
    st.error("No se pudieron cargar las agencias. Verificá tu conexión.")
    st.stop()

location_map = {loc["locationName"].strip(): loc["locationId"] for loc in locations}

# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Configuración")

    selected_name = st.selectbox("Agencia", options=sorted(location_map.keys()))

    today = date.today()
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Desde", value=today, min_value=today)
    with col2:
        end_date = st.date_input(
            "Hasta",
            value=today + timedelta(days=DAYS_AHEAD_DEFAULT),
            min_value=today + timedelta(days=1),
        )

    st.divider()
    interval = st.slider("Revisar cada (minutos)", 1, 30, CHECK_INTERVAL_MINUTES)

    st.divider()
    sound_enabled = st.toggle("🔊 Sonido al encontrar cita", value=True)
    sound_times   = st.slider("Repeticiones del sonido", 1, 10, 5, disabled=not sound_enabled)

    st.divider()
    auto_book_on = st.toggle("🤖 Auto-agendar cuando encuentre cita", value=False)
    if auto_book_on:
        st.info(
            f"Se agendará automáticamente para:\n"
            f"**{customer.FIRST_NAME} {customer.LAST_NAME}**\n"
            f"Placa: `{customer.VEHICLE_REGO}`\n"
            f"Primer slot disponible."
        )

    st.divider()
    start_btn = st.button("▶ Iniciar monitor", use_container_width=True, type="primary",
                           disabled=monitor.running)
    stop_btn  = st.button("⏹ Detener",         use_container_width=True,
                           disabled=not monitor.running)

# ─── Acciones ─────────────────────────────────────────────────────────────────

if start_btn:
    monitor.configure(
        location_id       = location_map[selected_name],
        location_name     = selected_name,
        start_date        = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc),
        end_date          = datetime.combine(end_date,   datetime.min.time(), tzinfo=timezone.utc),
        interval_min      = interval,
        sound_enabled     = sound_enabled,
        sound_times       = sound_times,
        auto_book_enabled = auto_book_on,
    )
    monitor.start()
    st.rerun()

if stop_btn:
    monitor.stop()
    st.rerun()

# ─── Resultado de booking ─────────────────────────────────────────────────────

if monitor.booking_result:
    r = monitor.booking_result
    slot_label = format_date(r["slot"]["time"])
    st.success(f"## ✅ ¡Cita agendada!")
    st.markdown(f"""
| Campo | Valor |
|-------|-------|
| **Número de cita** | `{r['reservationNumber']}` |
| **Fecha y hora** | {slot_label} |
| **Agencia** | {monitor.location_name} |
| **Placa** | `{customer.VEHICLE_REGO}` |
| **bookingId** | `{r['bookingId']}` |
""")
    st.info("Revisá tu correo para la confirmación de DEKRA.")
    st.stop()

# ─── Estado actual ────────────────────────────────────────────────────────────

if monitor.running:
    mode = "🤖 Auto-agendando" if monitor.auto_book_enabled else "👁 Monitoreando"
    st.success(f"{mode} **{monitor.location_name}** — cada {monitor.interval_min} min")
else:
    st.info("Monitor detenido. Configurá y presioná **Iniciar**.")

if monitor.last_check:
    st.caption(f"Última revisión: {monitor.last_check.strftime('%d/%m/%Y %H:%M:%S')} CR")

# ─── Nuevas aperturas ─────────────────────────────────────────────────────────

if monitor.new_days:
    st.subheader("🆕 Nuevas aperturas detectadas")
    for d in monitor.new_days:
        st.success(f"**{format_date(d)}**  —  `{d}`")

# ─── Disponibilidad ───────────────────────────────────────────────────────────

st.subheader("📅 Días disponibles")

if not monitor.last_check:
    st.write("_Iniciá el monitor para ver disponibilidad._")
elif not monitor.available_days:
    st.warning(f"Sin disponibilidad en **{monitor.location_name}** para el rango seleccionado.")
else:
    st.write(f"**{len(monitor.available_days)} día(s) disponibles** en {monitor.location_name}:")
    for d in monitor.available_days:
        col1, col2 = st.columns([2, 3])
        with col1:
            st.write(f"📆 {format_date(d)}")
        with col2:
            st.code(d, language=None)

# ─── Auto-refresh ─────────────────────────────────────────────────────────────

if monitor.running:
    import time
    time.sleep(10)
    st.rerun()
