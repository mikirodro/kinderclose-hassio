**Español** · [English](README.en.md)

# KinderClose para Home Assistant

![KinderClose](custom_components/kinderclose/brand/logo.png)

Muestra en Home Assistant la ficha diaria de la guardería que publica KinderClose: asistencia, horas de entrada y salida, comidas, siestas, deposiciones, biberones y lo que hay que llevar al centro. Crea un dispositivo con trece sensores por alumno y se actualiza cada 15 minutos.

Desde la versión 1.0 usa la misma API que la app móvil oficial: normalmente basta una petición por consulta y no instala dependencias adicionales.

## Instalación

### Con el Marketplace (Home Assistant 2026.11 o posterior)

1. Abre **Ajustes → Marketplace** y busca **KinderClose**.
2. Descárgalo y reinicia Home Assistant.

Si ya lo tenías instalado con HACS, al actualizar a Home Assistant 2026.11 pasa automáticamente al Marketplace: sigue instalado, conserva su configuración y recibe actualizaciones.

### Con HACS (Home Assistant anterior a 2026.11)

1. Abre **HACS** y busca **KinderClose**.
2. Descárgalo y reinicia Home Assistant.

KinderClose está en el catálogo por defecto de HACS, así que no hace falta añadirlo como repositorio personalizado. HACS no se puede instalar en Home Assistant 2026.11 o posterior.

### Manual

Copia `custom_components/kinderclose` a `/config/custom_components/kinderclose` y reinicia Home Assistant. Con esta opción no recibirás avisos de actualización.

## Configuración

1. En **Ajustes → Dispositivos y servicios → Añadir integración**, selecciona **KinderClose**.
2. Introduce el correo y la contraseña que usas en la app de KinderClose.
3. Si la cuenta tiene varios alumnos, elige uno. Si solo queda uno por configurar, se añade directamente.

Para añadir a otro hermano, repite la configuración con la misma cuenta: los alumnos de una cuenta comparten la sesión. Solo se admiten cuentas con correo y contraseña; el acceso con Google, Facebook o Apple no está disponible.

Requiere Home Assistant 2025.1 o posterior. Las imágenes de la marca se ven a partir de Home Assistant 2026.3.

## Sensores

Los sensores se llaman `sensor.kinderclose_<ID>_<clave>`, donde `<ID>` es el identificador del alumno en KinderClose.

| Clave | Estado | Atributos adicionales |
| --- | --- | --- |
| `ultima_ficha` | Fecha de la ficha | `ficha` (ficha completa), `consultado_en` |
| `asistencia` | `presente` o `ausente` | `ausencia_justificada` |
| `entrada`, `salida` | Hora (`HH:MM`) | `entrada_tarde`, `salida_tarde` |
| `desayuno`, `primero`, `segundo`, `postre`, `merienda` | `Todo`, `Bastante`, `Poco` o `Nada` | — |
| `sueno` | Minutos de siesta | `sesiones` (desde y hasta) |
| `deposiciones` | Número de deposiciones y pises | `detalles`, `control_esfinter` |
| `biberones` | Número de biberones | `detalles` (hora y ml) |
| `recordatorios` | Número de cosas que hay que llevar | `elementos` (por ejemplo, `Pañales` o `Toallitas`) |

Todos incluyen `fecha_ficha` y `url_ficha`, el enlace a la ficha en la web.

**Qué ficha se muestra.** La de hoy si ya existe. Si no, la más reciente de los últimos 7 días, de modo que el lunes por la mañana verás la del viernes: compara `fecha_ficha` con la fecha actual si necesitas saber si es de hoy. Si no hay fichas en esos 7 días (por ejemplo, en vacaciones), los sensores quedan desconocidos.

**Ejemplo:** avisar cuando el centro pida que llevéis algo.

```yaml
triggers:
  - trigger: state
    entity_id: sensor.kinderclose_123456_recordatorios
conditions:
  - condition: numeric_state
    entity_id: sensor.kinderclose_123456_recordatorios
    above: 0
actions:
  - action: notify.notify
    data:
      message: >
        Mañana hay que llevar:
        {{ state_attr('sensor.kinderclose_123456_recordatorios', 'elementos') | join(', ') }}
```

## Funcionamiento

- KinderClose no ofrece una API pública. La integración usa la API JSON de la app oficial, obtenida por ingeniería inversa y documentada en [docs/api.md](docs/api.md). Si KinderClose la cambia, la integración puede dejar de funcionar hasta que se adapte.
- Inicia sesión una vez y guarda en Home Assistant el token del dispositivo, igual que la app. Si KinderClose lo invalida, vuelve a iniciar sesión automáticamente. Si la contraseña deja de ser válida, Home Assistant pide que la actualices.
- En la lista de dispositivos de tu cuenta de KinderClose aparecerá «Home Assistant». Al eliminar la integración se cierra esa sesión.
- Si KinderClose no responde, los sensores se marcan como no disponibles y la consulta se reintenta automáticamente.

## Privacidad

Los sensores contienen datos de menores. Las credenciales y el token se guardan en la configuración interna de Home Assistant. Los atributos detallados (`ficha`, `sesiones`, `detalles`, `elementos`, `url_ficha` y `consultado_en`) no se guardan en el historial; los estados sí, por ejemplo la hora de entrada o los minutos de sueño. Estos datos pueden quedar accesibles desde Home Assistant, su historial y sus copias de seguridad según tu configuración: revisa quién tiene acceso y cuánto tiempo se conservan.

Si no necesitas el historial de estos sensores, exclúyelos de Recorder siguiendo la [documentación de Home Assistant](https://www.home-assistant.io/integrations/recorder/#configure-filter). La exclusión no elimina registros anteriores ni datos de otras integraciones o copias.

## Actualizar desde la versión 0.x

La versión 1.0 es un cambio mayor, pero las entradas existentes siguen funcionando sin reconfigurarlas y los `entity_id` no cambian. Revisa tus plantillas y automatizaciones si usan:

- el atributo `fichas` de `ultima_ficha`, sustituido por `ficha` (solo la última ficha);
- los textos de las comidas, que ahora son los de la app (`Todo`, `Bastante`, `Poco`, `Nada`);
- campos internos de la ficha: `presencia.ausente` es ahora un booleano.

Los detalles están en el [CHANGELOG](CHANGELOG.md). Si algo falla, puedes volver a una versión 0.5.x desde el Marketplace o HACS.

Si todavía usas el script externo o el contenedor Docker anteriores a la versión 0.3.2, configura primero la integración y después detén el script. Los sensores creados mediante la API REST no se migran: comprueba los identificadores de tus tarjetas y automatizaciones.

<!-- ha-marketplace:exclude-start -->

## Desarrollo

Las pruebas usan respuestas JSON ficticias y no necesitan credenciales ni acceso a KinderClose. Requieren Python 3.14, la versión que usa Home Assistant.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements_test.txt
.venv/bin/ruff check .
.venv/bin/python -m unittest discover -s tests -v   # cliente de la API y normalización
.venv/bin/pytest -v                                 # configuración, sensores y token en Home Assistant
```

Para comprobar la API real con tu cuenta sin mostrar datos personales:

```sh
KINDERCLOSE_EMAIL=... KINDERCLOSE_PASSWORD=... .venv/bin/python scripts/probe_api.py
```

Documentación para mantener el proyecto:

- [API de KinderClose: endpoints y campos](docs/api.md).
- [Arquitectura, flujo y contrato de datos](docs/architecture.md).
- [Estructura, desarrollo, publicación y recuperación](docs/maintenance.md).

<!-- ha-marketplace:exclude-end -->

## Seguridad, contribuciones y licencia

- [Comunicar vulnerabilidades de forma privada](SECURITY.md).
- [Guía para contribuir](CONTRIBUTING.md).
- [Licencia MIT](LICENSE).

KinderClose es una marca de sus propietarios. Este proyecto no está afiliado a KinderClose.
