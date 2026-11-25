"""Fixtures comunes para las pruebas con Home Assistant, sin acceso a la red."""
import pytest

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kinderclose.const import CONF_DEVICE_ID, CONF_PUPIL_ID, CONF_TOKEN, DOMAIN

CREDENTIALS = {CONF_USERNAME: "familia@example.com", CONF_PASSWORD: "secreto"}
ENTRY_DATA = {**CREDENTIALS, CONF_TOKEN: "tok-1", CONF_DEVICE_ID: 77, CONF_PUPIL_ID: "123"}

PUPILS = {
    "123": {"id": "123", "nombre": "Alumno", "nombre_completo": "Alumno De Prueba", "activo": True},
    "124": {"id": "124", "nombre": "Hermano", "nombre_completo": "Hermano De Prueba", "activo": True},
    "125": {"id": "125", "nombre": "Baja", "nombre_completo": "Baja De Prueba", "activo": False},
}

RECORD = {
    "fecha": "2026-10-07",
    "url": "https://app.kinderclose.com/familiar/alumno/123/ficha/456",
    "presencia": {"ausente": False, "ausencia_justificada": False, "hora_entrada": "09:00", "hora_salida": None, "hora_entrada_tarde": None, "hora_salida_tarde": None},
    "comidas": {"desayuno": "Todo", "primero": "Bastante", "segundo": None, "postre": None, "merienda": None},
    "sueno": [{"desde": "12:17", "hasta": "12:50"}],
    "sueno_minutos": 33,
    "deposiciones": [],
    "biberones": [{"hora": "10:00", "cantidad": 180}],
    "recordatorios": ["Pañales"],
    "control_esfinter": None,
}

DATA = {"alumno_id": "123", "alumno": "Alumno", "consultado_en": "2026-10-07T10:00:00+00:00", "ficha": RECORD}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def entry(hass):
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="123", title="KinderClose Alumno", data=ENTRY_DATA)
    config_entry.add_to_hass(hass)
    return config_entry
