# KinderClose → Home Assistant

Extrae las últimas cinco fichas del alumno configurado y publica once sensores en Home Assistant. Usa el formulario web de KinderClose, con cookies de sesión y token CSRF; no necesita navegador. No modifica fichas ni envía mensajes en KinderClose.

## Configuración

Conserva las variables de tu `.env` y añade:

```dotenv
HOMEASSISTANT_URL=http://homeassistant.local:8123
HOMEASSISTANT_TOKEN=tu_token_de_larga_duracion
POLL_INTERVAL_SECONDS=900
```

Usa una dirección de Home Assistant accesible desde el equipo o contenedor donde ejecutarás el programa. El token se crea en el perfil de usuario de Home Assistant, sección de tokens de acceso de larga duración. No publiques el `.env`: está excluido de Git y de la imagen Docker. `.env.example` contiene todas las opciones.

El ID `KINDERCLOSE_ALUMNO_ID` tiene prioridad. Si está vacío se busca una coincidencia exacta de `KINDERCLOSE_ALUMNO` con el nombre completo del enlace de la web, ignorando mayúsculas y acentos. Si hay ambigüedad, configura el ID.

## Ejecución en Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Comprobar extracción: muestra datos del alumno, sin enviar a Home Assistant.
.\.venv\Scripts\python.exe kinderclose.py --dry-run
# Enviar una vez.
.\.venv\Scripts\python.exe kinderclose.py
# Actualizar cada 15 minutos mientras esté en ejecución.
.\.venv\Scripts\python.exe kinderclose.py --watch
```

En Linux usa `python3 -m venv .venv` y `.venv/bin/python` para los comandos posteriores.

Para consultar una fecha concreta: `python kinderclose.py --date 2026-10-07 --dry-run`. Para limitar las fichas consultadas: `--limit 1` (máximo 5, las que ofrece la ficha del alumno). `--env-file /ruta/.env` permite seleccionar otro fichero. Las variables del entorno tienen prioridad sobre el fichero.

## Ejecución continua con Docker

```sh
docker compose up -d --build
docker compose logs -f
```

Ejecuta Docker en un equipo que pueda acceder a KinderClose y Home Assistant. Este proyecto es un servicio externo; no es un complemento instalable desde la tienda de Home Assistant OS. Con Home Assistant OS, ejecútalo en otro equipo con Docker. Los errores de conexión se registran sin credenciales y se reintentan en el siguiente intervalo.

## Sensores

El prefijo es `sensor.kinderclose_<ID>_` para evitar mezclar alumnos.

| Sufijo | Estado / atributos |
| --- | --- |
| `ultima_ficha` | Fecha de la última ficha; atributo `fichas` con las fichas consultadas y `consultado_en` con la fecha de consulta |
| `asistencia` | `presente` o `ausente`; datos de presencia como atributos |
| `entrada`, `salida` | Hora registrada o `unknown` |
| `desayuno`, `primero`, `segundo`, `postre`, `merienda` | Cantidad registrada o `unknown` |
| `sueno` | Minutos de sueño; atributo `sesiones`; `unknown` si no hay registros o alguna siesta no tiene inicio o fin |
| `deposiciones` | Número de registros; atributo `detalles` |

Todos incluyen `fecha_ficha` y `url_ficha`. Se publica la ficha más reciente disponible: puede ser de un día anterior, por ejemplo un fin de semana. Consulta `fecha_ficha` en tus automatizaciones para comprobarlo. Los campos sin rellenar permanecen desconocidos. Sin fichas o con un error de extracción no se sobrescriben los valores anteriores; `consultado_en` permite comprobar cuándo se actualizaron por última vez. Una interrupción durante el envío puede actualizar solo parte de los sensores; el siguiente ciclo vuelve a publicar todos.

Los sensores aparecen en **Herramientas de desarrollador → Estados** tras el primer envío. Añádelos a tu panel por su identificador. La [API REST de Home Assistant](https://developers.home-assistant.io/docs/api/rest/) permite publicar estados con un token Bearer. Estos sensores no se registran como dispositivos ni como entidades de una integración nativa y deben volver a publicarse tras reiniciar Home Assistant; `--watch` lo hace en el siguiente ciclo. Las cinco fichas son atributos de la última ficha, no un relleno retroactivo del historial de Home Assistant.

Ejemplo de tarjeta manual (sustituye `123` por tu ID):

```yaml
type: entities
title: KinderClose
entities:
  - sensor.kinderclose_123_ultima_ficha
  - sensor.kinderclose_123_asistencia
  - sensor.kinderclose_123_desayuno
  - sensor.kinderclose_123_primero
  - sensor.kinderclose_123_segundo
  - sensor.kinderclose_123_postre
  - sensor.kinderclose_123_merienda
  - sensor.kinderclose_123_sueno
  - sensor.kinderclose_123_deposiciones
```

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas usan HTML ficticio y una API simulada, sin credenciales ni datos personales. La comprobación real de extracción se ejecuta con `--dry-run`. Si KinderClose cambia su HTML, el programa rechaza fichas sin los paneles esperados en lugar de publicar datos vacíos.
