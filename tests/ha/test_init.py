"""Pruebas de carga, sensores, privacidad del historial y descarga de la integración."""
from unittest.mock import patch

import requests

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState

from conftest import DATA
from custom_components.kinderclose.client import AuthenticationError
from custom_components.kinderclose.sensor import KinderCloseSensor

FETCH = "custom_components.kinderclose.client.KinderClose.fetch"
CLOSE = "custom_components.kinderclose.client.KinderClose.close"


async def test_setup_creates_sensors_and_unload_closes_session(hass, entry):
    with patch(FETCH, return_value=DATA), patch(CLOSE) as close:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        assert hass.states.get("sensor.kinderclose_123_ultima_ficha").state == "2026-10-07"
        assert hass.states.get("sensor.kinderclose_123_asistencia").state == "presente"
        assert hass.states.get("sensor.kinderclose_123_entrada").state == "09:00"
        assert hass.states.get("sensor.kinderclose_123_salida").state == "unknown"
        assert hass.states.get("sensor.kinderclose_123_sueno").state == "33"
        assert hass.states.get("sensor.kinderclose_123_deposiciones").state == "0"
        assert hass.states.get("sensor.kinderclose_123_asistencia").attributes["friendly_name"] == "KinderClose 123 Attendance"

        ultima = hass.states.get("sensor.kinderclose_123_ultima_ficha")
        assert ultima.attributes["fichas"] == DATA["fichas"]
        assert ultima.attributes["url_ficha"] == DATA["fichas"][0]["url"]

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    close.assert_called_once()
    assert entry.state is ConfigEntryState.NOT_LOADED


def test_detailed_minor_data_is_not_recorded():
    assert {"fichas", "sesiones", "detalles", "url_ficha", "consultado_en"} <= KinderCloseSensor._unrecorded_attributes
    assert "fecha_ficha" not in KinderCloseSensor._unrecorded_attributes


async def test_rejected_credentials_start_reauth_and_close_session(hass, entry):
    with patch(FETCH, side_effect=AuthenticationError), patch(CLOSE) as close:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(flow["context"]["source"] == SOURCE_REAUTH for flow in hass.config_entries.flow.async_progress())
    close.assert_called_once()


async def test_connection_error_retries_setup_later(hass, entry):
    with patch(FETCH, side_effect=requests.ConnectionError), patch(CLOSE):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
