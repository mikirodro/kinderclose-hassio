"""Consulta KinderClose y publica sensores mediante la API REST de Home Assistant."""
import argparse
from datetime import date, datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from dotenv import load_dotenv
import requests

BASE = "https://app.kinderclose.com"
LOG = logging.getLogger("kinderclose")


def normalize(value):
    return " ".join(unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower().split())


def nullable(value):
    return value.strip() if value.strip() not in ("", "--") else None


def parse_record(html, url):
    soup = BeautifulSoup(html, "html.parser")
    panels = {}
    for panel in soup.select(".panel"):
        heading = panel.select_one(".panel-title")
        if heading:
            panels[normalize(heading.get_text(" ", strip=True))] = panel
    if not {"presencia", "comidas", "deposicion"}.issubset(panels):
        raise ValueError("La ficha no contiene los paneles esperados; puede haber cambiado la web.")
    match = re.search(r"defaultDate:\s*['\"](\d{4}-\d{2}-\d{2})", html)
    if not match:
        match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", soup.get_text(" "))
    if not match:
        raise ValueError("No se ha podido identificar la fecha de la ficha.")
    record = {"fecha": date.fromisoformat(match[1]).isoformat(), "url": url}
    for section in ("presencia", "comidas"):
        values = {}
        for paragraph in panels[section].select("p"):
            label = paragraph.find("strong")
            if label:
                key = normalize(label.get_text()).replace(" ", "_")
                label_text = label.get_text(" ", strip=True)
                value = paragraph.get_text(" ", strip=True)[len(label_text):].lstrip(" :")
                values[key] = nullable(value)
        record[section] = values
    if record["presencia"].get("ausente") not in ("Sí", "Si", "No"):
        raise ValueError("No se ha podido interpretar la asistencia.")
    record["sueno"] = []
    if "dormir" in panels:
        for row in panels["dormir"].select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) == 2:
                record["sueno"].append(dict(zip(("desde", "hasta"), (nullable(c.get_text(strip=True)) for c in cells))))
    minutes = 0
    complete = True
    for nap in record["sueno"]:
        if not nap["desde"] or not nap["hasta"]:
            complete = False
            continue
        start = datetime.strptime(nap["desde"], "%H:%M")
        end = datetime.strptime(nap["hasta"], "%H:%M")
        minutes += int((end - start).total_seconds() / 60) % (24 * 60)
    record["sueno_minutos"] = minutes if complete and record["sueno"] else None
    record["deposiciones"] = []
    for row in panels["deposicion"].select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) == 3:
            record["deposiciones"].append(dict(zip(("tipo", "hora", "info"), (nullable(c.get_text(" ", strip=True)) for c in cells))))
    return record


class KinderClose:
    def __init__(self):
        self.session = requests.Session()

    def get(self, url):
        if urlparse(url).netloc != urlparse(BASE).netloc:
            raise ValueError("Enlace de KinderClose no válido.")
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        if "/auth/login" in response.url:
            raise ValueError("KinderClose requiere iniciar sesión de nuevo.")
        return response

    def fetch(self, limit=5, requested_date=None):
        try:
            login = self.session.get(BASE + "/auth/login", timeout=30)
            login.raise_for_status()
            token = BeautifulSoup(login.text, "html.parser").select_one('input[name="_token"]')
            if token is None:
                raise ValueError("No se encuentra el formulario de acceso.")
            user, password = os.getenv("KINDERCLOSE_USER"), os.getenv("KINDERCLOSE_PASSWORD")
            if not user or not password:
                raise ValueError("Faltan KINDERCLOSE_USER o KINDERCLOSE_PASSWORD.")
            response = self.session.post(BASE + "/auth/login", data={"_token": token["value"], "email": user, "password": password}, timeout=30)
            response.raise_for_status()
            if "/auth/login" in response.url or BeautifulSoup(response.text, "html.parser").select_one('input[name="password"]'):
                raise ValueError("KinderClose ha rechazado el inicio de sesión.")
            listing = BeautifulSoup(self.get(BASE + "/familiar/alumno").text, "html.parser")
            pupils = {}
            for anchor in listing.select("a[href]"):
                url = urljoin(BASE, anchor["href"])
                match = re.fullmatch(re.escape(BASE) + r"/familiar/alumno/(\d+)", url)
                if match:
                    pupils.setdefault(match[1], []).append(anchor.get_text(" ", strip=True))
            pupil_id = os.getenv("KINDERCLOSE_ALUMNO_ID", "").strip()
            if not pupil_id:
                name = normalize(os.getenv("KINDERCLOSE_ALUMNO", ""))
                matches = [key for key, names in pupils.items() if name and any(normalize(n) == name for n in names)]
                if len(matches) != 1:
                    raise ValueError("El nombre no identifica un único alumno. Configura KINDERCLOSE_ALUMNO_ID.")
                pupil_id = matches[0]
            if pupil_id not in pupils:
                raise ValueError("El alumno configurado no aparece en esta cuenta.")
            pupil_url = BASE + "/familiar/alumno/" + pupil_id
            profile = BeautifulSoup(self.get(pupil_url).text, "html.parser")
            links = list(dict.fromkeys(urljoin(BASE, a["href"]) for a in profile.select("a[href]") if re.fullmatch(re.escape(pupil_url) + r"/ficha/\d+", urljoin(BASE, a["href"]))))
            if requested_date:
                links = [pupil_url + "/ficha/" + requested_date]
            if not links:
                raise ValueError("El alumno todavía no tiene fichas disponibles.")
            records = [parse_record(self.get(url).text, url) for url in links[:limit]]
            records.sort(key=lambda r: r["fecha"], reverse=True)
            return {"alumno_id": pupil_id, "consultado_en": datetime.now(timezone.utc).isoformat(), "fichas": records}
        finally:
            self.session.close()


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
                data = KinderClose().fetch(args.limit, args.date.isoformat() if args.date else None)
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
