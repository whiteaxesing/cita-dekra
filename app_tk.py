import customtkinter as ctk
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo
from threading import Thread

from api import fetch_locations
from monitor import monitor, format_date
import customer

TZ_CR = ZoneInfo("America/Costa_Rica")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("🚗 Cita DEKRA")
        self.geometry("700x780")
        self.resizable(False, False)

        self._locations: dict[str, str] = {}
        self._load_locations()
        self._build_ui()
        self._refresh()

    # ─── Cargar agencias ──────────────────────────────────────────────────────

    def _load_locations(self):
        locs = fetch_locations()
        self._locations = {loc["locationName"].strip(): loc["locationId"] for loc in locs}

    # ─── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 20, "pady": 6}
        padx = {"padx": 20}

        # Título
        ctk.CTkLabel(self, text="🚗 Cita DEKRA", font=ctk.CTkFont(size=22, weight="bold")).pack(padx=20, pady=(20, 4))
        ctk.CTkLabel(self, text="Monitor automático de disponibilidad", text_color="gray").pack(pady=(0, 10))

        # ── Agencia ──
        ctk.CTkLabel(self, text="Agencia", anchor="w").pack(fill="x", **pad)
        self.loc_var = ctk.StringVar(value=sorted(self._locations.keys())[0] if self._locations else "")
        self.loc_menu = ctk.CTkOptionMenu(self, variable=self.loc_var, values=sorted(self._locations.keys()))
        self.loc_menu.pack(fill="x", **pad)

        # ── Fechas ──
        date_frame = ctk.CTkFrame(self, fg_color="transparent")
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
        ctk.CTkLabel(self, text="Revisar cada (minutos)", anchor="w").pack(fill="x", **pad)
        self.interval_var = ctk.IntVar(value=5)
        interval_frame = ctk.CTkFrame(self, fg_color="transparent")
        interval_frame.pack(fill="x", **pad)
        self.interval_slider = ctk.CTkSlider(interval_frame, from_=1, to=30, variable=self.interval_var,
                                              command=lambda v: self.interval_label.configure(text=f"{int(v)} min"))
        self.interval_slider.pack(side="left", expand=True, fill="x")
        self.interval_label = ctk.CTkLabel(interval_frame, text="5 min", width=50)
        self.interval_label.pack(side="right")

        # ── Sonido ──
        sound_frame = ctk.CTkFrame(self, fg_color="transparent")
        sound_frame.pack(fill="x", **pad)
        self.sound_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(sound_frame, text="🔊 Sonido al encontrar cita", variable=self.sound_var).pack(side="left")


        # ── Auto-booking ──
        self.autobook_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(self, text="🤖 Auto-agendar cuando encuentre cita",
                      variable=self.autobook_var).pack(fill="x", **pad)
        ctk.CTkLabel(self,
                     text=f"  {customer.FIRST_NAME} {customer.LAST_NAME} · Placa {customer.VEHICLE_REGO}",
                     text_color="gray", anchor="w").pack(fill="x", padx=20)

        # ── Botones ──
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", **padx, pady=12)
        self.start_btn = ctk.CTkButton(btn_frame, text="▶ Iniciar", command=self._start, fg_color="green")
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.stop_btn = ctk.CTkButton(btn_frame, text="⏹ Detener", command=self._stop,
                                       fg_color="gray", state="disabled")
        self.stop_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))

        self.test_btn = ctk.CTkButton(self, text="🧪 Probar booking ahora", command=self._test_booking,
                                       fg_color="#555")
        self.test_btn.pack(fill="x", **padx, pady=(0, 4))

        # ── Estado ──
        self.status_label = ctk.CTkLabel(self, text="Monitor detenido.", text_color="gray")
        self.status_label.pack(**pad)

        # ── Resultados ──
        ctk.CTkLabel(self, text="📅 Resultados", font=ctk.CTkFont(size=14, weight="bold"), anchor="w").pack(fill="x", **pad)
        self.results_box = ctk.CTkTextbox(self, height=280, state="disabled", font=ctk.CTkFont(family="Courier", size=12))
        self.results_box.pack(fill="both", expand=True, **pad)

    # ─── Acciones ─────────────────────────────────────────────────────────────

    def _start(self):
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
        from api import fetch_time_slots, create_booking
        from monitor import CUSTOMER

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

            from api import fetch_available_days
            days = fetch_available_days(loc_id, start_dt.replace(tzinfo=timezone.utc), end_dt.replace(tzinfo=timezone.utc))
            if not days:
                self._set_results(f"❌ Sin días disponibles en {loc_name} para ese rango.")
                self.test_btn.configure(state="normal", text="🧪 Probar booking ahora")
                return

            result = None
            slot   = None
            for day in days:
                self._set_results(f"✅ Día: {day}\n⏳ Buscando slots...")
                slots = fetch_time_slots(loc_id, day)
                if not slots:
                    continue
                for s in slots[:3]:
                    self._set_results(f"✅ Día: {day}\n⏳ Probando slot {s['time']}...")
                    all_slots = fetch_time_slots(loc_id, day, selected_slot=s)
                    selected  = next((x for x in all_slots if x.get("isFirstSelected")), s)
                    from api import confirm_timeslot
                    confirm_timeslot(loc_id, selected)
                    result = create_booking(loc_id, selected, all_slots, CUSTOMER)
                    if result and result.get("isSuccess"):
                        slot = selected
                        break
                if result and result.get("isSuccess"):
                    break

            if result and result.get("isSuccess"):
                items = result.get("bookingResultItems", [])
                num   = items[0].get("reservationNumber", "?") if items else "?"
                bid   = items[0].get("bookingId", "?") if items else "?"
                self._set_results(
                    f"✅ ¡RESERVA EXITOSA!\n"
                    f"{'─'*35}\n"
                    f"Número:    {num}\n"
                    f"bookingId: {bid}\n"
                    f"Slot:      {slot['time']}\n"
                    f"Agencia:   {loc_name}\n"
                    f"Placa:     {customer.VEHICLE_REGO}\n"
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
                r = monitor.booking_result
                texto = (
                    f"✅ ¡CITA AGENDADA!\n"
                    f"{'─'*40}\n"
                    f"Número:  {r['reservationNumber']}\n"
                    f"Fecha:   {format_date(r['slot']['time'])}\n"
                    f"Agencia: {monitor.location_name}\n"
                    f"Placa:   {customer.VEHICLE_REGO}\n"
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

        self.after(10000, self._refresh)  # refresca cada 10 seg

    def _set_results(self, text: str):
        self.results_box.configure(state="normal")
        self.results_box.delete("1.0", "end")
        self.results_box.insert("1.0", text)
        self.results_box.configure(state="disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()
