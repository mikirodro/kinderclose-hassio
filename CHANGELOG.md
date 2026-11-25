# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). La sección de cada versión se usa como notas de la release de GitHub.

## [1.0.0]

Versión mayor: la integración deja de analizar la web de KinderClose y usa la API JSON de la app móvil oficial. Revisa **Incompatibilidades** antes de actualizar.

### Cambios

- **API en lugar de HTML.** La API v3 que usa la app «KinderClose Familiar» se ha obtenido por ingeniería inversa de la propia app y se documenta en `docs/api.md`. Una consulta normal pasa de hasta siete páginas HTML (inicio de sesión, listado, perfil y cinco fichas) a **una petición JSON**. Desaparece la dependencia `beautifulsoup4`: la integración ya no instala paquetes.
- **Sesión persistente.** Se inicia sesión una vez y el token de dispositivo se guarda en la entrada, así que los reinicios no vuelven a enviar la contraseña ni registran dispositivos nuevos en la cuenta. Si KinderClose rechaza el token, se inicia sesión de nuevo una sola vez. Al eliminar la integración se cierra la sesión de ese dispositivo.
- **Configuración más sencilla.** Basta con el correo y la contraseña. La integración detecta los alumnos activos de la cuenta y deja elegir entre ellos, o crea la entrada directamente si solo hay uno sin configurar. Ya no hace falta conocer el ID ni escribir el nombre completo.
- **Última ficha fiable.** Se pide la ficha del día. Si no hay, se busca la más reciente de los últimos 7 días, en lugar de depender del orden de los enlaces de la web. Las fechas y horas se interpretan en la zona horaria de Home Assistant. Las fichas de días anteriores se recuerdan en memoria y no se vuelven a pedir.
- **Sin ficha no es un error.** Si no hay ninguna ficha en 7 días (vacaciones) o el alumno aún no tiene ninguna, los sensores quedan desconocidos en lugar de no disponibles, y se puede configurar igualmente.
- **Nuevos sensores:** `biberones` (número de biberones, con hora y ml) y `recordatorios` (número de cosas que hay que llevar: pañales, toallitas, agua, muda o un texto del centro).
- **Nuevos atributos:** `ausencia_justificada` en asistencia, `entrada_tarde` y `salida_tarde` para el turno de tarde, y `control_esfinter` en deposiciones.
- Sesión HTTP sin cookies, sin redirecciones y con un límite de 1 MiB por respuesta. Un 429 (límite de peticiones) se trata como error temporal.
- `scripts/probe_api.py` comprueba la API con una cuenta real mostrando solo la estructura de las respuestas.

### Incompatibilidades

- El atributo `fichas` de `ultima_ficha` (lista de hasta cinco fichas) se sustituye por `ficha`, con la última ficha completa. Las plantillas que usen `fichas[0]` deben usar `ficha`.
- En la ficha normalizada, `presencia.ausente` pasa de texto (`Sí`/`No`) a booleano. El estado del sensor `asistencia` no cambia (`presente`/`ausente`).
- Las comidas toman los textos de la app (`Todo`, `Bastante`, `Poco`, `Nada`). Si el centro usaba otros textos en la web, los estados pueden cambiar.
- Las horas de las siestas y de las deposiciones se dan siempre en `HH:MM`.
- La opción «nombre completo del alumno» desaparece del formulario. Las entradas existentes siguen funcionando sin volver a configurarlas: conservan sus credenciales y su ID, y obtienen el token en la primera consulta.

No cambian los `entity_id` (`sensor.kinderclose_<ID>_<clave>`) ni los estados de los sensores existentes, salvo los matices de arriba.

## [0.5.4]

### Documentación

- KinderClose ya forma parte del catálogo por defecto de HACS. El README explica la instalación buscando la integración directamente en **HACS** o en **Ajustes → Marketplace**, sin añadirla como repositorio personalizado, tal como se pidió en la revisión de HACS.

### Mantenimiento

- Se actualiza `ruff` de 0.17.3 a 0.17.4 en las herramientas de pruebas (Dependabot, #26).

No cambian los sensores, sus identificadores ni sus atributos.

## [0.5.3]

### Rendimiento

- El análisis del HTML de KinderClose (formulario de acceso, listado de alumnos, perfil y fichas) se ejecuta fuera del bucle de eventos de Home Assistant, en un hilo con `asyncio.to_thread`. Antes, cada consulta cada 15 minutos analizaba hasta siete páginas de hasta 2 MiB en el bucle y podía bloquear durante ese tiempo al resto de integraciones.
- El análisis se separa en funciones puras que reciben el HTML y devuelven los datos (`parse_login_token`, `has_password_field`, `parse_pupils`, `parse_record_links` y `parse_record`).

No cambian los sensores, sus identificadores ni sus atributos.

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
