# Desarrollo, mantenimiento y publicación

## Mapa del repositorio

| Ruta | Responsabilidad |
| --- | --- |
| `custom_components/kinderclose/` | Integración distribuida: configuración, cliente HTTP y parser, coordinador, sensores, manifiesto, traducciones y marca. Mantener esta ruta para HACS y la instalación manual. |
| `tests/` | Pruebas unitarias del cliente y del parser con datos ficticios. |
| `.github/workflows/validate.yaml` | Pruebas Python y validación hassfest en GitHub Actions. |
| `hacs.json` | Metadatos y versión mínima declarada para HACS. |
| `requirements.txt` | Dependencias para las pruebas independientes; el manifiesto declara las de ejecución de la integración. |
| `assets/` | Recursos para documentación; no es el directorio de la integración. |

Para preparar el entorno y ejecutar las pruebas consulta el [README](../README.md#pruebas-para-desarrollo). Las pruebas actuales no arrancan Home Assistant ni comprueban una instalación real. Hassfest valida metadatos, no el funcionamiento completo. Los rangos de dependencias permiten versiones distintas entre instalaciones; un resultado local no garantiza que se haya probado toda la matriz de versiones.

## Revisión de cambios

1. Trabaja en una rama y revisa el comportamiento actual y los cambios de dependencias. No incluyas credenciales, HTML real ni datos de alumnos.
2. Añade pruebas con datos ficticios cuando cambien el parser, las peticiones o la semántica de los datos. Ejecuta las pruebas y comprueba los resultados de Actions.
3. Para cambios de entidades, configuración, atributos o unidades, documenta el impacto y la migración de automatizaciones y tarjetas. No cambies identificadores estables sin una migración explícita.
4. Para cambios que afecten al funcionamiento de Home Assistant, prueba también en una instalación de desarrollo apropiada antes de publicar. No uses datos reales en los artefactos de prueba.

## Lista de publicación

1. Comprueba que el código, las traducciones y la documentación coinciden, y que las pruebas y hassfest pasan en el commit candidato. Verifica compatibilidad con la versión mínima declarada en `hacs.json` y con una versión actual de Home Assistant; si no se ha probado, indícalo en la publicación.
2. Actualiza la versión de `custom_components/kinderclose/manifest.json` y describe en las notas los cambios, correcciones, incompatibilidades y pasos de migración. Comprueba que los requisitos de ejecución y pruebas siguen siendo coherentes.
3. Revisa el diff y prepara una etiqueta Git y una release de GitHub que apunten al mismo commit validado. Publicar una release es una operación independiente de editar este repositorio.
4. En un entorno de prueba, instala o actualiza mediante HACS, reinicia Home Assistant y comprueba configuración, actualización de sensores, reautenticación y descarga de la integración. No publiques credenciales ni datos reales en las evidencias.

## Recuperación

Antes de actualizar una instalación, conserva una copia de seguridad de Home Assistant y anota la versión instalada. Si la nueva versión falla, restaura una versión anterior compatible de la integración mediante HACS o desde una copia, reinicia Home Assistant y verifica la configuración y los sensores. Restaurar el código no revierte necesariamente cambios de configuración, registros o datos históricos: comprueba las notas de la versión y restaura desde la copia cuando sea necesario. Evita borrar entradas o historial como primer paso de diagnóstico.

Para incidencias, anota versiones, pasos y mensajes anonimizados; consulta [SECURITY.md](../SECURITY.md) para vulnerabilidades. Los logs y capturas pueden contener información personal incluso cuando el mensaje parece inocuo.
