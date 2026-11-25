"""Pruebas del cliente de la API y del parser, sin acceder a la red."""
import asyncio
from datetime import date, datetime, timedelta, timezone
import json
import unittest
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import aiohttp

from custom_components.kinderclose.client import (
    API, AuthenticationError, CannotConnect, KinderClose, MAX_RESPONSE_BYTES, ParseError, PupilNotFound, parse_date, parse_pupils, parse_record, parse_time,
)

MADRID = ZoneInfo("Europe/Madrid")
TODAY = date(2026, 11, 25)
LOGIN = {"userId": 9, "userName": "Familia", "deviceId": 77, "token": "tok-1", "centros": []}
PUPILS = [
    {"id": 123, "nombre": "Alumno", "apellidos": "De Prueba", "enabled": True},
    {"id": 124, "nombre": "Hermano", "apellidos": "De Prueba", "enabled": False},
]


def ficha(**overrides):
    """Ficha de la API con datos ficticios, en el formato de la app oficial."""
    data = {
        "id": 456, "alumno_id": 123, "fecha": "2026-11-24T23:00:00.000000Z",
        "ausente": 0, "ausencia_justificada": 0,
        "hora_entrada": "2026-11-25 08:55:00", "hora_salida": None, "hora_entrada_tarde": None, "hora_salida_tarde": None,
        "comida_desayuno": 4, "comida_primero": 3, "comida_segundo": 2, "comida_postre": 1, "comida_merienda": 0,
        "control_esfinter": -1,
        "lista_biberon": [{"hora_desde": "2026-11-25T10:00:00.000000Z", "cantidad": "180"}],
        "lista_dormir": [{"hora_desde": "2026-11-25 12:17:00", "hora_hasta": "2026-11-25 12:40:00"}, {"hora_desde": "14:00", "hora_hasta": "14:10"}],
        "lista_deposicion": [{"tipo": 1, "hora_desde": "2026-11-25 11:00:00", "info": "Normal"}, {"tipo": 2, "hora_desde": None, "info": ""}],
        "recordatorios": [2, {"id": 7, "label": "Crema"}],
        "editable": False,
    }
    data.update(overrides)
    return data


class FakeResponse:
    def __init__(self, data=None, status=200, raw=None):
        self.status = status
        self.body = raw if raw is not None else (b"" if data is None else json.dumps(data).encode())
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def iter_chunked(self, size):
        # Cede el control para que las consultas simultáneas se intercalen de verdad.
        await asyncio.sleep(0)
        for offset in range(0, len(self.body), size):
            yield self.body[offset:offset + size]


class FakeSession:
    """Responde por "MÉTODO /ruta" o "MÉTODO /ruta?fecha=...". Cada clave consume su lista y repite la última."""

    def __init__(self, routes):
        self.routes = {key: list(value) if isinstance(value, list) else [value] for key, value in routes.items()}
        self.calls = []
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        path = urlparse(url).path.removeprefix(urlparse(API).path)
        fecha = (kwargs.get("params") or {}).get("fecha")
        key = f"{method} {path}" + (f"?fecha={fecha}" if fecha else "")
        queue = self.routes.get(key, [FakeResponse(status=404)])
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, BaseException):
            raise item
        return item

    async def close(self):
        self.closed = True

    def paths(self):
        return [f"{m} {urlparse(u).path}" + (f"?fecha={k['params']['fecha']}" if (k.get('params') or {}).get("fecha") else "") for m, u, k in self.calls]


def routes(overrides=None):
    """Rutas de una cuenta válida; ``overrides`` sustituye o añade respuestas por "MÉTODO /ruta"."""
    result = {
        "POST /auth/login": FakeResponse(LOGIN),
        "GET /familiar/alumno": FakeResponse(PUPILS),
        "GET /familiar/alumno/123/ficha/null": FakeResponse(ficha()),
    }
    result.update(overrides or {})
    return result


def client(session, **kwargs):
    return KinderClose(session, "familia@example.com", "secreto", **kwargs)


class ParserTests(unittest.TestCase):
    def test_record_is_normalized(self):
        record = parse_record(ficha(), "123", MADRID)
        # Laravel envía la fecha en UTC: medianoche de Madrid es las 23:00 del día anterior.
        self.assertEqual(record["fecha"], "2026-11-25")
        self.assertEqual(record["url"], "https://app.kinderclose.com/familiar/alumno/123/ficha/456")
        self.assertEqual(record["presencia"], {"ausente": False, "ausencia_justificada": False, "hora_entrada": "08:55", "hora_salida": None, "hora_entrada_tarde": None, "hora_salida_tarde": None})
        self.assertEqual(record["comidas"], {"desayuno": "Todo", "primero": "Bastante", "segundo": "Poco", "postre": "Nada", "merienda": None})
        self.assertEqual(record["sueno"], [{"desde": "12:17", "hasta": "12:40"}, {"desde": "14:00", "hasta": "14:10"}])
        self.assertEqual(record["sueno_minutos"], 33)
        self.assertEqual(record["deposiciones"], [{"tipo": "Deposición", "hora": "11:00", "info": "Normal"}, {"tipo": "Pis", "hora": None, "info": None}])
        self.assertEqual(record["biberones"], [{"hora": "11:00", "cantidad": 180}])
        self.assertEqual(record["recordatorios"], ["Pañales", "Crema"])
        self.assertIsNone(record["control_esfinter"])

    def test_absence_and_flags_accept_strings_and_booleans(self):
        for value in (1, "1", True, "true"):
            self.assertTrue(parse_record(ficha(ausente=value), "123")["presencia"]["ausente"])
        for value in (0, "0", False, None, ""):
            self.assertFalse(parse_record(ficha(ausente=value), "123")["presencia"]["ausente"])

    def test_incomplete_or_missing_naps_give_unknown_sleep(self):
        self.assertIsNone(parse_record(ficha(lista_dormir=[{"hora_desde": "12:11", "hora_hasta": None}]), "123")["sueno_minutos"])
        self.assertIsNone(parse_record(ficha(lista_dormir=[]), "123")["sueno_minutos"])
        self.assertEqual(parse_record(ficha(lista_dormir=[{"hora_desde": "23:50", "hora_hasta": "00:20"}]), "123")["sueno_minutos"], 30)

    def test_missing_lists_and_unknown_values_do_not_fail(self):
        record = parse_record({"fecha": "2026-11-25", "comida_desayuno": 9, "lista_dormir": None, "recordatorios": None}, "123")
        self.assertIsNone(record["url"])
        self.assertIsNone(record["comidas"]["desayuno"])
        self.assertEqual((record["sueno"], record["deposiciones"], record["biberones"], record["recordatorios"]), ([], [], [], []))

    def test_record_without_valid_date_is_rejected(self):
        with self.assertRaises(ParseError):
            parse_record(ficha(fecha="mañana"), "123")

    def test_time_and_date_formats(self):
        self.assertEqual(parse_time("8:05"), "08:05")
        self.assertEqual(parse_time("08:05:59"), "08:05")
        self.assertEqual(parse_time("2026-07-01T06:30:00Z", MADRID), "08:30")  # horario de verano
        self.assertIsNone(parse_time("25:00"))
        self.assertIsNone(parse_time("--"))
        self.assertEqual(parse_date("2026-11-25"), date(2026, 11, 25))
        self.assertEqual(parse_date("2026-11-25 00:00:00"), date(2026, 11, 25))
        self.assertEqual(parse_date("2026-11-24T23:00:00Z", timezone.utc), date(2026, 11, 24))
        self.assertIsNone(parse_date(None))

    def test_pupils(self):
        pupils = parse_pupils(PUPILS)
        self.assertEqual(pupils["123"], {"id": "123", "nombre": "Alumno", "nombre_completo": "Alumno De Prueba", "activo": True})
        self.assertFalse(pupils["124"]["activo"])
        with self.assertRaises(ParseError):
            parse_pupils({"error": "x"})


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_logs_in_once_and_sends_token(self):
        session = FakeSession(routes())
        stored = []
        async with client(session, on_token=lambda *args: stored.append(args)) as api:
            result = await api.fetch("123", today=TODAY, tz=MADRID)
            await api.fetch("123", today=TODAY, tz=MADRID)
        self.assertEqual(result["alumno_id"], "123")
        self.assertEqual(result["alumno"], "Alumno")
        self.assertEqual(result["ficha"]["fecha"], "2026-11-25")
        self.assertEqual(stored, [("tok-1", 77)])
        method, url, kwargs = session.calls[0]
        self.assertEqual((method, url), ("POST", API + "/auth/login"))
        self.assertEqual(kwargs["json"], {"email": "familia@example.com", "password": "secreto", "provider": 1, "deviceName": "Home Assistant", "deviceType": 1, "appVersion": None})
        # Listado de alumnos solo en la primera consulta; después, una petición por consulta.
        self.assertEqual(session.paths()[1:], ["GET /api/v3/familiar/alumno", "GET /api/v3/familiar/alumno/123/ficha/null", "GET /api/v3/familiar/alumno/123/ficha/null"])
        for _, _, kwargs in session.calls:
            self.assertFalse(kwargs["allow_redirects"])
            self.assertEqual(kwargs["timeout"].total, 30)
        for _, _, kwargs in session.calls[1:]:
            self.assertEqual(kwargs["headers"]["token"], "tok-1")
            self.assertEqual(kwargs["params"]["device_id"], "77")
        self.assertTrue(session.closed)

    async def test_stored_token_skips_login(self):
        session = FakeSession(routes())
        await client(session, token="guardado", device_id=5).fetch("123", today=TODAY)
        self.assertNotIn("POST /api/v3/auth/login", session.paths())
        self.assertEqual(session.calls[0][2]["headers"]["token"], "guardado")

    async def test_expired_token_logs_in_again_once(self):
        session = FakeSession(routes({"GET /familiar/alumno": [FakeResponse(status=401), FakeResponse(PUPILS)]}))
        stored = []
        result = await client(session, token="viejo", device_id=5, on_token=lambda *a: stored.append(a)).fetch("123", today=TODAY, tz=MADRID)
        self.assertEqual(result["ficha"]["fecha"], "2026-11-25")
        self.assertEqual(stored, [("tok-1", 77)])
        self.assertEqual(session.paths().count("POST /api/v3/auth/login"), 1)

    async def test_token_rejected_right_after_login_is_a_connection_error(self):
        session = FakeSession(routes({"GET /familiar/alumno": FakeResponse(status=401)}))
        with self.assertRaises(CannotConnect):
            await client(session).fetch("123", today=TODAY)
        # Inicio de sesión inicial y una única renovación; no hay bucle de reintentos.
        self.assertEqual(session.paths().count("POST /api/v3/auth/login"), 2)

    async def test_concurrent_expiry_logs_in_once(self):
        session = FakeSession(routes({"GET /familiar/alumno/123/ficha/null": [FakeResponse(status=401), FakeResponse(status=401), FakeResponse(ficha())]}))
        api = client(session, token="viejo", device_id=5)
        api._pupils, api._pupils_at = parse_pupils(PUPILS), datetime.now(timezone.utc)
        results = await asyncio.gather(api.fetch("123", today=TODAY), api.fetch("123", today=TODAY))
        self.assertTrue(all(r["ficha"] for r in results))
        self.assertEqual(session.paths().count("POST /api/v3/auth/login"), 1)

    async def test_invalid_credentials(self):
        for status in (401, 422):
            with self.subTest(status=status):
                with self.assertRaises(AuthenticationError):
                    await client(FakeSession(routes({"POST /auth/login": FakeResponse({"error": {}}, status=status)}))).pupils()
        with self.assertRaises(AuthenticationError):
            await KinderClose(FakeSession(routes()), "", "").pupils()

    async def test_login_without_token_is_a_parse_error(self):
        with self.assertRaises(ParseError):
            await client(FakeSession(routes({"POST /auth/login": FakeResponse({"userId": 1})}))).pupils()

    async def test_network_errors_and_http_errors(self):
        for response in (aiohttp.ClientConnectionError(), TimeoutError(), FakeResponse(status=500), FakeResponse(status=429), FakeResponse(status=302)):
            with self.subTest(response=response):
                with self.assertRaises(CannotConnect):
                    await client(FakeSession(routes({"GET /familiar/alumno": response})), token="t", device_id=1).pupils()

    async def test_invalid_json_and_oversized_responses(self):
        for response in (FakeResponse(raw=b"<html>"), FakeResponse(raw=b"[" + b" " * MAX_RESPONSE_BYTES + b"]")):
            with self.subTest(size=len(response.body)):
                with self.assertRaises(ParseError):
                    await client(FakeSession(routes({"GET /familiar/alumno": response})), token="t", device_id=1).pupils()

    async def test_wrapped_responses_are_accepted(self):
        session = FakeSession(routes({"GET /familiar/alumno": FakeResponse({"data": PUPILS})}))
        self.assertIn("123", await client(session, token="t", device_id=1).pupils())

    async def test_unknown_or_invalid_pupil(self):
        for pupil_id in ("999", "../auth", ""):
            with self.subTest(pupil_id=pupil_id):
                with self.assertRaises(PupilNotFound):
                    await client(FakeSession(routes()), token="t", device_id=1).fetch(pupil_id, today=TODAY)
        with self.assertRaises(PupilNotFound):
            await client(FakeSession(routes({"GET /familiar/alumno/123/ficha/null": FakeResponse(status=403)})), token="t", device_id=1).fetch("123", today=TODAY)

    async def test_looks_back_to_the_latest_record_and_remembers_past_days(self):
        friday = TODAY - timedelta(days=4)
        session = FakeSession(routes({
            "GET /familiar/alumno/123/ficha/null": FakeResponse(status=404),
            f"GET /familiar/alumno/123/ficha/null?fecha={TODAY - timedelta(days=1)}": FakeResponse(None),
            f"GET /familiar/alumno/123/ficha/null?fecha={TODAY - timedelta(days=2)}": FakeResponse({"id": None, "fecha": "2026-11-23"}),
            f"GET /familiar/alumno/123/ficha/null?fecha={friday}": FakeResponse(ficha(fecha=friday.isoformat())),
        }))
        api = client(session, token="t", device_id=1)
        first = await api.fetch("123", today=TODAY)
        self.assertEqual(first["ficha"]["fecha"], friday.isoformat())
        before = len(session.calls)
        second = await api.fetch("123", today=TODAY)
        self.assertEqual(second["ficha"], first["ficha"])
        self.assertEqual(session.paths()[before:], ["GET /api/v3/familiar/alumno/123/ficha/null"])

    async def test_no_record_in_the_window_gives_none(self):
        session = FakeSession(routes({"GET /familiar/alumno/123/ficha/null": FakeResponse(status=404)}))
        result = await client(session, token="t", device_id=1).fetch("123", today=TODAY, lookback=3)
        self.assertIsNone(result["ficha"])
        self.assertEqual(len([p for p in session.paths() if "/ficha/" in p]), 3)

    async def test_logout_ignores_errors(self):
        session = FakeSession({"POST /auth/logout": aiohttp.ClientConnectionError()})
        api = client(session, token="t", device_id=1)
        await api.logout()
        self.assertIsNone(api.token)
        await api.logout()
        self.assertEqual(len(session.calls), 1)


if __name__ == "__main__":
    unittest.main()
