import customtkinter as ctk
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo
from datetime import timezone as _tz
from threading import Thread
import threading
from pathlib import Path
import json

from api import (fetch_locations, fetch_available_days, fetch_time_slots,
                 confirm_timeslot, create_booking, release_timeslot,
                 fetch_booking, check_update_allowed, delete_booking)
from config import PRODUCT_ID, VERSION, REPO
from monitor import monitor, format_date, _filter_days_by_weekday

try:
    TZ_CR = ZoneInfo("America/Costa_Rica")
except Exception:
    TZ_CR = _tz(timedelta(hours=-6))
CUSTOMER_FILE = Path.home() / ".cita_dekra.json"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def load_customer() -> dict:
    if CUSTOMER_FILE.exists():
        try:
            return json.loads(CUSTOMER_FILE.read_text())
        except Exception:
            pass
    return {}


def save_customer(data: dict):
    CUSTOMER_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🚗 Cita DEKRA")
        self.geometry("700x860")
        self.minsize(500, 600)
        self.resizable(True, True)

        self._locations: dict[str, str] = {}
        self._customer = load_customer()
        self._load_locations()
        self._build_ui()
        self._refresh()

        if not self._customer.get("email"):
            self._tabs.set("Mis datos")

        Thread(target=self._check_update, daemon=True).start()

    # ─── Helpers de UI ───────────────────────────────────────────────────────

    def _filter_slots_by_hour(self, slots: list[dict], hour_from: int, hour_to: int) -> list[dict]:
        result = []
        for s in slots:
            dt = datetime.fromisoformat(s["time"].replace("Z", "+00:00")).astimezone(TZ_CR)
            if hour_from <= dt.hour <= hour_to:
                result.append(s)
        return result

    def _build_day_filter(self, parent, pad) -> tuple[ctk.BooleanVar, list[ctk.BooleanVar]]:
        """Retorna (enabled_var, [day_vars Lun..Dom])."""
        DAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        enabled_var = ctk.BooleanVar(value=False)
        day_vars    = [ctk.BooleanVar(value=True) for _ in DAYS]

        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x", **pad)

        day_frame = ctk.CTkFrame(container, fg_color="transparent")
        row = ctk.CTkFrame(day_frame, fg_color="transparent")
        row.pack(fill="x")
        for name, var in zip(DAYS, day_vars):
            ctk.CTkCheckBox(row, text=name, variable=var, width=68).pack(side="left", padx=2)

        ctk.CTkSwitch(container, text="📆 Filtrar por día", variable=enabled_var,
                      command=lambda: day_frame.pack(fill="x", pady=(4, 0)) if enabled_var.get()
                                      else day_frame.pack_forget()).pack(fill="x")
        return enabled_var, day_vars

    def _day_filter(self, enabled_var: ctk.BooleanVar, day_vars: list[ctk.BooleanVar]) -> set[int] | None:
        if not enabled_var.get():
            return None
        result = {i for i, v in enumerate(day_vars) if v.get()}
        return result if result else None

    def _build_time_filter(self, parent, pad) -> tuple[ctk.BooleanVar, ctk.StringVar, ctk.StringVar]:
        """Retorna (enabled_var, from_var, to_var). El frame de horas se muestra/oculta dentro de un contenedor fijo."""
        enabled_var = ctk.BooleanVar(value=False)
        from_var    = ctk.StringVar(value="7:00")
        to_var      = ctk.StringVar(value="17:00")
        hours       = [f"{h}:00" for h in range(5, 20)]

        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x", **pad)

        ctk.CTkSwitch(container, text="🕐 Filtrar por horario", variable=enabled_var,
                      command=lambda: hour_frame.pack(fill="x", pady=(4, 0)) if enabled_var.get()
                                      else hour_frame.pack_forget()).pack(fill="x")

        hour_frame = ctk.CTkFrame(container, fg_color="transparent")
        left = ctk.CTkFrame(hour_frame, fg_color="transparent")
        left.pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkLabel(left, text="Desde las").pack(anchor="w")
        ctk.CTkOptionMenu(left, variable=from_var, values=hours).pack(fill="x")
        right = ctk.CTkFrame(hour_frame, fg_color="transparent")
        right.pack(side="right", expand=True, fill="x", padx=(5, 0))
        ctk.CTkLabel(right, text="Hasta las").pack(anchor="w")
        ctk.CTkOptionMenu(right, variable=to_var, values=hours).pack(fill="x")

        return enabled_var, from_var, to_var

    def _date_picker(self, parent, initial: date) -> "DatePicker":
        return DatePicker(parent, initial)

    # ─── Cargar agencias ──────────────────────────────────────────────────────

    def _check_update(self):
        try:
            import requests as _req
            r = _req.get(f"https://api.github.com/repos/{REPO}/releases/latest", timeout=5)
            latest = r.json().get("tag_name", "").lstrip("v")
            if latest and latest != VERSION:
                self.after(0, lambda: self._update_label.configure(
                    text=f"⬆ Nueva versión disponible: v{latest} — descargá en Releases",
                ))
                self.after(0, lambda: self._update_label.bind(
                    "<Button-1>", lambda e: __import__("webbrowser").open(
                        f"https://github.com/{REPO}/releases/latest")
                ))
        except Exception:
            pass

    def _load_locations(self):
        locs = fetch_locations()
        self._locations = {loc["locationName"].strip(): loc["locationId"] for loc in locs}

    # ─── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        ctk.CTkLabel(self, text="🚗 Cita DEKRA", font=ctk.CTkFont(size=22, weight="bold")).pack(padx=20, pady=(20, 4))
        ctk.CTkLabel(self, text="Monitor automático de disponibilidad", text_color="gray").pack(pady=(0, 10))

        self._update_label = ctk.CTkLabel(self, text="", text_color="#f0a500", cursor="hand2")
        self._update_label.pack()

        self._tabs = ctk.CTkTabview(self)
        self._tabs.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self._tabs.add("Agendador")
        self._tabs.add("Modificar cita")
        self._tabs.add("Mis datos")

        self._build_monitor_tab(self._tabs.tab("Agendador"))
        self._build_modificar_tab(self._tabs.tab("Modificar cita"))
        self._build_datos_tab(self._tabs.tab("Mis datos"))

    def _build_monitor_tab(self, tab):
        pad  = {"padx": 16, "pady": 5}
        padx = {"padx": 16}

        # ── Controles ──
        ctrl = ctk.CTkFrame(tab, fg_color="transparent")
        ctrl.pack(fill="x")

        # ── Resultados (toma el espacio restante) ──
        results_frame = ctk.CTkFrame(tab, fg_color="transparent")
        results_frame.pack(fill="both", expand=True, padx=16, pady=(4, 8))
        self.status_label = ctk.CTkLabel(results_frame, text="Monitor detenido.", text_color="gray", anchor="w")
        self.status_label.pack(fill="x")
        ctk.CTkLabel(results_frame, text="📅 Resultados", font=ctk.CTkFont(size=13, weight="bold"), anchor="w").pack(fill="x")
        self.results_box = ctk.CTkTextbox(results_frame, height=140, state="disabled", font=ctk.CTkFont(family="Courier", size=12))
        self.results_box.pack(fill="x")

        # ── Agencias (dropdown multi-selección) ──
        ctk.CTkLabel(ctrl, text="Agencias a monitorear", anchor="w").pack(fill="x", **pad)
        self._loc_check_vars: dict[str, ctk.BooleanVar] = {}
        self._loc_checkboxes: dict[str, ctk.CTkCheckBox] = {}
        for name in sorted(self._locations.keys()):
            self._loc_check_vars[name] = ctk.BooleanVar(value=False)
        self._loc_dropdown_btn = ctk.CTkButton(
            ctrl, text="Ninguna seleccionada", anchor="w",
            fg_color="#2b2b2b", hover_color="#3a3a3a", text_color="white",
            command=self._toggle_loc_dropdown
        )
        self._loc_dropdown_btn.pack(fill="x", padx=16, pady=(0, 0))
        self._loc_dropdown_frame = ctk.CTkScrollableFrame(ctrl, fg_color="#1e1e1e", corner_radius=6, height=160)
        for name, var in self._loc_check_vars.items():
            cb = ctk.CTkCheckBox(self._loc_dropdown_frame, text=name, variable=var,
                                 command=self._update_loc_btn_text)
            cb.pack(anchor="w", padx=12, pady=3)
            self._loc_checkboxes[name] = cb
        self._loc_dropdown_open = False

        # ── Fechas ──
        date_frame = ctk.CTkFrame(ctrl, fg_color="transparent")
        date_frame.pack(fill="x", **pad)
        left = ctk.CTkFrame(date_frame, fg_color="transparent")
        left.pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkLabel(left, text="Desde").pack(anchor="w")
        self.start_entry = self._date_picker(left, date.today())
        self.start_entry.pack(fill="x")
        right = ctk.CTkFrame(date_frame, fg_color="transparent")
        right.pack(side="right", expand=True, fill="x", padx=(5, 0))
        ctk.CTkLabel(right, text="Hasta").pack(anchor="w")
        self.end_entry = self._date_picker(right, date.today() + timedelta(days=30))
        self.end_entry.pack(fill="x")

        # ── Filtros ──
        self.time_enabled, self.time_from, self.time_to = self._build_time_filter(ctrl, pad)
        self.day_enabled, self.day_vars = self._build_day_filter(ctrl, pad)

        # ── Intervalo ──
        ctk.CTkLabel(ctrl, text="Revisar cada (minutos)", anchor="w").pack(fill="x", **pad)
        self.interval_var = ctk.IntVar(value=5)
        interval_frame = ctk.CTkFrame(ctrl, fg_color="transparent")
        interval_frame.pack(fill="x", **pad)
        self.interval_slider = ctk.CTkSlider(interval_frame, from_=1, to=30, variable=self.interval_var,
                                              command=lambda v: self.interval_label.configure(text=f"{int(v)} min"))
        self.interval_slider.pack(side="left", expand=True, fill="x")
        self.interval_label = ctk.CTkLabel(interval_frame, text="5 min", width=50)
        self.interval_label.pack(side="right")

        # ── Sonido ──
        self.sound_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(ctrl, text="🔊 Sonido al encontrar cita", variable=self.sound_var).pack(fill="x", **pad)
        self.autobook_var = ctk.BooleanVar(value=True)  # siempre activo
        self.customer_label = ctk.CTkLabel(ctrl, text=self._customer_summary(), text_color="gray", anchor="w")
        self.customer_label.pack(fill="x", padx=16)

        # ── Botones ──
        btn_frame = ctk.CTkFrame(ctrl, fg_color="transparent")
        btn_frame.pack(fill="x", **padx, pady=10)
        self.start_btn = ctk.CTkButton(btn_frame, text="▶ Iniciar", command=self._start, fg_color="green")
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.stop_btn = ctk.CTkButton(btn_frame, text="⏹ Detener", command=self._stop,
                                       fg_color="gray", state="disabled")
        self.stop_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))

    def _build_modificar_tab(self, tab):
        pad = {"padx": 16, "pady": 6}

        # ── Estado (fijo abajo) ──
        self.mod_status = ctk.CTkTextbox(tab, height=110, state="disabled", font=ctk.CTkFont(family="Courier", size=12))
        self.mod_status.pack(side="bottom", fill="x", padx=16, pady=(0, 8))

        # ── Controles (scroll) ──
        ctrl = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        ctrl.pack(side="top", fill="both", expand=True)

        ctk.CTkLabel(ctrl, text="Modificar cita existente", font=ctk.CTkFont(size=15, weight="bold"), anchor="w").pack(fill="x", **pad)
        ctk.CTkLabel(ctrl, text="Buscá tu cita y agendala en otro horario disponible.", text_color="gray", anchor="w").pack(fill="x", padx=16)

        # ── Tarjeta cita actual ──
        self.mod_card = ctk.CTkFrame(ctrl, fg_color="#1e2a38", corner_radius=10)
        self.mod_card.pack(fill="x", padx=16, pady=(12, 4))

        card_inner = ctk.CTkFrame(self.mod_card, fg_color="transparent")
        card_inner.pack(fill="x", padx=16, pady=12)

        self.mod_card_fecha   = ctk.CTkLabel(card_inner, text="📅  —", anchor="w", font=ctk.CTkFont(size=13))
        self.mod_card_agencia = ctk.CTkLabel(card_inner, text="🏢  —", anchor="w", text_color="gray")
        self.mod_card_placa   = ctk.CTkLabel(card_inner, text="🚗  —", anchor="w", text_color="gray")
        self.mod_card_fecha.pack(fill="x")
        self.mod_card_agencia.pack(fill="x")
        self.mod_card_placa.pack(fill="x")

        ctk.CTkButton(ctrl, text="🔍 Buscar mi cita", command=self._buscar_cita, fg_color="#444").pack(
            fill="x", padx=16, pady=(6, 8))

        ctk.CTkLabel(ctrl, text="Nueva agencia", anchor="w").pack(fill="x", **pad)
        loc_names = sorted(self._locations.keys())
        self.mod_loc_var = ctk.StringVar(value="— Elegí una agencia —")
        ctk.CTkOptionMenu(ctrl, variable=self.mod_loc_var,
                          values=["— Elegí una agencia —"] + loc_names).pack(fill="x", **pad)

        date_frame = ctk.CTkFrame(ctrl, fg_color="transparent")
        date_frame.pack(fill="x", **pad)
        left = ctk.CTkFrame(date_frame, fg_color="transparent")
        left.pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkLabel(left, text="Desde").pack(anchor="w")
        self.mod_start = self._date_picker(left, date.today())
        self.mod_start.pack(fill="x")
        right = ctk.CTkFrame(date_frame, fg_color="transparent")
        right.pack(side="right", expand=True, fill="x", padx=(5, 0))
        ctk.CTkLabel(right, text="Hasta").pack(anchor="w")
        self.mod_end = self._date_picker(right, date.today() + timedelta(days=30))
        self.mod_end.pack(fill="x")

        self.mod_time_enabled, self.mod_time_from, self.mod_time_to = self._build_time_filter(ctrl, pad)
        self.mod_day_enabled, self.mod_day_vars = self._build_day_filter(ctrl, pad)

        # ── Intervalo ──
        ctk.CTkLabel(ctrl, text="Revisar cada (minutos)", anchor="w").pack(fill="x", **pad)
        self.mod_interval_var = ctk.IntVar(value=5)
        mod_interval_frame = ctk.CTkFrame(ctrl, fg_color="transparent")
        mod_interval_frame.pack(fill="x", **pad)
        mod_interval_slider = ctk.CTkSlider(mod_interval_frame, from_=1, to=30,
                                            variable=self.mod_interval_var,
                                            command=lambda v: mod_interval_label.configure(text=f"{int(v)} min"))
        mod_interval_slider.pack(side="left", expand=True, fill="x")
        mod_interval_label = ctk.CTkLabel(mod_interval_frame, text="5 min", width=50)
        mod_interval_label.pack(side="right")

        self.cancel_btn = ctk.CTkButton(ctrl, text="🗑 Cancelar cita",
                                         command=self._cancelar_cita, fg_color="#8b1a1a", state="disabled")
        self.cancel_btn.pack(fill="x", padx=16, pady=(0, 4))

        # ── Auto-modificar ──
        ctk.CTkLabel(ctrl, text="Monitoreo automático", font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x", padx=16, pady=(8, 2))
        ctk.CTkLabel(ctrl, text="Busca un slot disponible y modifica tu cita automáticamente.", text_color="gray", anchor="w").pack(fill="x", padx=16)

        auto_btn_frame = ctk.CTkFrame(ctrl, fg_color="transparent")
        auto_btn_frame.pack(fill="x", padx=16, pady=6)
        self.automod_start_btn = ctk.CTkButton(auto_btn_frame, text="▶ Iniciar búsqueda",
                                                command=self._start_automod, fg_color="green", state="disabled")
        self.automod_start_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.automod_stop_btn = ctk.CTkButton(auto_btn_frame, text="⏹ Detener",
                                               command=self._stop_automod, fg_color="gray", state="disabled")
        self.automod_stop_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))

        self._current_booking: dict | None = None
        self._automod_thread: Thread | None = None
        self._automod_stop  = threading.Event()

    def _set_mod_status(self, text: str):
        self.mod_status.configure(state="normal")
        self.mod_status.delete("1.0", "end")
        self.mod_status.insert("1.0", text)
        self.mod_status.configure(state="disabled")

    def _buscar_cita(self):
        if not self._customer_ready():
            self._set_mod_status("❌ Completá tus datos en «Mis datos» primero.")
            return
        self._set_mod_status("⏳ Buscando tu cita...")

        def run():
            c = self._customer
            b = fetch_booking(c.get("vehicle_rego", ""), c.get("email", ""), c.get("phone", ""))
            self.after(0, lambda: self._on_buscar_result(b))

        Thread(target=run, daemon=True).start()

    def _on_buscar_result(self, b: dict | None):
        if not b:
            self.mod_card_fecha.configure(text="📅  Sin cita activa encontrada.", text_color="gray")
            self.mod_card_agencia.configure(text="🏢  —", text_color="gray")
            self.mod_card_placa.configure(text="🚗  —", text_color="gray")
            self._set_mod_status("Sin cita activa para tus datos.")
            self._current_booking = None
            self.cancel_btn.configure(state="disabled")
            self.automod_start_btn.configure(state="disabled")
            return

        self._current_booking = b
        self.mod_card_fecha.configure(text=f"📅  {format_date(b['startDateTime'])}", text_color="white")
        self.mod_card_agencia.configure(text=f"🏢  {b.get('locationName', '—')}", text_color="#aac4e0")
        self.mod_card_placa.configure(text=f"🚗  Placa {b.get('vehicleRego', '—')}", text_color="#aac4e0")
        self._set_mod_status("Cita encontrada. Elegí la nueva agencia y fechas, y presioná «Iniciar búsqueda».")
        self.cancel_btn.configure(state="normal")
        self.automod_start_btn.configure(state="normal")

    def _start_automod(self):
        if not self._current_booking:
            return
        if not self._locations.get(self.mod_loc_var.get()):
            self._set_mod_status("❌ Elegí una agencia primero.")
            return
        try:
            start_dt = datetime.strptime(self.mod_start.get(), "%Y-%m-%d")
            end_dt   = datetime.strptime(self.mod_end.get(), "%Y-%m-%d")
        except ValueError:
            self._set_mod_status("❌ Fechas inválidas.")
            return

        self.automod_start_btn.configure(state="disabled")
        self.automod_stop_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")

        self._automod_stop.clear()
        self._automod_thread = Thread(target=self._automod_loop,
                                       args=(start_dt, end_dt), daemon=True)
        self._automod_thread.start()

    def _stop_automod(self):
        self._automod_stop.set()
        self.automod_start_btn.configure(state="normal")
        self.automod_stop_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self._set_mod_status("Búsqueda automática detenida.")

    def _automod_loop(self, start_dt: datetime, end_dt: datetime):
        interval = int(self.mod_interval_var.get()) * 60
        new_loc_name = self.mod_loc_var.get()
        new_loc_id   = self._locations.get(new_loc_name, "")
        hr  = self._hour_range(self.mod_time_enabled, self.mod_time_from, self.mod_time_to)
        df  = self._day_filter(self.mod_day_enabled, self.mod_day_vars)

        while not self._automod_stop.is_set():
            self.after(0, lambda: self._set_mod_status(
                f"⏳ Buscando en {new_loc_name}...\n"
                f"Revisando cada {int(self.mod_interval_var.get())} min."
            ))
            days = fetch_available_days(new_loc_id,
                                        start_dt.replace(tzinfo=timezone.utc),
                                        end_dt.replace(tzinfo=timezone.utc))
            if days is None:
                self.after(0, lambda: self._set_mod_status(
                    f"⚠️ Sin conexión — reintentando en {int(self.mod_interval_var.get())} min."
                ))
                self._automod_stop.wait(timeout=int(self.mod_interval_var.get()) * 60)
                continue
            if days:
                for day in _filter_days_by_weekday(days, df):
                    if self._automod_stop.is_set():
                        return
                    slots = fetch_time_slots(new_loc_id, day)
                    if hr:
                        slots = self._filter_slots_by_hour(slots, hr[0], hr[1])
                    if not slots:
                        continue
                    for s in slots[:3]:
                        all_slots = fetch_time_slots(new_loc_id, day, selected_slot=s)
                        selected  = next((x for x in all_slots if x.get("isFirstSelected")), s)
                        confirm_timeslot(new_loc_id, selected)

                        b          = self._current_booking
                        old_loc_id = b.get("locationId", b.get("locationid", b.get("locationID", new_loc_id)))
                        old_slot   = {
                            "time":            b["startDateTime"],
                            "resourceIds":     b.get("resourceIds", []),
                            "locationId":      old_loc_id,
                            "productDuration": 5,
                            "productId":       PRODUCT_ID,
                            "productIndex":    0,
                            "productName":     b.get("productName", "AUTOMÓVIL"),
                        }
                        release_timeslot(old_loc_id, old_slot)
                        delete_booking(b["id"])

                        result = create_booking(new_loc_id, selected, all_slots, self._customer)
                        if result and result.get("isSuccess"):
                            items = result.get("bookingResultItems", [])
                            num   = items[0].get("reservationNumber", "?") if items else "?"
                            self.after(0, lambda n=num, sl=selected, loc=new_loc_name: self._on_automod_success(n, sl, loc))
                            return
            self._automod_stop.wait(timeout=interval)

    def _on_automod_success(self, num: str, selected: dict, loc_name: str):
        self._automod_stop.set()
        self._current_booking = None
        self.automod_start_btn.configure(state="disabled")
        self.automod_stop_btn.configure(state="disabled")
        self.cancel_btn.configure(state="disabled")
        self.mod_card_fecha.configure(text=f"📅  {format_date(selected['time'])}", text_color="lightgreen")
        self.mod_card_agencia.configure(text=f"🏢  {loc_name}", text_color="#aac4e0")
        self.mod_card_placa.configure(text=f"🚗  Número: {num}", text_color="#aac4e0")
        self._set_mod_status(
            f"✅ ¡CITA MODIFICADA!\n"
            f"{'─'*30}\n"
            f"Número:  {num}\n"
            f"Fecha:   {format_date(selected['time'])}\n"
            f"Agencia: {loc_name}\n"
            f"{'─'*30}\n"
            f"Revisá tu correo."
        )
        import monitor as _mon
        _mon.trigger_booked_alert(loc_name, selected["time"], num, 1)

    def _cancelar_cita(self):
        if not self._current_booking:
            return
        from tkinter import messagebox
        b = self._current_booking
        fecha = format_date(b.get("startDateTime", ""))
        if not messagebox.askyesno(
            "Confirmar cancelación",
            f"¿Seguro que querés cancelar esta cita?\n\n{fecha}\n{b.get('locationName', '')}",
            icon="warning"
        ):
            return
        self.cancel_btn.configure(state="disabled", text="Cancelando...")
        self._set_mod_status("⏳ Cancelando cita...")

        def run():
            book_id    = b["id"]
            loc_id     = b.get("locationId", b.get("locationid", b.get("locationID", "")))
            old_slot   = {
                "time":            b["startDateTime"],
                "resourceIds":     b.get("resourceIds", []),
                "locationId":      loc_id,
                "productDuration": 5,
                "productId":       PRODUCT_ID,
                "productIndex":    0,
                "productName":     b.get("productName", "AUTOMÓVIL"),
            }
            release_timeslot(loc_id, old_slot)
            ok = delete_booking(book_id)
            self.after(0, lambda: self._on_cancelled(ok))

        Thread(target=run, daemon=True).start()

    def _on_cancelled(self, ok: bool):
        if ok:
            self._current_booking = None
            self.mod_card_fecha.configure(text="📅  —", text_color="gray")
            self.mod_card_agencia.configure(text="🏢  —", text_color="gray")
            self.mod_card_placa.configure(text="🚗  —", text_color="gray")
            self._set_mod_status("✅ Cita cancelada. Revisá tu correo para la confirmación.")
        else:
            self._set_mod_status("❌ No se pudo cancelar. Intentalo de nuevo o hacelo desde la web de DEKRA.")
        self.cancel_btn.configure(state="disabled" if ok else "normal", text="🗑 Cancelar cita")

    def _modificar_cita(self):
        if not self._current_booking:
            return
        if not self._customer_ready():
            self._set_mod_status("❌ Completá tus datos en «Mis datos» primero.")
            return

        try:
            start_dt = datetime.strptime(self.mod_start.get(), "%Y-%m-%d")
            end_dt   = datetime.strptime(self.mod_end.get(), "%Y-%m-%d")
        except ValueError:
            self._set_mod_status("❌ Fechas inválidas. Formato: YYYY-MM-DD")
            return

        self._set_mod_status("⏳ Verificando que se puede modificar...")

        def run():
            b        = self._current_booking
            book_id  = b["id"]
            loc_id   = b.get("locationId") or b.get("locationid") or b.get("locationID", "")

            # Intentar obtener locationId del booking si no está directo
            if not loc_id:
                # buscarlo en el campo de la agencia seleccionada
                loc_name = self.mod_loc_var.get()
                loc_id   = self._locations.get(loc_name, "")

            if not check_update_allowed(book_id):
                self._set_mod_status("❌ Esta cita no se puede modificar (muy cerca de la fecha o ya expiró).")
                return

            new_loc_name = self.mod_loc_var.get()
            new_loc_id   = self._locations.get(new_loc_name, "")

            self._set_mod_status("⏳ Buscando slots disponibles en nueva agencia...")
            days = fetch_available_days(new_loc_id, start_dt.replace(tzinfo=timezone.utc), end_dt.replace(tzinfo=timezone.utc))
            if days is None:
                self._set_mod_status("⚠️ Sin conexión. Verificá tu internet e intentá de nuevo.")
                return
            if not days:
                self._set_mod_status(f"❌ Sin disponibilidad en {new_loc_name} para ese rango.")
                return

            hr     = self._hour_range(self.mod_time_enabled, self.mod_time_from, self.mod_time_to)
            result = None
            selected = None
            for day in days:
                slots = fetch_time_slots(new_loc_id, day)
                if hr:
                    slots = self._filter_slots_by_hour(slots, hr[0], hr[1])
                if not slots:
                    continue
                for s in slots[:3]:
                    all_slots = fetch_time_slots(new_loc_id, day, selected_slot=s)
                    selected  = next((x for x in all_slots if x.get("isFirstSelected")), s)
                    confirm_timeslot(new_loc_id, selected)

                    # Cancelar cita anterior justo antes de crear la nueva
                    old_loc_id = b.get("locationId", b.get("locationid", b.get("locationID", new_loc_id)))
                    old_slot   = {
                        "time":            b["startDateTime"],
                        "resourceIds":     b.get("resourceIds", []),
                        "locationId":      old_loc_id,
                        "productDuration": 5,
                        "productId":       PRODUCT_ID,
                        "productIndex":    0,
                        "productName":     b.get("productName", "AUTOMÓVIL"),
                    }
                    release_timeslot(old_loc_id, old_slot)
                    delete_booking(book_id)

                    result = create_booking(new_loc_id, selected, all_slots, self._customer)
                    if result and result.get("isSuccess"):
                        break
                    else:
                        # Si falla el nuevo booking, informar — la cita vieja ya fue cancelada
                        self._set_mod_status("⚠️ La cita anterior fue cancelada pero el nuevo booking falló.\nIntentá agendar manualmente en la web de DEKRA.")
                        return
                if result and result.get("isSuccess"):
                    break

            if result and result.get("isSuccess"):
                items = result.get("bookingResultItems", [])
                num   = items[0].get("reservationNumber", "?") if items else "?"
                self._current_booking = None
                self.mod_card_fecha.configure(text="📅  Cita modificada exitosamente.", text_color="lightgreen")
                self.mod_card_agencia.configure(text="", text_color="gray")
                self.mod_card_placa.configure(text="", text_color="gray")
                self._set_mod_status(
                    f"✅ ¡CITA MODIFICADA!\n"
                    f"{'─'*35}\n"
                    f"Número:  {num}\n"
                    f"Fecha:   {format_date(selected['time'])}\n"
                    f"Agencia: {new_loc_name}\n"
                    f"{'─'*35}\n"
                    f"Revisá tu correo."
                )
            else:
                self._set_mod_status(f"❌ No se pudo modificar.\nRespuesta: {result}")

        Thread(target=run, daemon=True).start()

    def _build_datos_tab(self, tab):
        pad = {"padx": 16, "pady": 6}
        c   = self._customer

        ctk.CTkLabel(tab, text="Tus datos personales", font=ctk.CTkFont(size=15, weight="bold"), anchor="w").pack(fill="x", **pad)
        ctk.CTkLabel(tab, text="Se guardan en tu computadora. Nunca se comparten.", text_color="gray", anchor="w").pack(fill="x", padx=16)

        fields = [
            ("Nombre",              "first_name",   c.get("first_name",   "")),
            ("Apellidos",           "last_name",    c.get("last_name",    "")),
            ("Correo electrónico",  "email",        c.get("email",        "")),
            ("Teléfono",            "phone",        c.get("phone",        "")),
            ("Número de placa",     "vehicle_rego", c.get("vehicle_rego", "")),
        ]

        self._field_entries: dict[str, ctk.CTkEntry] = {}
        for label, key, value in fields:
            ctk.CTkLabel(tab, text=label, anchor="w").pack(fill="x", **pad)
            entry = ctk.CTkEntry(tab)
            entry.insert(0, value)
            entry.pack(fill="x", **pad)
            self._field_entries[key] = entry

        ctk.CTkButton(tab, text="💾 Guardar datos", command=self._save_customer, fg_color="green").pack(
            fill="x", padx=16, pady=12)
        self.save_status = ctk.CTkLabel(tab, text="")
        self.save_status.pack()

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _hour_range(self, enabled_var, from_var, to_var) -> tuple[int, int] | None:
        if not enabled_var.get():
            return None
        return int(from_var.get().split(":")[0]), int(to_var.get().split(":")[0])

    def _customer_summary(self) -> str:
        c = self._customer
        name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
        rego = c.get("vehicle_rego", "")
        if not name and not rego:
            return "  ⚠ Completá tus datos en la pestaña «Mis datos»"
        return f"  {name} · Placa {rego}"

    def _customer_ready(self) -> bool:
        return bool(self._customer.get("email") and self._customer.get("vehicle_rego"))

    # ─── Acciones ─────────────────────────────────────────────────────────────

    def _save_customer(self):
        data = {key: entry.get().strip() for key, entry in self._field_entries.items()}
        data["country_code"] = "+506"
        if not data.get("email") or not data.get("vehicle_rego"):
            self.save_status.configure(text="❌ Correo y placa son obligatorios.", text_color="red")
            return
        self._customer = data
        save_customer(data)
        self.customer_label.configure(text=self._customer_summary())
        self.save_status.configure(text="✅ Datos guardados.", text_color="lightgreen")

    def _toggle_loc_dropdown(self):
        if self._loc_dropdown_open:
            self._loc_dropdown_frame.pack_forget()
            self._loc_dropdown_open = False
        else:
            self._loc_dropdown_frame.pack(fill="x", padx=16, pady=(0, 4),
                                          after=self._loc_dropdown_btn)
            self._loc_dropdown_open = True

    def _update_loc_btn_text(self):
        selected = [n for n, v in self._loc_check_vars.items() if v.get()]
        if not selected:
            self._loc_dropdown_btn.configure(text="Ninguna seleccionada")
        elif len(selected) == 1:
            self._loc_dropdown_btn.configure(text=selected[0])
        else:
            self._loc_dropdown_btn.configure(text=f"{len(selected)} agencias seleccionadas")

    def _start(self):
        if self.autobook_var.get() and not self._customer_ready():
            self._set_results("❌ Completá tus datos en la pestaña «Mis datos» antes de activar el auto-agendado.")
            self._tabs.set("Mis datos")
            return

        try:
            start_dt = datetime.strptime(self.start_entry.get(), "%Y-%m-%d")
            end_dt   = datetime.strptime(self.end_entry.get(),   "%Y-%m-%d")
        except ValueError:
            self._set_results("❌ Fechas inválidas. Formato: YYYY-MM-DD")
            return

        selected_locs = [(self._locations[n], n) for n, v in self._loc_check_vars.items() if v.get()]
        if not selected_locs:
            self._set_results("❌ Seleccioná al menos una agencia.")
            return

        monitor.configure(
            locations         = selected_locs,
            start_date        = start_dt.replace(tzinfo=timezone.utc),
            end_date          = end_dt.replace(tzinfo=timezone.utc),
            interval_min      = int(self.mod_interval_var.get()),
            sound_enabled     = self.sound_var.get(),
            sound_times       = 1,
            auto_book_enabled = self.autobook_var.get(),
            customer          = self._customer,
            hour_range        = self._hour_range(self.time_enabled, self.time_from, self.time_to),
            day_filter        = self._day_filter(self.day_enabled, self.day_vars),
        )
        monitor.start()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._loc_dropdown_btn.configure(state="disabled")

    def _stop(self):
        monitor.stop()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._loc_dropdown_btn.configure(state="normal")
        self.status_label.configure(text="Monitor detenido.", text_color="gray")

    def _test_booking(self):
        if not self._customer_ready():
            self._set_results("❌ Completá tus datos en la pestaña «Mis datos» primero.")
            self._tabs.set("Mis datos")
            return

        self.test_btn.configure(state="disabled", text="Probando...")
        self._set_results("⏳ Buscando slots disponibles...")

        def run():
            loc_name = self.loc_var.get()
            loc_id   = self._locations.get(loc_name)
            try:
                start_dt = datetime.strptime(self.start_entry.get(), "%Y-%m-%d")
                end_dt   = datetime.strptime(self.end_entry.get(), "%Y-%m-%d")
            except ValueError:
                self._set_results("❌ Fechas inválidas.")
                self.test_btn.configure(state="normal", text="🧪 Probar booking ahora")
                return

            days = fetch_available_days(loc_id, start_dt.replace(tzinfo=timezone.utc), end_dt.replace(tzinfo=timezone.utc))
            if not days:
                self._set_results(f"❌ Sin días disponibles en {loc_name} para ese rango.")
                self.test_btn.configure(state="normal", text="🧪 Probar booking ahora")
                return

            hr     = self._hour_range(self.time_enabled, self.time_from, self.time_to)
            result = None
            selected = None
            for day in days:
                self._set_results(f"✅ Día: {day}\n⏳ Buscando slots...")
                slots = fetch_time_slots(loc_id, day)
                if hr:
                    slots = self._filter_slots_by_hour(slots, hr[0], hr[1])
                if not slots:
                    continue
                for s in slots[:3]:
                    self._set_results(f"✅ Día: {day}\n⏳ Probando slot {s['time']}...")
                    all_slots = fetch_time_slots(loc_id, day, selected_slot=s)
                    selected  = next((x for x in all_slots if x.get("isFirstSelected")), s)
                    confirm_timeslot(loc_id, selected)
                    result = create_booking(loc_id, selected, all_slots, self._customer)
                    if result and result.get("isSuccess"):
                        break
                if result and result.get("isSuccess"):
                    break

            if result and result.get("isSuccess"):
                items = result.get("bookingResultItems", [])
                num   = items[0].get("reservationNumber", "?") if items else "?"
                bid   = items[0].get("bookingId", "?") if items else "?"
                rego  = self._customer.get("vehicle_rego", "—")
                self._set_results(
                    f"✅ ¡RESERVA EXITOSA!\n"
                    f"{'─'*35}\n"
                    f"Número:    {num}\n"
                    f"bookingId: {bid}\n"
                    f"Slot:      {selected['time'] if selected else '?'}\n"
                    f"Agencia:   {loc_name}\n"
                    f"Placa:     {rego}\n"
                    f"{'─'*35}\n"
                    f"Revisá tu correo."
                )
            else:
                self._set_results(f"❌ La reserva falló.\nRespuesta: {result}")

            self.test_btn.configure(state="normal", text="🧪 Probar booking ahora")

        Thread(target=run, daemon=True).start()

    # ─── Refresh ──────────────────────────────────────────────────────────────

    def _refresh(self):
        if monitor.running:
            mode = "🤖 Auto-agendando" if monitor.auto_book_enabled else "👁 Monitoreando"
            last = monitor.last_check.strftime("%H:%M:%S") if monitor.last_check else "..."
            if monitor.connection_error:
                self.status_label.configure(
                    text=f"⚠️ Sin conexión · reintentando en {monitor.interval_min} min.",
                    text_color="orange"
                )
            else:
                self.status_label.configure(
                    text=f"{mode} {monitor.location_name} · última revisión: {last}",
                    text_color="lightgreen"
                )

            if monitor.booking_result:
                r    = monitor.booking_result
                rego = self._customer.get("vehicle_rego", "—")
                loc  = next((n for _, n in monitor.locations if _ == r.get("slot", {}).get("locationId", "")),
                            monitor.location_name)
                texto = (
                    f"✅ ¡CITA AGENDADA!\n"
                    f"{'─'*40}\n"
                    f"Número:  {r['reservationNumber']}\n"
                    f"Fecha:   {format_date(r['slot']['time'])}\n"
                    f"Agencia: {loc}\n"
                    f"Placa:   {rego}\n"
                    f"ID:      {r['bookingId']}\n"
                    f"{'─'*40}\n"
                    f"Revisá tu correo para la confirmación."
                )
                self._set_results(texto)
                self._stop()
            elif monitor.available_days:
                lines = []
                if monitor.new_days:
                    lines.append("🆕 NUEVAS APERTURAS:")
                    for loc_name, days in monitor.new_days.items():
                        for d in days:
                            lines.append(f"  ★ {loc_name} · {format_date(d)}")
                    lines.append("")
                total = sum(len(v) for v in monitor.available_days.values())
                lines.append(f"📅 {total} día(s) disponibles:")
                for loc_name, days in monitor.available_days.items():
                    lines.append(f"  🏢 {loc_name}")
                    for d in days:
                        lines.append(f"    · {format_date(d)}")
                self._set_results("\n".join(lines))
            elif monitor.last_check:
                self._set_results(f"Sin disponibilidad para el rango seleccionado.\nÚltima revisión: {monitor.last_check.strftime('%d/%m/%Y %H:%M:%S')}")

        self.after(10000, self._refresh)


    def _set_results(self, text: str):
        self.results_box.configure(state="normal")
        self.results_box.delete("1.0", "end")
        self.results_box.insert("1.0", text)
        self.results_box.configure(state="disabled")


class DatePicker(ctk.CTkFrame):
    """Selector de fecha con tres dropdowns: día / mes / año."""

    MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]

    def __init__(self, parent, initial: date):
        super().__init__(parent, fg_color="transparent")
        self._day_var   = ctk.StringVar(value=str(initial.day))
        self._month_var = ctk.StringVar(value=self.MESES[initial.month - 1])
        self._year_var  = ctk.StringVar(value=str(initial.year))

        years = [str(y) for y in range(date.today().year, date.today().year + 3)]
        days  = [str(d) for d in range(1, 32)]

        ctk.CTkOptionMenu(self, variable=self._day_var,   values=days,          width=58).pack(side="left", padx=(0, 2))
        ctk.CTkOptionMenu(self, variable=self._month_var, values=self.MESES,    width=72).pack(side="left", padx=2)
        ctk.CTkOptionMenu(self, variable=self._year_var,  values=years,         width=76).pack(side="left", padx=(2, 0))

    def get(self) -> str:
        try:
            m = self.MESES.index(self._month_var.get()) + 1
            d = int(self._day_var.get())
            y = int(self._year_var.get())
            return date(y, m, d).strftime("%Y-%m-%d")
        except (ValueError, IndexError):
            return date.today().strftime("%Y-%m-%d")




if __name__ == "__main__":
    app = App()
    app.mainloop()
