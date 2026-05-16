# 🚗 Cita DEKRA

Agendador automático de citas DEKRA Costa Rica. Monitorea la disponibilidad en las agencias que elijas y reserva tu cita en cuanto aparezca un espacio libre.

## Por qué una app local y no una página web

Una página web depende de un servidor que ejecute el monitoreo en segundo plano. Eso implica infraestructura, costos y límites de tiempo de ejecución — los servicios gratuitos (Railway, Render, etc.) cortan procesos que duran más de unos minutos sin actividad.

Esta app corre directamente en tu computadora: el monitoreo es infinito, ininterrumpido y sin costo mientras la tengas abierta. No necesitás cuenta en ningún servicio ni configurar nada externo.

## Descarga

<p>
  <a href="../../releases/latest/download/CitaDEKRA-mac.zip">
    <img src="https://img.shields.io/badge/Mac-Descargar-black?style=for-the-badge&logo=apple" alt="Descargar para Mac">
  </a>
  &nbsp;
  <a href="../../releases/latest/download/CitaDEKRA.exe">
    <img src="https://img.shields.io/badge/Windows-Descargar-0078D4?style=for-the-badge&logo=windows" alt="Descargar para Windows">
  </a>
</p>

## Instalación

**Mac:**
1. Descomprimí el `.zip`
2. Abrí la Terminal y ejecutá:
   ```bash
   xattr -cr ~/Downloads/CitaDEKRA.app
   ```
3. Doble clic en `CitaDEKRA.app`

> Este paso es necesario porque la app no está firmada con un certificado de Apple. No afecta su funcionamiento.

**Windows:**
1. Descomprimí el `.zip`
2. Doble clic en `CitaDEKRA.exe`
3. Si aparece una advertencia de Windows ("PC protegido" o "autor desconocido"), hacé clic en **Más información** → **Ejecutar de todos modos**

> Esto ocurre porque la app no tiene firma digital de pago. No afecta su funcionamiento.

## Uso

La primera vez que abrís la app, te lleva automáticamente a la pestaña **Mis datos**. Llenás tu nombre, correo, teléfono y placa, guardás, y ya podés usarla.

1. Seleccioná una o varias agencias
2. Elegí el rango de fechas y el intervalo de revisión
3. Opcionalmente filtrá por rango de horario
4. Presioná **▶ Iniciar** — la app reserva sola cuando encuentra disponibilidad

## Alertas por plataforma

| OS | Alerta |
|----|--------|
| macOS | Sonido Glass + voz Paulina |
| Windows | Notificación del sistema |
