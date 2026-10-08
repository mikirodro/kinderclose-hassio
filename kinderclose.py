"""Consulta KinderClose y publica sensores mediante la API REST de Home Assistant."""
import argparse
from datetime import date
from urllib.parse import urlparse
import json
import logging
import os
from pathlib import Path
import time

from dotenv import load_dotenv
import requests

BASE = "https://app.kinderclose.com"
LOG = logging.getLogger("kinderclose")


# Cliente compartido por el script y la integración nativa.
from custom_components.kinderclose.client import KinderClose, parse_record


def sensor_payloads(data):
    latest = data["fichas"][0]
    prefix = "sensor.kinderclose_" + data["alumno_id"] + "_"
    common = {"fecha_ficha": latest["fecha"], "url_ficha": latest["url"]}
    values = {
        "ultima_ficha": (latest["fecha"], {"device_class": "date", "fichas": data["fichas"], "consultado_en": data["consultado_en"]}),
        "asistencia": ("ausente" if latest["presencia"]["ausente"] in ("Sí", "Si") else "presente", latest["presencia"]),
        "entrada": (latest["presencia"].get("hora_entrada"), {}),
        "salida": (latest["presencia"].get("hora_salida"), {}),
        "sueno": (latest["sueno_minutos"], {"unit_of_measurement": "min", "sesiones": latest["sueno"]}),
        "deposiciones": (len(latest["deposiciones"]), {"detalles": latest["deposiciones"]}),
    }
    for meal in ("desayuno", "primero", "segundo", "postre", "merienda"):
        values[meal] = (latest["comidas"].get(meal), {})
    return {prefix + key: {"state": "unknown" if state is None else str(state), "attributes": {"friendly_name": "KinderClose " + key.replace("_", " "), **common, **attributes}} for key, (state, attributes) in values.items()}


def publish(data):
    base = os.getenv("HOMEASSISTANT_URL", "").rstrip("/")
    token = os.getenv("HOMEASSISTANT_TOKEN", "")
    if not base or not token:
        raise ValueError("Configura HOMEASSISTANT_URL y HOMEASSISTANT_TOKEN en .env.")
    if urlparse(base).scheme not in ("http", "https") or not urlparse(base).netloc:
        raise ValueError("HOMEASSISTANT_URL debe ser una URL HTTP o HTTPS válida.")
    with requests.Session() as session:
        session.headers.update({"Authorization": "Bearer " + token})
        for entity, payload in sensor_payloads(data).items():
            response = session.post(base + "/api/states/" + entity, json=payload, timeout=30, allow_redirects=False)
            if response.status_code not in (200, 201):
                raise ValueError(f"Home Assistant rechazó {entity} (HTTP {response.status_code}); comprueba URL y token.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(Path(__file__).with_name(".env")))
    parser.add_argument("--dry-run", action="store_true", help="Muestra JSON sin enviar a Home Assistant")
    parser.add_argument("--watch", action="store_true", help="Actualiza periódicamente")
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 6))
    parser.add_argument("--date", type=date.fromisoformat, help="Consulta una fecha YYYY-MM-DD")
    args = parser.parse_args()
    load_dotenv(args.env_file)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        interval = int(os.getenv("POLL_INTERVAL_SECONDS", "900"))
        if interval < 60:
            raise ValueError("POLL_INTERVAL_SECONDS debe ser al menos 60.")
        if not args.dry_run and (not os.getenv("HOMEASSISTANT_URL") or not os.getenv("HOMEASSISTANT_TOKEN")):
            raise ValueError("Configura HOMEASSISTANT_URL y HOMEASSISTANT_TOKEN, o usa --dry-run.")
        while True:
            try:
                data = KinderClose(os.getenv("KINDERCLOSE_USER"), os.getenv("KINDERCLOSE_PASSWORD"), os.getenv("KINDERCLOSE_ALUMNO_ID", ""), os.getenv("KINDERCLOSE_ALUMNO", "")).fetch(args.limit, args.date.isoformat() if args.date else None)
                if args.dry_run:
                    print(json.dumps(data, ensure_ascii=False, indent=2))
                else:
                    publish(data)
                    LOG.info("Actualizados 11 sensores; última ficha: %s", data["fichas"][0]["fecha"])
            except (requests.RequestException, ValueError) as error:
                # Los errores HTTP pueden contener URLs privadas: no imprimir respuestas ni cabeceras.
                LOG.error("%s", str(error) if isinstance(error, ValueError) else "Error de conexión HTTP; comprueba conectividad y disponibilidad del servicio.")
                if not args.watch:
                    return 1
            if not args.watch:
                return 0
            time.sleep(interval)
    except ValueError as error:
        LOG.error("%s", error)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
