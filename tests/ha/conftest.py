"""Fixtures comunes para las pruebas con Home Assistant, sin acceso a la red."""
import pytest

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kinderclose.const import CONF_PUPIL_ID, DOMAIN

USER_INPUT = {CONF_USERNAME: "familia@example.com", CONF_PASSWORD: "secreto", CONF_PUPIL_ID: "123"}

DATA = {
    "alumno_id": "123",
    "consultado_en": "2026-10-07T10:00:00+00:00",
    "fichas": [{
        "fecha": "2026-10-07",
        "url": "https://app.kinderclose.com/familiar/alumno/123/ficha/456",
        "presencia": {"ausente": "No", "hora_entrada": "09:00", "hora_salida": None},
        "comidas": {"desayuno": "Bien"},
        "sueno": [{"desde": "12:17", "hasta": "12:50"}],
        "sueno_minutos": 33,
        "deposiciones": [],
    }],
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def entry(hass):
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="123", title="KinderClose 123", data=USER_INPUT)
    config_entry.add_to_hass(hass)
    return config_entry
