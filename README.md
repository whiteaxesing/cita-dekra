# 🚗 Cita DEKRA

Monitor de disponibilidad de citas DEKRA Costa Rica. Revisa automáticamente si hay espacio disponible en la agencia que elijas y te avisa con sonido y voz en cuanto aparezca algo. Si querés, puede agendar la cita por vos automáticamente.

## Requisitos

- Python 3.11+

## Instalación

```bash
pip install -r requirements.txt
```

> **macOS:** si ves `No module named '_tkinter'`, instalá el soporte con `brew install python-tk`.

## Configurar tus datos

Antes de correr la app, copiá el archivo de ejemplo y llenalo con tus datos:

```bash
cp customer.example.py customer.py
```

Editá `customer.py`:

```python
FIRST_NAME    = "Juan"
LAST_NAME     = "Pérez González"
EMAIL         = "juan@example.com"
PHONE         = "88881234"
COUNTRY_CODE  = "+506"
VEHICLE_REGO  = "ABC123"   # número de placa sin guión
```

`customer.py` está en `.gitignore` — tus datos nunca se suben al repo.

## Uso

```bash
python3 app_tk.py
```

1. Seleccioná la agencia
2. Elegí el rango de fechas
3. Configurá el intervalo de revisión
4. Activá **Auto-agendar** si querés que reserve solo cuando encuentre disponibilidad
5. Presioná **▶ Iniciar**

## Plataformas

| OS | Alerta |
|----|--------|
| macOS | Sonido Glass + voz Paulina |
| Windows | Notificación del sistema |
| Linux | `notify-send` |
