"""Cliente de la API JSON de KinderClose (v3), independiente de Home Assistant.

KinderClose no publica una API documentada. Los endpoints, cabeceras y campos de
este módulo se han obtenido por ingeniería inversa de la app oficial «KinderClose
Familiar» (Ionic/Angular), que usa la misma API; ver docs/api.md. Sustituye al
análisis del HTML de la web: una consulta normal es una única petición JSON.
"""
import asyncio
from datetime import date, datetime, time, timedelta, timezone
import json
import re

import aiohttp

BASE = "https://app.kinderclose.com"
API = BASE + "/api/v3"
TIMEOUT = aiohttp.ClientTimeout(total=30)
MAX_RESPONSE_BYTES = 1024 * 1024  # Límite del contenido descomprimido; una ficha ocupa unos pocos KiB.
# Días que se retrocede, como máximo, para encontrar la última ficha (cubre fines de semana y puentes).
LOOKBACK_DAYS = 7
# Cada cuánto se vuelve a comprobar que el alumno sigue en la cuenta.
PUPILS_TTL = timedelta(hours=6)

# Valores que la app envía al iniciar sesión (enumeraciones de la app oficial).
PROVIDER_LOCAL = 1
DEVICE_TYPE_WEB = 1
DEVICE_NAME = "Home Assistant"

# Textos de la app oficial para los valores numéricos de la ficha.
MEALS = ("desayuno", "primero", "segundo", "postre", "merienda")
FOOD = {1: "Nada", 2: "Poco", 3: "Bastante", 4: "Todo"}
DIAPER = {1: "Deposición", 2: "Pis"}
REMINDERS = {1: "Toallitas", 2: "Pañales", 3: "Agua", 4: "Muda"}
YES_NO = {0: "No", 1: "Sí"}
TIME = re.compile(r"(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?")


class AuthenticationError(ValueError):
    """KinderClose ha rechazado las credenciales."""


class CannotConnect(Exception):
    """KinderClose no responde o ha devuelto un error HTTP."""


class ParseError(ValueError):
    """La respuesta de KinderClose no tiene el formato esperado."""


class PupilNotFound(ValueError):
    """El alumno configurado no está en la cuenta."""


class SessionExpired(Exception):
    """El token ya no es válido y hay que volver a iniciar sesión."""


# Normalización de valores. La API devuelve números, cadenas o booleanos según el
# campo; las funciones toleran las variantes y devuelven None si no hay dato.


def _int(value):
    if isinstance(value, bool):
        return int(value)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _flag(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "si", "sí", "s", "yes")
    return bool(value)


def _text(value):
    text = str(value).strip() if value is not None else ""
    return text if text not in ("", "--") else None


def _local(value, tz):
    """Fecha y hora de un texto ISO, en la zona ``tz`` si trae zona; ``None`` si no lo es."""
    text = _text(value)
    if text is None:
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is not None:
        moment = moment.astimezone(tz)
    return moment


def parse_time(value, tz=None):
    """Hora ``HH:MM`` de una hora suelta (``08:30:00``) o de una fecha y hora ISO."""
    moment = _local(value, tz)
    if moment is not None:
        return moment.strftime("%H:%M")
    match = TIME.fullmatch(_text(value) or "")
    if match and int(match[1]) < 24:
        return f"{int(match[1]):02d}:{match[2]}"
    return None


def parse_date(value, tz=None):
    """Fecha de la ficha. Laravel serializa las fechas en UTC: se convierten a ``tz``."""
    moment = _local(value, tz)
    if moment is not None:
        return moment.date()
    try:
        return date.fromisoformat((_text(value) or "")[:10])
    except ValueError:
        return None


def _minutes(start, end):
    """Minutos entre dos horas ``HH:MM``, admitiendo el cruce de medianoche."""
    first, second = (datetime.combine(date.min, time.fromisoformat(value)) for value in (start, end))
    return int((second - first).total_seconds() // 60) % (24 * 60)


def _items(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _reminder(item):
    if isinstance(item, dict):
        return _text(item.get("label")) or REMINDERS.get(_int(item.get("id")))
    return REMINDERS.get(_int(item))


def parse_record(data, pupil_id, tz=None):
    """Convierte una ficha de la API en el diccionario que usan los sensores."""
    day = parse_date(data.get("fecha"), tz)
    if day is None:
        raise ParseError("La ficha de KinderClose no tiene una fecha válida.")
    naps = [{"desde": parse_time(n.get("hora_desde"), tz), "hasta": parse_time(n.get("hora_hasta"), tz)} for n in _items(data.get("lista_dormir"))]
    complete = bool(naps) and all(n["desde"] and n["hasta"] for n in naps)
    record_id = _int(data.get("id"))
    return {
        "fecha": day.isoformat(),
        "url": f"{BASE}/familiar/alumno/{pupil_id}/ficha/{record_id}" if record_id is not None else None,
        "presencia": {
            "ausente": _flag(data.get("ausente")),
            "ausencia_justificada": _flag(data.get("ausencia_justificada")),
            **{key: parse_time(data.get(key), tz) for key in ("hora_entrada", "hora_salida", "hora_entrada_tarde", "hora_salida_tarde")},
        },
        "comidas": {meal: FOOD.get(_int(data.get("comida_" + meal))) for meal in MEALS},
        "sueno": naps,
        "sueno_minutos": sum(_minutes(n["desde"], n["hasta"]) for n in naps) if complete else None,
        "deposiciones": [
            {"tipo": DIAPER.get(_int(d.get("tipo"))), "hora": parse_time(d.get("hora_desde"), tz), "info": _text(d.get("info"))}
            for d in _items(data.get("lista_deposicion"))
        ],
        "biberones": [{"hora": parse_time(b.get("hora_desde"), tz), "cantidad": _int(b.get("cantidad"))} for b in _items(data.get("lista_biberon"))],
        "recordatorios": [label for label in map(_reminder, data.get("recordatorios") or []) if label],
        "control_esfinter": YES_NO.get(_int(data.get("control_esfinter"))),
    }


def parse_pupils(data):
    """Alumnos de la cuenta: ``{id: {"id", "nombre", "nombre_completo", "activo"}}``."""
    if not isinstance(data, list):
        raise ParseError("KinderClose ha devuelto un listado de alumnos inesperado.")
    pupils = {}
    for item in _items(data):
        pupil_id = _int(item.get("id"))
        if pupil_id is None:
            continue
        first = _text(item.get("nombre")) or ""
        full = " ".join(part for part in (first, _text(item.get("apellidos"))) if part)
        pupils[str(pupil_id)] = {"id": str(pupil_id), "nombre": first or str(pupil_id), "nombre_completo": full or str(pupil_id), "activo": item.get("enabled", True) is not False}
    return pupils


def _unwrap(data):
    """Algunos recursos de Laravel envuelven la respuesta en ``{"data": ...}``."""
    if isinstance(data, dict) and "data" in data and set(data) <= {"data", "meta", "links"}:
        return data["data"]
    return data


class KinderClose:
    """Cliente asíncrono de una cuenta de KinderClose, compartible entre sus alumnos.

    El inicio de sesión devuelve un token de dispositivo que se reutiliza mientras
    KinderClose lo acepte; ``on_token`` permite guardarlo para no registrar un
    dispositivo nuevo en cada reinicio. Un candado evita inicios de sesión
    simultáneos y, si el token caduca, se renueva una sola vez. Las fichas de días
    anteriores se guardan en memoria: en una consulta normal solo se pide la de hoy.
    El cliente es dueño de ``session`` y la cierra en ``close``.
    """

    def __init__(self, session, user, password, token=None, device_id=None, on_token=None):
        self.session = session
        self.user = user
        self.password = password
        self.token = token
        self.device_id = device_id
        self.on_token = on_token
        self._login_lock = asyncio.Lock()
        self._generation = 0
        self._pupils = None
        self._pupils_at = None
        self._history = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def close(self):
        await self.session.close()

    async def _request(self, method, path, params=None, payload=None, auth=True):
        """Devuelve ``(estado, json)``. Nunca sigue redirecciones: la API no las usa."""
        headers = {"Accept": "application/json"}
        params = dict(params or {})
        if auth:
            headers["token"] = self.token
            params["device_id"] = str(self.device_id)
        try:
            async with self.session.request(
                method, API + path, params=params or None, json=payload, headers=headers, allow_redirects=False, timeout=TIMEOUT
            ) as response:
                body = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise ParseError("La respuesta de KinderClose supera el tamaño permitido.")
                status = response.status
        except (aiohttp.ClientError, TimeoutError) as error:
            raise CannotConnect("No se puede conectar con KinderClose.") from error
        if not 200 <= status < 300:
            return status, None
        try:
            return status, _unwrap(json.loads(body)) if body.strip() else None
        except (UnicodeDecodeError, ValueError) as error:
            raise ParseError("KinderClose no ha devuelto JSON válido.") from error

    @staticmethod
    def _raise_for_status(status):
        if status == 429:
            raise CannotConnect("KinderClose limita el número de peticiones; se reintentará más tarde.")
        if not 200 <= status < 300:
            raise CannotConnect(f"KinderClose ha respondido con el estado HTTP {status}.")

    async def _get(self, path, params=None):
        """GET autenticado; ``None`` si el recurso no existe (404)."""
        status, data = await self._request("GET", path, params)
        if status == 401:
            raise SessionExpired
        if status == 404:
            return None
        if status == 403:
            raise PupilNotFound("La cuenta no tiene acceso a este alumno.")
        self._raise_for_status(status)
        return data

    async def _login(self):
        if not self.user or not self.password:
            raise AuthenticationError("Faltan el usuario o la contraseña de KinderClose.")
        payload = {
            "email": self.user.strip(), "password": self.password, "provider": PROVIDER_LOCAL,
            "deviceName": DEVICE_NAME, "deviceType": DEVICE_TYPE_WEB, "appVersion": None,
        }
        status, data = await self._request("POST", "/auth/login", payload=payload, auth=False)
        if status in (400, 401, 403, 422):
            raise AuthenticationError("KinderClose ha rechazado el inicio de sesión.")
        self._raise_for_status(status)
        if not isinstance(data, dict) or not data.get("token") or data.get("deviceId") is None:
            raise ParseError("KinderClose no ha devuelto un token de sesión.")
        self.token, self.device_id = str(data["token"]), data["deviceId"]
        self._generation += 1
        if self.on_token:
            self.on_token(self.token, self.device_id)

    async def _ensure_login(self, expired=None):
        """Inicia sesión si hace falta y devuelve la generación del token vigente.

        ``expired`` es la generación que ha caducado: si otra consulta ya la ha
        renovado mientras se esperaba el candado, se reutiliza el token nuevo.
        """
        async with self._login_lock:
            if not self.token or self._generation == expired:
                await self._login()
            return self._generation

    async def _call(self, method, *args):
        generation = await self._ensure_login()
        try:
            return await method(*args)
        except SessionExpired:
            await self._ensure_login(expired=generation)
        try:
            return await method(*args)
        except SessionExpired as error:
            raise CannotConnect("KinderClose rechaza la sesión recién iniciada.") from error

    async def pupils(self):
        """Alumnos de la cuenta (inicia sesión si hace falta)."""
        return await self._call(self._load_pupils)

    async def _load_pupils(self):
        self._pupils = parse_pupils(await self._get("/familiar/alumno"))
        self._pupils_at = datetime.now(timezone.utc)
        return self._pupils

    async def fetch(self, pupil_id, today=None, tz=None, lookback=LOOKBACK_DAYS):
        """Última ficha del alumno en los últimos ``lookback`` días, o ``None`` si no hay.

        ``today`` y ``tz`` son la fecha y la zona horaria locales (las de Home
        Assistant); por defecto, las del sistema.
        """
        pupil_id = str(pupil_id).strip()
        if not pupil_id.isdigit():
            raise PupilNotFound("El ID del alumno no es válido.")
        return await self._call(self._fetch, pupil_id, today or date.today(), tz, lookback)

    async def _fetch(self, pupil_id, today, tz, lookback):
        stale = self._pupils is None or datetime.now(timezone.utc) - self._pupils_at > PUPILS_TTL
        if stale or pupil_id not in self._pupils:
            await self._load_pupils()
        if pupil_id not in self._pupils:
            raise PupilNotFound("El alumno configurado no aparece en esta cuenta.")
        # La ficha del día: ficha/null sin fecha es lo que pide la app al abrirla.
        record = await self._record(pupil_id, None, tz)
        oldest = today - timedelta(days=lookback - 1)
        self._history = {key: value for key, value in self._history.items() if key[1] >= oldest}
        day = today
        while record is None and day > oldest:
            day -= timedelta(days=1)
            # Las fichas de días pasados no cambian: se piden una vez y se recuerdan.
            if (pupil_id, day) not in self._history:
                self._history[(pupil_id, day)] = await self._record(pupil_id, day, tz)
            record = self._history[(pupil_id, day)]
        return {
            "alumno_id": pupil_id,
            "alumno": self._pupils[pupil_id]["nombre"],
            "consultado_en": datetime.now(timezone.utc).isoformat(),
            "ficha": record,
        }

    async def _record(self, pupil_id, day, tz):
        params = {"fecha": day.isoformat()} if day else None
        data = await self._get(f"/familiar/alumno/{pupil_id}/ficha/null", params)
        # Sin ficha: 404, cuerpo vacío o una ficha sin guardar (id nulo).
        if not isinstance(data, dict) or not data.get("fecha") or ("id" in data and data["id"] is None):
            return None
        return parse_record(data, pupil_id, tz)

    async def logout(self):
        """Cierra la sesión del dispositivo en KinderClose. Los errores se ignoran."""
        if not self.token:
            return
        try:
            await self._request("POST", "/auth/logout", payload={})
        except (CannotConnect, ParseError):
            pass
        self.token = None
