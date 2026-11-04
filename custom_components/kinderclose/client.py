"""Cliente compartido de KinderClose, independiente de Home Assistant."""
import asyncio
from datetime import date, datetime, timezone
import re
import unicodedata
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

BASE = "https://app.kinderclose.com"
TIMEOUT = aiohttp.ClientTimeout(total=30)
REDIRECT_STATUSES = (301, 302, 303, 307, 308)
# Fechas en formato ISO (2026-10-07) o español (7/10/2026).
DATE = re.compile(r"\b(?:(\d{4})-(\d{2})-(\d{2})|(\d{1,2})/(\d{1,2})/(\d{4}))\b")


def normalize(value):
    return " ".join(unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower().split())


def nullable(value):
    return value.strip() if value.strip() not in ("", "--") else None


class ParseError(ValueError):
    """La página de KinderClose no tiene la estructura esperada."""


class PupilNotFound(ValueError):
    """El alumno configurado no se puede identificar en la cuenta."""


class NoRecords(ValueError):
    """El alumno existe pero todavía no tiene fichas."""


class CannotConnect(Exception):
    """KinderClose no responde o ha devuelto un error HTTP."""


def dates_in(text):
    """Fechas válidas distintas del texto, en orden de aparición."""
    found = []
    for match in DATE.finditer(text):
        year, month, day = match.group(1, 2, 3) if match[1] else match.group(6, 5, 4)
        try:
            value = date(int(year), int(month), int(day))
        except ValueError:
            continue
        if value not in found:
            found.append(value)
    return found


def record_date(soup, html):
    """Fecha de la ficha, de la fuente más fiable a la menos fiable.

    1. ``defaultDate`` del calendario de la página.
    2. La fecha de los encabezados, si solo hay una.
    3. La fecha de todo el texto, si solo hay una.

    Si una fuente contiene varias fechas distintas (por ejemplo, la de nacimiento
    del alumno) se considera ambigua: se rechaza la ficha antes que mostrar una
    fecha equivocada.
    """
    match = re.search(r"defaultDate:\s*['\"](\d{4}-\d{2}-\d{2})", html)
    calendar = dates_in(match[1]) if match else []
    if calendar:
        return calendar[0]
    headings = " ".join(tag.get_text(" ", strip=True) for tag in soup.select("title, h1, h2, h3, h4, .page-header"))
    for text in (headings, soup.get_text(" ")):
        found = dates_in(text)
        if len(found) == 1:
            return found[0]
    raise ParseError("No se ha podido identificar sin ambigüedad la fecha de la ficha.")


def parse_record(html, url):
    soup = BeautifulSoup(html, "html.parser")
    panels = {}
    for panel in soup.select(".panel"):
        heading = panel.select_one(".panel-title")
        if heading:
            panels[normalize(heading.get_text(" ", strip=True))] = panel
    if not {"presencia", "comidas", "deposicion"}.issubset(panels):
        raise ParseError("La ficha no contiene los paneles esperados; puede haber cambiado la web.")
    record = {"fecha": record_date(soup, html).isoformat(), "url": url}
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
        raise ParseError("No se ha podido interpretar la asistencia.")
    record["sueno"] = []
    if "dormir" in panels:
        for row in panels["dormir"].select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) == 2:
                record["sueno"].append(dict(zip(("desde", "hasta"), (nullable(c.get_text(strip=True)) for c in cells), strict=True)))
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
            record["deposiciones"].append(dict(zip(("tipo", "hora", "info"), (nullable(c.get_text(" ", strip=True)) for c in cells), strict=True)))
    return record


class AuthenticationError(ValueError):
    """Credentials were rejected by KinderClose."""


class SessionExpired(ValueError):
    """La sesión de KinderClose ha caducado y hay que volver a iniciar sesión."""


class KinderClose:
    """Cliente asíncrono de una cuenta de KinderClose, compartible entre sus alumnos.

    Reutiliza la sesión entre consultas y solo inicia sesión cuando no hay sesión
    activa o KinderClose la ha invalidado, en lugar de enviar la contraseña en cada
    consulta. Un candado evita que varias consultas simultáneas inicien sesión a la
    vez. Todas las redirecciones se siguen manualmente y solo dentro de ``BASE``.
    El cliente es dueño de ``session`` y la cierra en ``close``.
    """

    MAX_REDIRECTS = 5

    def __init__(self, session, user, password):
        self.session = session
        self.user = user
        self.password = password
        self.logged_in = False
        self._login_lock = asyncio.Lock()
        self._generation = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def close(self):
        self.logged_in = False
        await self.session.close()

    @staticmethod
    def _check_url(url):
        parsed, base = urlparse(url), urlparse(BASE)
        if parsed.scheme != base.scheme or parsed.netloc != base.netloc:
            raise ValueError("Enlace de KinderClose no válido.")

    async def _request(self, method, url, data=None):
        """Devuelve ``(url_final, html)`` sin salir nunca de ``BASE``, ni siquiera por redirección.

        Las 307/308 conservarían el cuerpo (y con él la contraseña), así que cada
        salto se valida antes de seguirlo.
        """
        for _ in range(self.MAX_REDIRECTS + 1):
            self._check_url(url)
            try:
                async with self.session.request(method, url, data=data, allow_redirects=False, timeout=TIMEOUT) as response:
                    location = response.headers.get("Location") if response.status in REDIRECT_STATUSES else None
                    if location is None:
                        response.raise_for_status()
                        return url, await response.text()
            except (aiohttp.ClientError, TimeoutError) as error:
                raise CannotConnect("No se puede conectar con KinderClose.") from error
            if response.status not in (307, 308):
                method, data = "GET", None
            url = urljoin(url, location)
        raise ValueError("KinderClose ha devuelto demasiadas redirecciones.")

    async def _get(self, url):
        final_url, html = await self._request("GET", url)
        if "/auth/login" in final_url:
            # No se toca logged_in: _ensure_login decide por generación si hay que renovar.
            raise SessionExpired("KinderClose requiere iniciar sesión de nuevo.")
        return html

    async def _login(self):
        user, password = self.user, self.password
        if not user or not password:
            raise ValueError("Faltan el usuario o la contraseña de KinderClose.")
        # Sesión limpia: no reutilizar cookies de una sesión caducada.
        self.session.cookie_jar.clear()
        self.logged_in = False
        _, html = await self._request("GET", BASE + "/auth/login")
        token = BeautifulSoup(html, "html.parser").select_one('input[name="_token"]')
        if token is None or not token.get("value"):
            raise ParseError("No se encuentra el formulario de acceso.")
        final_url, html = await self._request("POST", BASE + "/auth/login", data={"_token": token["value"], "email": user, "password": password})
        if "/auth/login" in final_url or BeautifulSoup(html, "html.parser").select_one('input[name="password"]'):
            raise AuthenticationError("KinderClose ha rechazado el inicio de sesión.")
        self.logged_in = True
        self._generation += 1

    async def _ensure_login(self, expired=None):
        """Inicia sesión si hace falta y devuelve la generación de la sesión vigente.

        ``expired`` es la generación que ha caducado: si otra consulta ya la ha
        renovado mientras se esperaba el candado, se reutiliza la nueva.
        """
        async with self._login_lock:
            if not self.logged_in or self._generation == expired:
                await self._login()
            return self._generation

    async def fetch(self, pupil_id="", pupil_name="", limit=5):
        generation = await self._ensure_login()
        try:
            return await self._fetch(pupil_id, pupil_name, limit)
        except SessionExpired:
            # La sesión ha caducado: un único reintento con la sesión renovada.
            await self._ensure_login(expired=generation)
            return await self._fetch(pupil_id, pupil_name, limit)

    async def _fetch(self, pupil_id, pupil_name, limit):
        listing = BeautifulSoup(await self._get(BASE + "/familiar/alumno"), "html.parser")
        pupils = {}
        for anchor in listing.select("a[href]"):
            url = urljoin(BASE, anchor["href"])
            match = re.fullmatch(re.escape(BASE) + r"/familiar/alumno/(\d+)", url)
            if match:
                pupils.setdefault(match[1], []).append(anchor.get_text(" ", strip=True))
        pupil_id = pupil_id.strip()
        if not pupil_id:
            name = normalize(pupil_name)
            matches = [key for key, names in pupils.items() if name and any(normalize(n) == name for n in names)]
            if len(matches) != 1:
                raise PupilNotFound("El nombre no identifica un único alumno. Configura el ID del alumno.")
            pupil_id = matches[0]
        if pupil_id not in pupils:
            raise PupilNotFound("El alumno configurado no aparece en esta cuenta.")
        pupil_url = BASE + "/familiar/alumno/" + pupil_id
        profile = BeautifulSoup(await self._get(pupil_url), "html.parser")
        links = list(dict.fromkeys(urljoin(BASE, a["href"]) for a in profile.select("a[href]") if re.fullmatch(re.escape(pupil_url) + r"/ficha/\d+", urljoin(BASE, a["href"]))))
        if not links:
            raise NoRecords("El alumno todavía no tiene fichas disponibles.")
        records = [parse_record(await self._get(url), url) for url in links[:limit]]
        records.sort(key=lambda r: r["fecha"], reverse=True)
        return {"alumno_id": pupil_id, "consultado_en": datetime.now(timezone.utc).isoformat(), "fichas": records}
