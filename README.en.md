[Español](README.md) · **English**

# KinderClose for Home Assistant

![KinderClose](custom_components/kinderclose/brand/logo.png)

Shows in Home Assistant the daily nursery report published by KinderClose: attendance, check-in and check-out times, meals, naps, bowel movements, bottles and what to bring to the nursery. It creates a device with thirteen sensors per child and updates every 15 minutes.

Since version 1.0 it uses the same API as the official mobile app: a single request per update is usually enough, and it installs no additional dependencies.

## Installation

### From the Marketplace (Home Assistant 2026.11 or later)

1. Open **Settings → Marketplace** and search for **KinderClose**.
2. Download it and restart Home Assistant.

If you had already installed it with HACS, it moves to the Marketplace automatically when you update to Home Assistant 2026.11: it stays installed, keeps its configuration and keeps receiving updates.

### With HACS (Home Assistant before 2026.11)

1. Open **HACS** and search for **KinderClose**.
2. Download it and restart Home Assistant.

KinderClose is in the HACS default catalog, so you don't need to add it as a custom repository. HACS cannot be installed on Home Assistant 2026.11 or later.

### Manual

Copy `custom_components/kinderclose` to `/config/custom_components/kinderclose` and restart Home Assistant. With this option you won't be notified of updates.

## Configuration

1. In **Settings → Devices & services → Add integration**, select **KinderClose**.
2. Enter the email and password you use in the KinderClose app.
3. If the account has several children, choose one. If only one is left to configure, it is added directly.

To add a sibling, repeat the configuration with the same account: children from one account share the session. Only email and password accounts are supported; signing in with Google, Facebook or Apple is not available.

Requires Home Assistant 2025.1 or later. Brand images are shown from Home Assistant 2026.3 onwards.

## Sensors

Sensors are named `sensor.kinderclose_<ID>_<key>`, where `<ID>` is the child's identifier in KinderClose. Sensor names are translated, but keys and state values are in Spanish, as in the app.

| Key | State | Additional attributes |
| --- | --- | --- |
| `ultima_ficha` (latest record) | Date of the report | `ficha` (full report), `consultado_en` (fetched at) |
| `asistencia` (attendance) | `presente` (present) or `ausente` (absent) | `ausencia_justificada` (excused absence) |
| `entrada`, `salida` (check-in, check-out) | Time (`HH:MM`) | `entrada_tarde`, `salida_tarde` (afternoon times) |
| `desayuno`, `primero`, `segundo`, `postre`, `merienda` (breakfast, first course, second course, dessert, afternoon snack) | `Todo` (all), `Bastante` (most), `Poco` (a little) or `Nada` (nothing) | — |
| `sueno` (sleep) | Nap minutes | `sesiones` (from and to) |
| `deposiciones` (bowel movements) | Number of bowel movements and wees | `detalles`, `control_esfinter` (toilet trained) |
| `biberones` (bottles) | Number of bottles | `detalles` (time and ml) |
| `recordatorios` (reminders) | Number of things to bring | `elementos` (for example, `Pañales` or `Toallitas`: nappies or wipes) |

All of them include `fecha_ficha` and `url_ficha`, the link to the report on the website.

**Which report is shown.** Today's, if it already exists. Otherwise, the most recent one from the last 7 days, so on Monday morning you'll see Friday's: compare `fecha_ficha` with the current date if you need to know whether it is today's. If there are no reports in those 7 days (for example, during holidays), the sensors are unknown.

**Example:** get notified when the nursery asks you to bring something.

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
        Bring tomorrow:
        {{ state_attr('sensor.kinderclose_123456_recordatorios', 'elementos') | join(', ') }}
```

## How it works

- KinderClose does not offer a public API. The integration uses the JSON API of the official app, reverse engineered and documented in [docs/api.md](docs/api.md) (in Spanish). If KinderClose changes it, the integration may stop working until it is adapted.
- It signs in once and stores the device token in Home Assistant, just like the app. If KinderClose invalidates it, it signs in again automatically. If the password is no longer valid, Home Assistant asks you to update it.
- "Home Assistant" will appear in the device list of your KinderClose account. Removing the integration signs that session out.
- If KinderClose does not respond, the sensors become unavailable and the update is retried automatically.

## Privacy

The sensors contain data about minors. Credentials and the token are stored in Home Assistant's internal configuration. Detailed attributes (`ficha`, `sesiones`, `detalles`, `elementos`, `url_ficha` and `consultado_en`) are not stored in the history; states are, for example the check-in time or the nap minutes. Depending on your setup, this data may be accessible from Home Assistant, its history and its backups: review who has access and how long it is kept.

If you don't need the history of these sensors, exclude them from Recorder following the [Home Assistant documentation](https://www.home-assistant.io/integrations/recorder/#configure-filter). Excluding them does not delete earlier records or data from other integrations or backups.

## Upgrading from version 0.x

Version 1.0 is a major change, but existing entries keep working without reconfiguring them and `entity_id`s don't change. Review your templates and automations if they use:

- the `fichas` attribute of `ultima_ficha`, replaced by `ficha` (only the latest report);
- the meal texts, which are now the app's (`Todo`, `Bastante`, `Poco`, `Nada`);
- internal report fields: `presencia.ausente` is now a boolean.

Details are in the [CHANGELOG](CHANGELOG.md) (in Spanish). If something goes wrong, you can go back to a 0.5.x version from the Marketplace or HACS.

If you still use the external script or Docker container from before version 0.3.2, configure the integration first and then stop the script. Sensors created through the REST API are not migrated: check the identifiers in your cards and automations.

<!-- ha-marketplace:exclude-start -->

## Development

Tests use fake JSON responses and need neither credentials nor access to KinderClose. They require Python 3.14, the version used by Home Assistant.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements_test.txt
.venv/bin/ruff check .
.venv/bin/python -m unittest discover -s tests -v   # API client and normalization
.venv/bin/pytest -v                                 # configuration, sensors and token in Home Assistant
```

To check the real API with your account without showing personal data:

```sh
KINDERCLOSE_EMAIL=... KINDERCLOSE_PASSWORD=... .venv/bin/python scripts/probe_api.py
```

Documentation for maintaining the project (in Spanish):

- [KinderClose API: endpoints and fields](docs/api.md).
- [Architecture, flow and data contract](docs/architecture.md).
- [Structure, development, publishing and recovery](docs/maintenance.md).

<!-- ha-marketplace:exclude-end -->

## Security, contributing and license

- [Report vulnerabilities privately](SECURITY.md).
- [Contributing guide](CONTRIBUTING.md).
- [MIT license](LICENSE).

KinderClose is a trademark of its owners. This project is not affiliated with KinderClose.
