# Desarrollo, mantenimiento y publicación

## Mapa del repositorio

| Ruta | Responsabilidad |
| --- | --- |
| `custom_components/kinderclose/` | Integración distribuida: configuración, cliente HTTP y parser, coordinador, sensores, manifiesto, traducciones y marca. Mantener esta ruta para HACS y la instalación manual. |
| `tests/` | Pruebas unitarias del cliente y del parser (`unittest`) con datos ficticios. |
| `tests/ha/` | Pruebas con Home Assistant (`pytest-homeassistant-custom-component`): configuración, reautenticación, sensores y descarga. |
| `.github/workflows/validate.yaml` | Ruff, pruebas, hassfest y validación de HACS. Los jobs `tests` y `hassfest` son checks obligatorios de `main`. |
| `.github/workflows/release.yaml` | Publicación manual: valida el commit y crea el tag y la release. |
| `CHANGELOG.md` | Cambios por versión; su sección es el texto de la release. |
| `hacs.json` | Metadatos y versión mínima declarada para HACS. |
| `requirements.txt`, `requirements_test.txt` | Dependencias del cliente y de la CI; el manifiesto declara las de ejecución de la integración. |
| `assets/` | Recursos para documentación; no es el directorio de la integración. |

Para preparar el entorno y ejecutar las pruebas consulta el [README](../README.md#pruebas-para-desarrollo). Las pruebas de `tests/ha` arrancan un Home Assistant de pruebas con respuestas simuladas, pero no comprueban la web real ni una instalación completa. Hassfest valida metadatos, no el funcionamiento completo. Los rangos de dependencias permiten versiones distintas entre instalaciones; un resultado local no garantiza que se haya probado toda la matriz de versiones.

La CI actual no valida Home Assistant 2025.1, el mínimo de `hacs.json`. Antes de prometerlo en una release, instala la integración en entornos aislados con esa versión y con una versión actual; comprueba instalación por HACS, configuración, actualización, reautenticación y descarga. Documenta los resultados; si el mínimo no funciona, fija la primera versión realmente compatible y comunica el impacto. Para probar KinderClose usa una cuenta de desarrollo autorizada y nunca guardes respuestas reales ni credenciales en artefactos.

La acción HACS fijada por SHA ejecuta la imagen `ghcr.io/hacs/action:main`, cuya etiqueta puede cambiar. Revisa su origen y digest periódicamente; fijar el SHA de la acción no fija esa imagen. La versión de `aiohttp` de `requirements.txt` corresponde a pruebas independientes: Home Assistant controla la versión de su propia instalación.

## Revisión de cambios

1. Trabaja en una rama y revisa el comportamiento actual y los cambios de dependencias. No incluyas credenciales, HTML real ni datos de alumnos.
2. Añade pruebas con datos ficticios cuando cambien el parser, las peticiones o la semántica de los datos. Ejecuta las pruebas y comprueba los resultados de Actions.
3. Para cambios de entidades, configuración, atributos o unidades, documenta el impacto y la migración de automatizaciones y tarjetas. No cambies identificadores estables sin una migración explícita.
4. Para cambios que afecten al funcionamiento de Home Assistant, prueba también en una instalación de desarrollo apropiada antes de publicar. No uses datos reales en los artefactos de prueba.

## Lista de publicación

1. En un pull request, sube la versión de `custom_components/kinderclose/manifest.json` y añade en `CHANGELOG.md` una sección `## [X.Y.Z]` con los cambios, correcciones, incompatibilidades y pasos de migración. Comprueba que el código, las traducciones y la documentación coinciden y que los requisitos de ejecución y pruebas siguen siendo coherentes.
2. Fusiona el pull request cuando los checks pasen.
3. En GitHub, abre **Actions → Release → Run workflow** sobre `main`. El workflow comprueba que la versión no esté publicada y que exista su sección en el changelog, valida ese commit con los mismos checks que los pull requests y, solo si pasan, crea el tag y la release con las notas del changelog. No crees tags ni releases a mano: el ruleset de tags impide moverlos o borrarlos después.
4. En un entorno de prueba, instala o actualiza mediante HACS, reinicia Home Assistant y comprueba configuración, actualización de sensores, reautenticación y descarga de la integración. Verifica la compatibilidad con la versión mínima de `hacs.json`; si no se ha probado, indícalo en la release. No publiques credenciales ni datos reales en las evidencias.

## Recuperación

Antes de actualizar una instalación, conserva una copia de seguridad de Home Assistant y anota la versión instalada. Si la nueva versión falla, restaura una versión anterior compatible de la integración mediante HACS o desde una copia, reinicia Home Assistant y verifica la configuración y los sensores. Restaurar el código no revierte necesariamente cambios de configuración, registros o datos históricos: comprueba las notas de la versión y restaura desde la copia cuando sea necesario. Evita borrar entradas o historial como primer paso de diagnóstico.

Para incidencias, anota versiones, pasos y mensajes anonimizados; consulta [SECURITY.md](../SECURITY.md) para vulnerabilidades. Los logs y capturas pueden contener información personal incluso cuando el mensaje parece inocuo.
