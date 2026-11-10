"""Pruebas del cliente compartido, sin acceder a la red."""
import asyncio
import gzip
import threading
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import aiohttp
from aiohttp import web

from custom_components.kinderclose import client as client_module
from custom_components.kinderclose.client import (
    AuthenticationError, CannotConnect, KinderClose, MAX_RESPONSE_BYTES, NoRecords, ParseError, PupilNotFound, SessionExpired,
)
from test_kinderclose import fixture

BASE = "https://app.kinderclose.com"

LOGIN_FORM = '<input name="_token" value="csrf">'
LISTING = '<a href="/familiar/alumno/123">Alumno de prueba</a><a href="/familiar/alumno/124">Hermano de prueba</a>'


def profile(pupil_id="123"):
    return f'<a href="/familiar/alumno/{pupil_id}/ficha/456">Ver</a>'


class FakeResponse:
    def __init__(self, html="", status=200, location=None):
        self.html = html
        self.status = status
        self.headers = {"Location": location} if location else {}
        self.charset = "utf-8"
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def iter_chunked(self, size):
        # Cede el control para que las consultas simultáneas se intercalen de verdad.
        await asyncio.sleep(0)
        data = self.html.encode("utf-8")
        for offset in range(0, len(data), size):
            yield data[offset:offset + size]

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(MagicMock(), (), status=self.status)


class FakeSession:
    """Responde por "MÉTODO /ruta". Cada ruta consume su lista en orden y repite la última respuesta."""

    def __init__(self, routes):
        self.routes = {key: list(value) if isinstance(value, list) else [value] for key, value in routes.items()}
        self.calls = []
        self.cookie_jar = MagicMock()
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        queue = self.routes[f"{method} {urlparse(url).path}"]
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, BaseException):
            raise item
        return item

    async def close(self):
        self.closed = True

    def methods(self):
        return [method for method, _, _ in self.calls]

    def posts(self):
        return [call for call in self.calls if call[0] == "POST"]


def routes(**overrides):
    """Rutas de una cuenta válida: login correcto, dos alumnos y una ficha cada uno."""
    result = {
        "GET /auth/login": FakeResponse(LOGIN_FORM),
        "POST /auth/login": FakeResponse(status=302, location="/inicio"),
        "GET /inicio": FakeResponse("OK"),
        "GET /familiar/alumno": FakeResponse(LISTING),
        "GET /familiar/alumno/123": FakeResponse(profile("123")),
        "GET /familiar/alumno/124": FakeResponse(profile("124")),
        "GET /familiar/alumno/123/ficha/456": FakeResponse(fixture()),
        "GET /familiar/alumno/124/ficha/456": FakeResponse(fixture()),
    }
    result.update(overrides)
    return result


def expired():
    """Respuesta de KinderClose cuando la sesión ha caducado: redirige al login."""
    return FakeResponse(status=302, location="/auth/login")


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_logs_in_and_parses_records(self):
        session = FakeSession(routes())
        async with KinderClose(session, "user", "password") as client:
            result = await client.fetch("123")
        self.assertEqual(result["alumno_id"], "123")
        self.assertEqual(result["fichas"][0]["fecha"], "2026-10-07")
        self.assertEqual(session.posts()[0][2]["data"], {"_token": "csrf", "email": "user", "password": "password"})
        for _, _, kwargs in session.calls:
            self.assertFalse(kwargs["allow_redirects"])
            self.assertEqual(kwargs["timeout"].total, 30)
        self.assertTrue(session.closed)

    async def test_pupil_can_be_resolved_by_name(self):
        session = FakeSession(routes())
        result = await KinderClose(session, "user", "password").fetch(pupil_name="hermano  DE prueba")
        self.assertEqual(result["alumno_id"], "124")

    async def test_invalid_credentials_raise_authentication_error_and_close(self):
        session = FakeSession(routes(**{"POST /auth/login": FakeResponse('<input name="password">')}))
        with self.assertRaises(AuthenticationError):
            async with KinderClose(session, "user", "bad") as client:
                await client.fetch("123")
        self.assertTrue(session.closed)

    async def test_unrelated_pupil_is_rejected(self):
        session = FakeSession(routes())
        with self.assertRaisesRegex(PupilNotFound, "no aparece"):
            await KinderClose(session, "user", "password").fetch("999")

    async def test_pupil_without_records_raises_no_records(self):
        session = FakeSession(routes(**{"GET /familiar/alumno/123": FakeResponse("")}))
        with self.assertRaises(NoRecords):
            await KinderClose(session, "user", "password").fetch("123")

    async def test_login_form_without_token_value_is_rejected_before_posting(self):
        session = FakeSession(routes(**{"GET /auth/login": FakeResponse('<input name="_token">')}))
        with self.assertRaises(ParseError):
            await KinderClose(session, "user", "password").fetch("123")
        self.assertEqual(session.methods(), ["GET"])

    async def test_html_is_parsed_outside_the_event_loop(self):
        """Analizar HTML es costoso: nunca debe bloquear el bucle de Home Assistant."""
        loop_thread = threading.get_ident()
        parse_threads = []
        real_soup = client_module.BeautifulSoup

        def recording_soup(*args, **kwargs):
            parse_threads.append(threading.get_ident())
            return real_soup(*args, **kwargs)

        with patch.object(client_module, "BeautifulSoup", recording_soup):
            await KinderClose(FakeSession(routes()), "user", "password").fetch("123")
        # Formulario de acceso, respuesta del login, listado, perfil y una ficha.
        self.assertEqual(len(parse_threads), 5)
        self.assertNotIn(loop_thread, parse_threads)


class NetworkErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_oversized_response_is_rejected(self):
        session = FakeSession(routes(**{"GET /auth/login": FakeResponse("x" * (MAX_RESPONSE_BYTES + 1))}))
        with self.assertRaisesRegex(ParseError, "tamaño permitido"):
            await KinderClose(session, "user", "password").fetch("123")
        self.assertEqual(session.methods(), ["GET"])

    async def test_compressed_response_limit_applies_after_decompression(self):
        async def handler(request):
            return web.Response(body=gzip.compress(b"x" * (MAX_RESPONSE_BYTES + 1)), headers={"Content-Encoding": "gzip"})

        app = web.Application()
        app.router.add_get("/", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        self.addAsyncCleanup(runner.cleanup)
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = runner.addresses[0][1]
        async with aiohttp.ClientSession() as session:
            client = KinderClose(session, "user", "password")
            client._check_url = MagicMock()
            with self.assertRaisesRegex(ParseError, "tamaño permitido"):
                await client._request("GET", f"http://127.0.0.1:{port}/")

    async def test_network_errors_become_cannot_connect(self):
        for error in (aiohttp.ClientConnectionError(), TimeoutError()):
            with self.subTest(error=type(error).__name__):
                session = FakeSession(routes(**{"GET /auth/login": error}))
                with self.assertRaises(CannotConnect):
                    await KinderClose(session, "user", "password").fetch("123")

    async def test_http_error_becomes_cannot_connect(self):
        session = FakeSession(routes(**{"GET /familiar/alumno": FakeResponse(status=500)}))
        with self.assertRaises(CannotConnect):
            await KinderClose(session, "user", "password").fetch("123")


class SessionReuseTests(unittest.IsolatedAsyncioTestCase):
    async def test_second_fetch_reuses_session_without_sending_password(self):
        session = FakeSession(routes())
        client = KinderClose(session, "user", "password")
        await client.fetch("123")
        await client.fetch("123")
        self.assertEqual(len(session.posts()), 1)
        self.assertFalse(session.closed)

    async def test_simultaneous_fetches_of_two_pupils_share_one_login(self):
        session = FakeSession(routes())
        client = KinderClose(session, "user", "password")
        first, second = await asyncio.gather(client.fetch("123"), client.fetch("124"))
        self.assertEqual((first["alumno_id"], second["alumno_id"]), ("123", "124"))
        self.assertEqual(len(session.posts()), 1)

    async def test_expired_session_logs_in_again_once(self):
        session = FakeSession(routes(**{"GET /familiar/alumno": [FakeResponse(LISTING), expired(), FakeResponse(LISTING)]}))
        client = KinderClose(session, "user", "password")
        await client.fetch("123")
        result = await client.fetch("123")
        self.assertEqual(result["alumno_id"], "123")
        self.assertEqual(len(session.posts()), 2)
        session.cookie_jar.clear.assert_called()

    async def test_simultaneous_expiry_renews_the_session_only_once(self):
        session = FakeSession(routes(**{"GET /familiar/alumno": [FakeResponse(LISTING), expired(), expired(), FakeResponse(LISTING)]}))
        client = KinderClose(session, "user", "password")
        await client.fetch("123")
        await asyncio.gather(client.fetch("123"), client.fetch("124"))
        self.assertEqual(len(session.posts()), 2)

    async def test_session_that_keeps_expiring_is_not_retried_forever(self):
        session = FakeSession(routes(**{"GET /familiar/alumno": expired()}))
        with self.assertRaises(SessionExpired):
            await KinderClose(session, "user", "password").fetch("123")
        self.assertEqual(len(session.posts()), 2)

    async def test_close_forces_new_login(self):
        session = FakeSession(routes())
        client = KinderClose(session, "user", "password")
        await client.fetch("123")
        await client.close()
        await client.fetch("123")
        self.assertEqual(len(session.posts()), 2)


class RedirectTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_host_redirect_is_followed_as_get(self):
        session = FakeSession(routes())
        await KinderClose(session, "user", "password").fetch("123")
        method, url, kwargs = session.calls[2]
        self.assertEqual((method, url), ("GET", BASE + "/inicio"))
        self.assertIsNone(kwargs["data"])

    async def test_password_is_never_sent_to_foreign_host_on_307(self):
        session = FakeSession(routes(**{"POST /auth/login": FakeResponse(status=307, location="https://evil.example/collect")}))
        with self.assertRaisesRegex(ValueError, "no válido"):
            await KinderClose(session, "user", "password").fetch("123")
        self.assertEqual(session.methods(), ["GET", "POST"])

    async def test_get_redirect_to_foreign_host_is_rejected(self):
        session = FakeSession(routes(**{"GET /familiar/alumno": FakeResponse(status=302, location="https://evil.example/familiar/alumno")}))
        with self.assertRaisesRegex(ValueError, "no válido"):
            await KinderClose(session, "user", "password").fetch("123")
        self.assertEqual(len(session.calls), 4)

    async def test_https_downgrade_is_rejected(self):
        session = FakeSession(routes(**{"GET /auth/login": FakeResponse(status=301, location="http://app.kinderclose.com/auth/login")}))
        with self.assertRaisesRegex(ValueError, "no válido"):
            await KinderClose(session, "user", "password").fetch("123")

    async def test_redirect_loop_is_bounded(self):
        session = FakeSession(routes(**{"GET /auth/login": FakeResponse(status=302, location="/auth/login")}))
        with self.assertRaisesRegex(ValueError, "demasiadas redirecciones"):
            await KinderClose(session, "user", "password").fetch("123")
        self.assertEqual(len(session.calls), KinderClose.MAX_REDIRECTS + 1)


if __name__ == "__main__":
    unittest.main()
