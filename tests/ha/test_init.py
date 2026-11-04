"""Pruebas de carga, sensores, privacidad del historial y descarga de la integración."""
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from conftest import DATA, USER_INPUT
from custom_components.kinderclose.client import AuthenticationError, CannotConnect
from custom_components.kinderclose.const import CONF_PUPIL_ID, DOMAIN
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


async def test_pupils_of_the_same_account_share_one_client(hass, entry):
    sibling = MockConfigEntry(domain=DOMAIN, unique_id="124", title="KinderClose 124", data={**USER_INPUT, CONF_PUPIL_ID: "124"})
    sibling.add_to_hass(hass)
    other_account = MockConfigEntry(domain=DOMAIN, unique_id="200", title="KinderClose 200", data={**USER_INPUT, "username": "otra@example.com", CONF_PUPIL_ID: "200"})
    other_account.add_to_hass(hass)
    with patch(FETCH, return_value=DATA) as fetch, patch(CLOSE) as close:
        # Configurar la primera entrada del dominio carga también las demás.
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert all(e.state is ConfigEntryState.LOADED for e in (entry, sibling, other_account))
        assert entry.runtime_data.client is sibling.runtime_data.client
        assert entry.runtime_data.client is not other_account.runtime_data.client
        assert {call.args[0] for call in fetch.call_args_list} >= {"123", "124", "200"}

        assert await hass.config_entries.async_unload(entry.entry_id)
        close.assert_not_called()
        assert await hass.config_entries.async_unload(sibling.entry_id)
        close.assert_called_once()
        assert await hass.config_entries.async_unload(other_account.entry_id)
        assert close.call_count == 2


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
    with patch(FETCH, side_effect=CannotConnect), patch(CLOSE):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
