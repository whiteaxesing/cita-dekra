# 🚗 Cita DEKRA

Monitor de disponibilidad de citas DEKRA Costa Rica. Revisa automáticamente si hay espacio disponible en la agencia que elijas y te avisa con sonido y voz en cuanto aparezca algo.

## Requisitos

- Python 3.11+
- pip

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
streamlit run app.py
```

Se abre en el browser en `http://localhost:8501`.

1. Seleccioná la agencia
2. Elegí el rango de fechas
3. Configurá el intervalo y el sonido
4. Presioná **Iniciar monitor**

## Plataformas

| OS | Notificación |
|----|-------------|
| macOS | Sonido Glass + voz Paulina |
| Windows | Notificación del sistema |
| Linux | `notify-send` |
