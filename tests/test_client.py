"""Pruebas del cliente compartido, sin acceder a la red."""
import unittest
from unittest.mock import MagicMock, patch

from custom_components.kinderclose.client import AuthenticationError, KinderClose
from test_kinderclose import fixture

BASE = "https://app.kinderclose.com"


def response(html, path):
    result = MagicMock()
    result.text = html
    result.url = BASE + path
    return result


class ClientTests(unittest.TestCase):
    @patch("custom_components.kinderclose.client.requests.Session")
    @patch.dict("os.environ", {}, clear=True)
    def test_explicit_credentials_work_without_env_or_home_assistant(self, session_class):
        session = session_class.return_value
        session.get.side_effect = [
            response('<input name="_token" value="csrf">', "/auth/login"),
            response('<a href="/familiar/alumno/123">Alumno de prueba</a>', "/familiar/alumno"),
            response('<a href="/familiar/alumno/123/ficha/456">Ver</a>', "/familiar/alumno/123"),
            response(fixture(), "/familiar/alumno/123/ficha/456"),
        ]
        session.post.return_value = response("OK", "/familiar/alumno")
        result = KinderClose("user", "password", "123").fetch()
        self.assertEqual(result["alumno_id"], "123")
        self.assertEqual(result["fichas"][0]["fecha"], "2026-10-07")
        self.assertEqual(session.post.call_args.kwargs["data"], {"_token": "csrf", "email": "user", "password": "password"})
        session.close.assert_called_once()

    @patch("custom_components.kinderclose.client.requests.Session")
    def test_invalid_credentials_raise_authentication_error_and_close(self, session_class):
        session = session_class.return_value
        session.get.return_value = response('<input name="_token" value="csrf">', "/auth/login")
        session.post.return_value = response('<input name="password">', "/auth/login")
        with self.assertRaises(AuthenticationError):
            KinderClose("user", "bad", "123").fetch()
        session.close.assert_called_once()

    @patch("custom_components.kinderclose.client.requests.Session")
    def test_unrelated_pupil_is_rejected(self, session_class):
        session = session_class.return_value
        session.get.side_effect = [response('<input name="_token" value="csrf">', "/auth/login"), response('<a href="/familiar/alumno/123">Alumno</a>', "/familiar/alumno")]
        session.post.return_value = response("OK", "/familiar/alumno")
        with self.assertRaisesRegex(ValueError, "no aparece"):
            KinderClose("user", "password", "999").fetch()
        session.close.assert_called_once()
