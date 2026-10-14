# Reverse API Engineer: plan de simplificación

La integración actual ya utiliza `requests.Session` y consulta rutas HTTP sin navegador. **Reverse API Engineer es una herramienta de desarrollo, no una dependencia de ejecución**.

## Diagnóstico del cliente actual

- `client.py`: autenticación mediante formulario con token CSRF, redirecciones restringidas al dominio, sesión persistente y reintento único tras caducidad.
- `_fetch`: recupera listado de alumnos, perfil y fichas HTML.
- `parse_record`: extrae asistencia, comidas, sueño y deposiciones del HTML.
- `coordinator.py`: ejecución fuera del event loop y refresco cada 15 minutos.

No se debe reemplazar este cliente por código generado sin verificar primero si KinderClose dispone de endpoints JSON internos estables. Si solo utiliza páginas HTML, la herramienta no simplificará necesariamente el código.

## Captura controlada

1. Instalar `reverse-api-engineer` en un entorno de desarrollo aislado (no dentro de Home Assistant).
2. Abrir una sesión de prueba propia en `https://app.kinderclose.com`.
3. Capturar inicio de sesión, listado de alumnos, perfil y una ficha con los mecanismos de la herramienta.
4. Inspeccionar el HAR **localmente**; contiene potencialmente contraseñas, cookies, tokens CSRF y datos personales de menores. No subir el HAR, sus respuestas ni los clientes generados sin revisión a GitHub ni enviarlos a servicios de IA externos.
5. Identificar endpoints JSON, métodos, parámetros, paginación, caducidad y errores.
6. Si hay endpoints adecuados, reemplazar solo la obtención y normalización de datos en `client.py`, preservando la interfaz `KinderClose.fetch(limit, requested_date)`, el contrato de once sensores y el coordinador.

## Criterios de aceptación

- Misma estructura `{alumno_id, consultado_en, fichas}` y mismos campos en cada ficha.
- Misma validación de alumno y control de redirecciones, sin exponer credenciales a otros hosts.
- Sin login en cada actualización; reautenticación limitada.
- Pruebas unitarias con respuestas anonimizadas, sin datos reales de menores.
- Compatibilidad HACS, sin navegador, modelo de IA ni Reverse API Engineer en tiempo de ejecución.
- Comparativa de peticiones y tiempo de ejecución antes/después.

**Estado:** fase de análisis. Aún no existe una captura autenticada que permita implementar y probar un cliente alternativo con seguridad.
