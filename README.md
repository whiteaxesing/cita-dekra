# 🚗 Cita DEKRA

Monitor de disponibilidad de citas DEKRA Costa Rica. Revisa automáticamente si hay espacio disponible en la agencia que elijas y te avisa con sonido y voz en cuanto aparezca algo. Si querés, puede agendar la cita por vos automáticamente.

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
1. Doble clic en `CitaDEKRA.exe`

## Uso

La primera vez que abrís la app, te lleva automáticamente a la pestaña **Mis datos**. Llenás tu nombre, correo, teléfono y placa, guardás, y ya podés usar el monitor.

1. Seleccioná la agencia
2. Elegí el rango de fechas
3. Configurá el intervalo de revisión
4. Activá **Auto-agendar** si querés que reserve solo cuando encuentre disponibilidad
5. Presioná **▶ Iniciar**

## Alertas por plataforma

| OS | Alerta |
|----|--------|
| macOS | Sonido Glass + voz Paulina |
| Windows | Notificación del sistema |
