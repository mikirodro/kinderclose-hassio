# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). La sección de cada versión se usa como notas de la release de GitHub.

## [0.5.2]

### Mantenimiento

- Preparación para el Marketplace de Home Assistant 2026.11: el manifiesto declara la categoría `productivity_information` y la validación de `hacs/action` ya no omite la comprobación de marca, como exige el catálogo.
- El README explica la instalación desde **Ajustes → Marketplace** y mantiene HACS para versiones anteriores a 2026.11. Las secciones de desarrollo no se muestran en el Marketplace.
- `DeviceInfo` se importa de `homeassistant.helpers.device_registry`. En 2026.11 es una dataclass; la integración ya lo creaba con argumentos con nombre, así que no cambia su comportamiento.

No cambian los sensores, sus identificadores ni sus atributos. Los `entity_id` no cambian con el nuevo sistema de nombres de 2026.11; las tarjetas o plantillas que usen `friendly_name` pueden mostrar nombres distintos tras renombrar la entidad o el dispositivo.

## [0.5.1]

### Seguridad y mantenimiento

- Se rechazan respuestas HTTP de más de 2 MiB una vez descomprimidas. Una página legítima mayor provocaría un error controlado.
- Se actualiza el mínimo de `aiohttp` para pruebas independientes a 3.14.5. Home Assistant gestiona su propia versión; este cambio no la actualiza.
- La CI comprueba Home Assistant 2025.1.0 y una versión actual con respuestas simuladas; la instalación completa mediante HACS y la web real requieren pruebas adicionales.

## [0.5.0]

### Cambios

- El cliente usa `aiohttp` de forma asíncrona, como recomienda Home Assistant, en lugar de `requests` en hilos del executor.
- Los alumnos configurados con la misma cuenta (mismo correo y contraseña) comparten una sola sesión y un solo inicio de sesión. Si caduca, se renueva una única vez aunque varios alumnos se actualicen a la vez.
- La fecha de la ficha es más fiable: se toma del calendario de la página; si no existe, de la única fecha de los encabezados y, si tampoco, de la única fecha del texto. Se entienden los formatos `2026-10-07` y `7/10/2026`. Si hay varias fechas posibles (por ejemplo, la de nacimiento), la actualización falla con un error claro en lugar de mostrar una fecha equivocada.

No cambian los sensores, sus identificadores ni sus atributos.

## [0.4.0]

### Privacidad

- Las fichas completas (`fichas`), las sesiones de sueño (`sesiones`), los detalles de deposiciones (`detalles`), el enlace (`url_ficha`) y `consultado_en` siguen visibles en el estado actual, pero se excluyen del historial de Home Assistant. Esto no garantiza su ausencia de otras copias o integraciones. El historial anterior no se borra automáticamente.

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
