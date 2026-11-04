# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). La sección de cada versión se usa como notas de la release de GitHub.

## [0.4.0]

### Privacidad

- Las fichas completas (`fichas`), las sesiones de sueño (`sesiones`), los detalles de deposiciones (`detalles`), el enlace (`url_ficha`) y `consultado_en` siguen visibles en el estado actual, pero ya no se guardan en el historial de Home Assistant ni en sus copias. El historial anterior no se borra automáticamente.

### Cambios

- Los nombres de los sensores se traducen según el idioma de Home Assistant. En español no cambian; en otros idiomas se muestran en inglés. Los identificadores `sensor.kinderclose_<ID>_*` no cambian.
- El formulario distingue alumno no encontrado, alumno sin fichas y errores inesperados, que ahora se registran en el log en lugar de mostrar un error genérico.
- Se limita `beautifulsoup4` a versiones `<5` para evitar roturas por una versión mayor.

### Mantenimiento

- Pruebas de Home Assistant para la configuración, la reautenticación, la carga y la descarga.
- CI con ruff (incluidas reglas de seguridad) y validación de HACS. Las releases se publican con un workflow que valida el commit antes de crear el tag.

## [0.3.4]

- Documenta la arquitectura, el flujo y el contrato de datos, la privacidad y el mantenimiento.

## [0.3.3]

- Actualiza la referencia fijada de la acción hassfest.

## [0.3.2]

- El proyecto distribuye solo la integración de Home Assistant; se retiran el script externo y el contenedor Docker.
