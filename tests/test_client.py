"""Pruebas del cliente compartido, sin acceder a la red."""
import unittest
from unittest.mock import MagicMock, patch

from custom_components.kinderclose.client import AuthenticationError, KinderClose, SessionExpired
from test_kinderclose import fixture

BASE = "https://app.kinderclose.com"

LOGIN_FORM = '<input name="_token" value="csrf">'
LISTING = '<a href="/familiar/alumno/123">Alumno de prueba</a>'
PROFILE = '<a href="/familiar/alumno/123/ficha/456">Ver</a>'


def response(html, path, status=200, location=None):
    result = MagicMock()
    result.text = html
    result.url = path if path.startswith("http") else BASE + path
    result.status_code = status
    result.is_redirect = location is not None
    result.headers = {"Location": location} if location else {}
    return result


def happy_path():
    """Respuestas de una consulta completa sin login: listado, perfil y una ficha."""
    return [
        response(LISTING, "/familiar/alumno"),
        response(PROFILE, "/familiar/alumno/123"),
        response(fixture(), "/familiar/alumno/123/ficha/456"),
    ]


def login_responses():
    return [
        response(LOGIN_FORM, "/auth/login"),
        response("OK", "/familiar/alumno"),
    ]


def methods(session):
    return [call.args[0] for call in session.request.call_args_list]


def post_calls(session):
    return [call for call in session.request.call_args_list if call.args[0] == "POST"]


class ClientTests(unittest.TestCase):
    @patch("custom_components.kinderclose.client.requests.Session")
    @patch.dict("os.environ", {}, clear=True)
    def test_explicit_credentials_work_without_env_or_home_assistant(self, session_class):
        session = session_class.return_value
        session.request.side_effect = login_responses() + happy_path()
        with KinderClose("user", "password", "123") as client:
            result = client.fetch()
        self.assertEqual(result["alumno_id"], "123")
        self.assertEqual(result["fichas"][0]["fecha"], "2026-10-07")
        self.assertEqual(post_calls(session)[0].kwargs["data"], {"_token": "csrf", "email": "user", "password": "password"})
        for call in session.request.call_args_list:
            self.assertFalse(call.kwargs["allow_redirects"])
            self.assertEqual(call.kwargs["timeout"], 30)
        session.close.assert_called_once()

    @patch("custom_components.kinderclose.client.requests.Session")
    def test_invalid_credentials_raise_authentication_error_and_close(self, session_class):
        session = session_class.return_value
        session.request.side_effect = [response(LOGIN_FORM, "/auth/login"), response('<input name="password">', "/auth/login")]
        with self.assertRaises(AuthenticationError):
            with KinderClose("user", "bad", "123") as client:
                client.fetch()
        session.close.assert_called_once()

    @patch("custom_components.kinderclose.client.requests.Session")
    def test_unrelated_pupil_is_rejected(self, session_class):
        session = session_class.return_value
        session.request.side_effect = login_responses() + [response('<a href="/familiar/alumno/123">Alumno</a>', "/familiar/alumno")]
        with self.assertRaisesRegex(ValueError, "no aparece"):
            with KinderClose("user", "password", "999") as client:
                client.fetch()
        session.close.assert_called_once()


class SessionReuseTests(unittest.TestCase):
    @patch("custom_components.kinderclose.client.requests.Session")
    def test_second_fetch_reuses_session_without_sending_password(self, session_class):
        session = session_class.return_value
        session.request.side_effect = login_responses() + happy_path() + happy_path()
        client = KinderClose("user", "password", "123")
        client.fetch()
        client.fetch()
        self.assertEqual(len(post_calls(session)), 1)
        session.close.assert_not_called()

    @patch("custom_components.kinderclose.client.requests.Session")
    def test_expired_session_logs_in_again_once(self, session_class):
        session = session_class.return_value
        expired = response("", BASE + "/auth/login", status=302, location="/auth/login")
        session.request.side_effect = (
            login_responses() + happy_path()
            + [expired, response(LOGIN_FORM, "/auth/login")]  # listado → redirige al login
            + login_responses() + happy_path()
        )
        client = KinderClose("user", "password", "123")
        client.fetch()
        result = client.fetch()
        self.assertEqual(result["alumno_id"], "123")
        self.assertEqual(len(post_calls(session)), 2)
        session.cookies.clear.assert_called()

    @patch("custom_components.kinderclose.client.requests.Session")
    def test_session_expired_right_after_login_is_not_retried_forever(self, session_class):
        session = session_class.return_value
        session.request.side_effect = login_responses() + [response(LOGIN_FORM, "/auth/login")]
        with self.assertRaises(SessionExpired):
            KinderClose("user", "password", "123").fetch()
        self.assertEqual(len(post_calls(session)), 1)

    @patch("custom_components.kinderclose.client.requests.Session")
    def test_close_forces_new_login(self, session_class):
        session = session_class.return_value
        session.request.side_effect = login_responses() + happy_path() + login_responses() + happy_path()
        client = KinderClose("user", "password", "123")
        client.fetch()
        client.close()
        client.fetch()
        self.assertEqual(len(post_calls(session)), 2)


class RedirectTests(unittest.TestCase):
    @patch("custom_components.kinderclose.client.requests.Session")
    def test_same_host_redirect_is_followed_as_get(self, session_class):
        session = session_class.return_value
        session.request.side_effect = [
            response(LOGIN_FORM, "/auth/login"),
            response("", "/auth/login", status=302, location="/familiar/alumno"),
            response("OK", "/familiar/alumno"),
        ] + happy_path()
        KinderClose("user", "password", "123").fetch()
        calls = session.request.call_args_list
        self.assertEqual((calls[2].args[0], calls[2].args[1]), ("GET", BASE + "/familiar/alumno"))
        self.assertIsNone(calls[2].kwargs["data"])

    @patch("custom_components.kinderclose.client.requests.Session")
    def test_password_is_never_sent_to_foreign_host_on_307(self, session_class):
        session = session_class.return_value
        session.request.side_effect = [
            response(LOGIN_FORM, "/auth/login"),
            response("", "/auth/login", status=307, location="https://evil.example/collect"),
        ]
        with self.assertRaisesRegex(ValueError, "no válido"):
            KinderClose("user", "password", "123").fetch()
        self.assertEqual(methods(session), ["GET", "POST"])

    @patch("custom_components.kinderclose.client.requests.Session")
    def test_get_redirect_to_foreign_host_is_rejected(self, session_class):
        session = session_class.return_value
        session.request.side_effect = login_responses() + [
            response("", "/familiar/alumno", status=302, location="https://evil.example/familiar/alumno"),
        ]
        with self.assertRaisesRegex(ValueError, "no válido"):
            KinderClose("user", "password", "123").fetch()
        self.assertEqual(len(session.request.call_args_list), 3)

    @patch("custom_components.kinderclose.client.requests.Session")
    def test_https_downgrade_is_rejected(self, session_class):
        session = session_class.return_value
        session.request.side_effect = [response("", "/auth/login", status=301, location="http://app.kinderclose.com/auth/login")]
        with self.assertRaisesRegex(ValueError, "no válido"):
            KinderClose("user", "password", "123").fetch()

    @patch("custom_components.kinderclose.client.requests.Session")
    def test_redirect_loop_is_bounded(self, session_class):
        session = session_class.return_value
        session.request.return_value = response("", "/auth/login", status=302, location="/auth/login")
        with self.assertRaisesRegex(ValueError, "demasiadas redirecciones"):
            KinderClose("user", "password", "123").fetch()
        self.assertEqual(session.request.call_count, KinderClose.MAX_REDIRECTS + 1)


if __name__ == "__main__":
    unittest.main()
