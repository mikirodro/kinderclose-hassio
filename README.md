# KinderClose para Home Assistant

![KinderClose](custom_components/kinderclose/brand/logo.png)

Integración para consultar las fichas de KinderClose desde Home Assistant. Crea once sensores agrupados en un dispositivo por alumno y consulta hasta cinco fichas cada 15 minutos.

## Instalación

### Con el Marketplace (Home Assistant 2026.11 o posterior)

1. En **Ajustes → Marketplace**, añade `https://github.com/mikirodro/kinderclose-hassio` como repositorio personalizado de tipo **Integración**. Los repositorios personalizados requieren iniciar sesión con GitHub desde el Marketplace.
2. Busca KinderClose, descárgalo y reinicia Home Assistant.

Si ya lo tenías instalado con HACS, al actualizar a Home Assistant 2026.11 pasa automáticamente al Marketplace: sigue instalado, conserva su configuración y recibe actualizaciones.

### Con HACS (Home Assistant anterior a 2026.11)

1. En HACS, abre **Repositorios personalizados** y añade `https://github.com/mikirodro/kinderclose-hassio` como **Integración**.
2. Busca KinderClose, descárgalo y reinicia Home Assistant.

HACS no se puede instalar en Home Assistant 2026.11 o posterior.

### Manual

Copia `custom_components/kinderclose` a `/config/custom_components/kinderclose` y reinicia Home Assistant. Así no recibirás avisos de actualización.

### Configuración

1. En **Ajustes → Dispositivos y servicios → Añadir integración**, selecciona KinderClose.
2. Introduce el correo y la contraseña de KinderClose y el ID del alumno. Si no conoces el ID, indica el nombre completo tal como aparece en la web.

La versión mínima declarada es Home Assistant 2025.1. Las imágenes locales de marca requieren Home Assistant 2026.3 o posterior. La integración se prueba con Home Assistant 2025.1.0 y con versiones actuales mediante respuestas simuladas; esas pruebas no sustituyen una instalación completa ni una consulta a KinderClose.

Puedes añadir varios alumnos repitiendo la configuración. Las credenciales se guardan en la configuración interna de Home Assistant. Si KinderClose las rechaza, la integración solicita reautenticación. Si falla una actualización, los sensores se marcan como no disponibles y se reintenta automáticamente. Si el alumno todavía no tiene fichas, no se crea la entrada.

## Sensores y privacidad

El prefijo es `sensor.kinderclose_<ID>_`. Los sensores son `ultima_ficha`, `asistencia`, `entrada`, `salida`, `desayuno`, `primero`, `segundo`, `postre`, `merienda`, `sueno` y `deposiciones`.

Se muestra la ficha más reciente entre las consultadas, que puede ser de un día anterior. La integración consulta los primeros cinco enlaces que ofrece KinderClose; la selección depende del orden de esa página. Todos los sensores incluyen la fecha y el enlace de la ficha. `ultima_ficha` incluye hasta cinco fichas en sus atributos; `sueno` contiene sesiones y `deposiciones` incluye detalles. Desde la versión 0.4.0 esos atributos detallados, el enlace y el momento de consulta no se guardan en el historial de Home Assistant; los estados de los sensores (por ejemplo, la hora de entrada o los minutos de sueño) sí. Estos datos de menores pueden quedar accesibles desde Home Assistant, su historial y sus copias de seguridad según tu configuración. Revisa los accesos y la retención antes de compartirlos.

Si no necesitas historial de estos sensores, puedes excluir sus entidades de Recorder siguiendo la [documentación de Home Assistant](https://www.home-assistant.io/integrations/recorder/#configure-filter). La exclusión no elimina registros anteriores ni datos de otras integraciones o copias.

## Actualización desde el script anterior

Desde la versión 0.3.2 el proyecto solo distribuye la integración de Home Assistant. Si usabas el script externo o el contenedor Docker, configura primero la integración nativa y después detén el script o contenedor. Los sensores creados mediante la API REST no se migran automáticamente al registro de entidades: comprueba los identificadores de tus tarjetas y automatizaciones.

<!-- ha-marketplace:exclude-start -->

## Pruebas para desarrollo

Las pruebas utilizan HTML ficticio y peticiones simuladas; no necesitan credenciales ni acceso a KinderClose. Requieren Python 3.14, la versión que usa Home Assistant.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements_test.txt
.venv/bin/ruff check .
.venv/bin/python -m unittest discover -s tests -v   # cliente y parser
.venv/bin/pytest -v                                 # flujo de configuración y sensores en Home Assistant
```

`requirements.txt` contiene las dependencias del cliente y `requirements_test.txt` añade Home Assistant de pruebas y ruff; la integración declara sus propios requisitos en el manifiesto.

## Documentación para mantener el proyecto

- [Arquitectura, flujo y contrato de datos](docs/architecture.md).
- [Estructura, desarrollo, publicación y recuperación](docs/maintenance.md).

<!-- ha-marketplace:exclude-end -->

## Seguridad, contribuciones y licencia

- [Comunicar vulnerabilidades de forma privada](SECURITY.md).
- [Guía para contribuir](CONTRIBUTING.md).
- [Licencia MIT](LICENSE).
