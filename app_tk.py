import customtkinter as ctk
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo
from threading import Thread
from pathlib import Path
import json

from api import (fetch_locations, fetch_available_days, fetch_time_slots,
                 confirm_timeslot, create_booking, release_timeslot,
                 fetch_booking, check_update_allowed, delete_booking)
from config import PRODUCT_ID
from monitor import monitor, format_date

TZ_CR = ZoneInfo("America/Costa_Rica")
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
        self.resizable(False, False)

        self._locations: dict[str, str] = {}
        self._customer = load_customer()
        self._load_locations()
        self._build_ui()
        self._refresh()

        if not self._customer.get("email"):
            self._tabs.set("Mis datos")

    # ─── Cargar agencias ──────────────────────────────────────────────────────

    def _load_locations(self):
        locs = fetch_locations()
        self._locations = {loc["locationName"].strip(): loc["locationId"] for loc in locs}

    # ─── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        ctk.CTkLabel(self, text="🚗 Cita DEKRA", font=ctk.CTkFont(size=22, weight="bold")).pack(padx=20, pady=(20, 4))
        ctk.CTkLabel(self, text="Monitor automático de disponibilidad", text_color="gray").pack(pady=(0, 10))

        self._tabs = ctk.CTkTabview(self)
        self._tabs.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self._tabs.add("Monitor")
        self._tabs.add("Modificar cita")
        self._tabs.add("Mis datos")

        self._build_monitor_tab(self._tabs.tab("Monitor"))
        self._build_modificar_tab(self._tabs.tab("Modificar cita"))
        self._build_datos_tab(self._tabs.tab("Mis datos"))

    def _build_monitor_tab(self, tab):
        pad  = {"padx": 16, "pady": 6}
        padx = {"padx": 16}

        # ── Agencia ──
        ctk.CTkLabel(tab, text="Agencia", anchor="w").pack(fill="x", **pad)
        self.loc_var = ctk.StringVar(value=sorted(self._locations.keys())[0] if self._locations else "")
        self.loc_menu = ctk.CTkOptionMenu(tab, variable=self.loc_var, values=sorted(self._locations.keys()))
        self.loc_menu.pack(fill="x", **pad)

        # ── Fechas ──
        date_frame = ctk.CTkFrame(tab, fg_color="transparent")
        date_frame.pack(fill="x", **pad)
        left = ctk.CTkFrame(date_frame, fg_color="transparent")
        left.pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkLabel(left, text="Desde").pack(anchor="w")
        self.start_entry = ctk.CTkEntry(left, placeholder_text="YYYY-MM-DD")
        self.start_entry.insert(0, date.today().strftime("%Y-%m-%d"))
        self.start_entry.pack(fill="x")
        right = ctk.CTkFrame(date_frame, fg_color="transparent")
        right.pack(side="right", expand=True, fill="x", padx=(5, 0))
        ctk.CTkLabel(right, text="Hasta").pack(anchor="w")
        self.end_entry = ctk.CTkEntry(right, placeholder_text="YYYY-MM-DD")
        self.end_entry.insert(0, (date.today() + timedelta(days=30)).strftime("%Y-%m-%d"))
        self.end_entry.pack(fill="x")

        # ── Intervalo ──
        ctk.CTkLabel(tab, text="Revisar cada (minutos)", anchor="w").pack(fill="x", **pad)
        self.interval_var = ctk.IntVar(value=5)
        interval_frame = ctk.CTkFrame(tab, fg_color="transparent")
        interval_frame.pack(fill="x", **pad)
        self.interval_slider = ctk.CTkSlider(interval_frame, from_=1, to=30, variable=self.interval_var,
                                              command=lambda v: self.interval_label.configure(text=f"{int(v)} min"))
        self.interval_slider.pack(side="left", expand=True, fill="x")
        self.interval_label = ctk.CTkLabel(interval_frame, text="5 min", width=50)
        self.interval_label.pack(side="right")

        # ── Sonido ──
        sound_frame = ctk.CTkFrame(tab, fg_color="transparent")
        sound_frame.pack(fill="x", **pad)
        self.sound_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(sound_frame, text="🔊 Sonido al encontrar cita", variable=self.sound_var).pack(side="left")

        # ── Auto-booking ──
        self.autobook_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(tab, text="🤖 Auto-agendar cuando encuentre cita",
                      variable=self.autobook_var).pack(fill="x", **pad)
        self.customer_label = ctk.CTkLabel(tab, text=self._customer_summary(), text_color="gray", anchor="w")
        self.customer_label.pack(fill="x", padx=16)

        # ── Botones ──
        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.pack(fill="x", **padx, pady=12)
        self.start_btn = ctk.CTkButton(btn_frame, text="▶ Iniciar", command=self._start, fg_color="green")
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.stop_btn = ctk.CTkButton(btn_frame, text="⏹ Detener", command=self._stop,
                                       fg_color="gray", state="disabled")
        self.stop_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))

        self.test_btn = ctk.CTkButton(tab, text="🧪 Probar booking ahora", command=self._test_booking,
                                       fg_color="#555")
        self.test_btn.pack(fill="x", **padx, pady=(0, 4))

        # ── Estado ──
        self.status_label = ctk.CTkLabel(tab, text="Monitor detenido.", text_color="gray")
        self.status_label.pack(**pad)

        # ── Resultados ──
        ctk.CTkLabel(tab, text="📅 Resultados", font=ctk.CTkFont(size=14, weight="bold"), anchor="w").pack(fill="x", **pad)
        self.results_box = ctk.CTkTextbox(tab, height=200, state="disabled", font=ctk.CTkFont(family="Courier", size=12))
        self.results_box.pack(fill="both", expand=True, **pad)

    def _build_modificar_tab(self, tab):
        pad = {"padx": 16, "pady": 6}

        ctk.CTkLabel(tab, text="Modificar cita existente", font=ctk.CTkFont(size=15, weight="bold"), anchor="w").pack(fill="x", **pad)
        ctk.CTkLabel(tab, text="Buscá tu cita y agendala en otro horario disponible.", text_color="gray", anchor="w").pack(fill="x", padx=16)

        # Cita actual
        ctk.CTkLabel(tab, text="Cita actual", font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x", padx=16, pady=(16, 2))
        self.mod_current = ctk.CTkLabel(tab, text="Presioná «Buscar» para cargar tu cita.", text_color="gray", anchor="w", wraplength=600)
        self.mod_current.pack(fill="x", padx=16)

        ctk.CTkButton(tab, text="🔍 Buscar mi cita", command=self._buscar_cita, fg_color="#444").pack(
            fill="x", padx=16, pady=8)

        ctk.CTkLabel(tab, text="Nueva agencia", anchor="w").pack(fill="x", **pad)
        self.mod_loc_var = ctk.StringVar(value=sorted(self._locations.keys())[0] if self._locations else "")
        ctk.CTkOptionMenu(tab, variable=self.mod_loc_var, values=sorted(self._locations.keys())).pack(fill="x", **pad)

        date_frame = ctk.CTkFrame(tab, fg_color="transparent")
        date_frame.pack(fill="x", **pad)
        left = ctk.CTkFrame(date_frame, fg_color="transparent")
        left.pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkLabel(left, text="Desde").pack(anchor="w")
        self.mod_start = ctk.CTkEntry(left, placeholder_text="YYYY-MM-DD")
        self.mod_start.insert(0, date.today().strftime("%Y-%m-%d"))
        self.mod_start.pack(fill="x")
        right = ctk.CTkFrame(date_frame, fg_color="transparent")
        right.pack(side="right", expand=True, fill="x", padx=(5, 0))
        ctk.CTkLabel(right, text="Hasta").pack(anchor="w")
        self.mod_end = ctk.CTkEntry(right, placeholder_text="YYYY-MM-DD")
        self.mod_end.insert(0, (date.today() + timedelta(days=30)).strftime("%Y-%m-%d"))
        self.mod_end.pack(fill="x")

        self.mod_btn = ctk.CTkButton(tab, text="🔄 Modificar a primer slot disponible",
                                      command=self._modificar_cita, fg_color="#1a6aa0", state="disabled")
        self.mod_btn.pack(fill="x", padx=16, pady=10)

        self.mod_status = ctk.CTkTextbox(tab, height=140, state="disabled", font=ctk.CTkFont(family="Courier", size=12))
        self.mod_status.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self._current_booking: dict | None = None

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
            if not b:
                self.mod_current.configure(text="No se encontró ninguna cita activa para tus datos.", text_color="gray")
                self._set_mod_status("Sin cita activa.")
                self._current_booking = None
                self.mod_btn.configure(state="disabled")
                return

            self._current_booking = b
            slot_cr = format_date(b["startDateTime"])
            self.mod_current.configure(
                text=f"📅 {slot_cr}  |  {b.get('locationName', '—')}  |  Placa {b.get('vehicleRego', '—')}",
                text_color="white"
            )
            self._set_mod_status(f"Cita encontrada. ID: {b.get('id', '?')}\nPresioná «Modificar» para cambiarla.")
            self.mod_btn.configure(state="normal")

        Thread(target=run, daemon=True).start()

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

        self.mod_btn.configure(state="disabled", text="Modificando...")
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
                self.mod_btn.configure(state="normal", text="🔄 Modificar a primer slot disponible")
                return

            new_loc_name = self.mod_loc_var.get()
            new_loc_id   = self._locations.get(new_loc_name, "")

            self._set_mod_status("⏳ Buscando slots disponibles en nueva agencia...")
            days = fetch_available_days(new_loc_id, start_dt.replace(tzinfo=timezone.utc), end_dt.replace(tzinfo=timezone.utc))
            if not days:
                self._set_mod_status(f"❌ Sin disponibilidad en {new_loc_name} para ese rango.")
                self.mod_btn.configure(state="normal", text="🔄 Modificar a primer slot disponible")
                return

            result   = None
            selected = None
            for day in days:
                slots = fetch_time_slots(new_loc_id, day)
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
                        self.mod_btn.configure(state="normal", text="🔄 Modificar a primer slot disponible")
                        return
                if result and result.get("isSuccess"):
                    break

            if result and result.get("isSuccess"):
                items = result.get("bookingResultItems", [])
                num   = items[0].get("reservationNumber", "?") if items else "?"
                self._current_booking = None
                self.mod_btn.configure(state="disabled", text="🔄 Modificar a primer slot disponible")
                self.mod_current.configure(text="Cita modificada exitosamente.", text_color="lightgreen")
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
                self.mod_btn.configure(state="normal", text="🔄 Modificar a primer slot disponible")

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

        loc_name = self.loc_var.get()
        loc_id   = self._locations.get(loc_name)
        if not loc_id:
            self._set_results("❌ Agencia no válida.")
            return

        monitor.configure(
            location_id       = loc_id,
            location_name     = loc_name,
            start_date        = start_dt.replace(tzinfo=timezone.utc),
            end_date          = end_dt.replace(tzinfo=timezone.utc),
            interval_min      = int(self.interval_var.get()),
            sound_enabled     = self.sound_var.get(),
            sound_times       = 1,
            auto_book_enabled = self.autobook_var.get(),
            customer          = self._customer,
        )
        monitor.start()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.loc_menu.configure(state="disabled")

    def _stop(self):
        monitor.stop()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.loc_menu.configure(state="normal")
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

            result   = None
            selected = None
            for day in days:
                self._set_results(f"✅ Día: {day}\n⏳ Buscando slots...")
                slots = fetch_time_slots(loc_id, day)
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
            self.status_label.configure(
                text=f"{mode} {monitor.location_name} · última revisión: {last}",
                text_color="lightgreen"
            )

            if monitor.booking_result:
                r    = monitor.booking_result
                rego = self._customer.get("vehicle_rego", "—")
                texto = (
                    f"✅ ¡CITA AGENDADA!\n"
                    f"{'─'*40}\n"
                    f"Número:  {r['reservationNumber']}\n"
                    f"Fecha:   {format_date(r['slot']['time'])}\n"
                    f"Agencia: {monitor.location_name}\n"
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
                    for d in monitor.new_days:
                        lines.append(f"  ★ {format_date(d)}")
                    lines.append("")
                lines.append(f"📅 {len(monitor.available_days)} día(s) disponibles en {monitor.location_name}:")
                for d in monitor.available_days:
                    lines.append(f"  · {format_date(d)}")
                self._set_results("\n".join(lines))
            elif monitor.last_check:
                self._set_results(f"Sin disponibilidad para el rango seleccionado.\nÚltima revisión: {monitor.last_check.strftime('%d/%m/%Y %H:%M:%S')}")

        self.after(10000, self._refresh)

    def _set_results(self, text: str):
        self.results_box.configure(state="normal")
        self.results_box.delete("1.0", "end")
        self.results_box.insert("1.0", text)
        self.results_box.configure(state="disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()
