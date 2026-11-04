# KinderClose para Home Assistant

![KinderClose](custom_components/kinderclose/brand/logo.png)

Integración para consultar las fichas de KinderClose desde Home Assistant. Crea once sensores agrupados en un dispositivo por alumno y consulta hasta cinco fichas cada 15 minutos.

## Instalación con HACS

1. En HACS, abre **Repositorios personalizados** y añade `https://github.com/mikirodro/kinderclose-hassio` como **Integración**.
2. Busca KinderClose, descárgalo y reinicia Home Assistant.
3. En **Ajustes → Dispositivos y servicios → Añadir integración**, selecciona KinderClose.
4. Introduce el correo y la contraseña de KinderClose y el ID del alumno. Si no conoces el ID, indica el nombre completo tal como aparece en la web.

También puedes copiar `custom_components/kinderclose` a `/config/custom_components/kinderclose` y reiniciar Home Assistant. Las imágenes locales de marca requieren Home Assistant 2026.3 o posterior.

Puedes añadir varios alumnos repitiendo la configuración. Las credenciales se guardan en la configuración interna de Home Assistant. Si KinderClose las rechaza, la integración solicita reautenticación. Si falla una actualización, los sensores se marcan como no disponibles y se reintenta automáticamente. Si el alumno todavía no tiene fichas, no se crea la entrada.

## Sensores y privacidad

El prefijo es `sensor.kinderclose_<ID>_`. Los sensores son `ultima_ficha`, `asistencia`, `entrada`, `salida`, `desayuno`, `primero`, `segundo`, `postre`, `merienda`, `sueno` y `deposiciones`.

Se muestra la ficha más reciente entre las consultadas, que puede ser de un día anterior. La integración consulta los primeros cinco enlaces que ofrece KinderClose; la selección depende del orden de esa página. Todos los sensores incluyen la fecha y el enlace de la ficha. `ultima_ficha` incluye hasta cinco fichas en sus atributos; `sueno` contiene sesiones y `deposiciones` incluye detalles. Estos datos de menores pueden quedar accesibles desde Home Assistant, su historial y sus copias de seguridad según tu configuración. Revisa los accesos y la retención antes de compartirlos.

## Actualización desde el script anterior

Desde la versión 0.3.2 el proyecto solo distribuye la integración de Home Assistant. Si usabas el script externo o el contenedor Docker, configura primero la integración nativa y después detén el script o contenedor. Los sensores creados mediante la API REST no se migran automáticamente al registro de entidades: comprueba los identificadores de tus tarjetas y automatizaciones.

## Pruebas para desarrollo

Las pruebas utilizan HTML ficticio y peticiones simuladas; no necesitan credenciales ni acceso a KinderClose.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

El archivo `requirements.txt` contiene dependencias para las pruebas fuera de Home Assistant; la integración declara sus propios requisitos en el manifiesto.

## Documentación para mantener el proyecto

- [Arquitectura, flujo y contrato de datos](docs/architecture.md).
- [Estructura, desarrollo, publicación y recuperación](docs/maintenance.md).

## Seguridad, contribuciones y licencia

- [Comunicar vulnerabilidades de forma privada](SECURITY.md).
- [Guía para contribuir](CONTRIBUTING.md).
- [Licencia MIT](LICENSE).
