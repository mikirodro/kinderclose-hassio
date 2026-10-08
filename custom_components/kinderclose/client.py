"""Cliente compartido de KinderClose, independiente de Home Assistant."""
from datetime import date, datetime, timezone
import re
import unicodedata
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import requests

BASE = "https://app.kinderclose.com"


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


class AuthenticationError(ValueError):
    """Credentials were rejected by KinderClose."""


class SessionExpired(ValueError):
    """La sesión de KinderClose ha caducado y hay que volver a iniciar sesión."""


class KinderClose:
    """Cliente de KinderClose que reutiliza la sesión entre consultas.

    Solo inicia sesión cuando no hay sesión activa o cuando KinderClose la ha
    invalidado, en lugar de enviar la contraseña en cada consulta. Todas las
    redirecciones se siguen manualmente y solo dentro de ``BASE``.
    """

    MAX_REDIRECTS = 5

    def __init__(self, user, password, pupil_id="", pupil_name=""):
        self.user = user
        self.password = password
        self.pupil_id = pupil_id
        self.pupil_name = pupil_name
        self.session = requests.Session()
        self.logged_in = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self.logged_in = False
        self.session.close()

    @staticmethod
    def _check_url(url):
        parsed, base = urlparse(url), urlparse(BASE)
        if parsed.scheme != base.scheme or parsed.netloc != base.netloc:
            raise ValueError("Enlace de KinderClose no válido.")

    def _request(self, method, url, data=None):
        """Petición HTTP que no sale nunca de ``BASE``, ni siquiera por redirección.

        Las 307/308 conservarían el cuerpo (y con él la contraseña), así que cada
        salto se valida antes de seguirlo.
        """
        for _ in range(self.MAX_REDIRECTS + 1):
            self._check_url(url)
            response = self.session.request(method, url, data=data, timeout=30, allow_redirects=False)
            if response.is_redirect:
                url = urljoin(url, response.headers["Location"])
                if response.status_code not in (307, 308):
                    method, data = "GET", None
                continue
            response.raise_for_status()
            return response
        raise ValueError("KinderClose ha devuelto demasiadas redirecciones.")

    def get(self, url):
        response = self._request("GET", url)
        if "/auth/login" in response.url:
            self.logged_in = False
            raise SessionExpired("KinderClose requiere iniciar sesión de nuevo.")
        return response

    def login(self):
        user, password = self.user, self.password
        if not user or not password:
            raise ValueError("Faltan KINDERCLOSE_USER o KINDERCLOSE_PASSWORD.")
        # Sesión limpia: no reutilizar cookies de una sesión caducada.
        self.session.cookies.clear()
        self.logged_in = False
        login = self._request("GET", BASE + "/auth/login")
        token = BeautifulSoup(login.text, "html.parser").select_one('input[name="_token"]')
        if token is None:
            raise ValueError("No se encuentra el formulario de acceso.")
        response = self._request("POST", BASE + "/auth/login", data={"_token": token["value"], "email": user, "password": password})
        if "/auth/login" in response.url or BeautifulSoup(response.text, "html.parser").select_one('input[name="password"]'):
            raise AuthenticationError("KinderClose ha rechazado el inicio de sesión.")
        self.logged_in = True

    def fetch(self, limit=5, requested_date=None):
        if not self.logged_in:
            self.login()
            return self._fetch(limit, requested_date)
        try:
            return self._fetch(limit, requested_date)
        except SessionExpired:
            # La sesión reutilizada ha caducado: un único reintento con login nuevo.
            self.login()
            return self._fetch(limit, requested_date)

    def _fetch(self, limit, requested_date):
        listing = BeautifulSoup(self.get(BASE + "/familiar/alumno").text, "html.parser")
        pupils = {}
        for anchor in listing.select("a[href]"):
            url = urljoin(BASE, anchor["href"])
            match = re.fullmatch(re.escape(BASE) + r"/familiar/alumno/(\d+)", url)
            if match:
                pupils.setdefault(match[1], []).append(anchor.get_text(" ", strip=True))
        pupil_id = self.pupil_id.strip()
        if not pupil_id:
            name = normalize(self.pupil_name)
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
