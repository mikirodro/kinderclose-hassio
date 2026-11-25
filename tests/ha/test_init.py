"""Pruebas de carga, sensores, privacidad del historial, token y descarga de la integración."""
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from conftest import DATA, ENTRY_DATA, RECORD
from custom_components.kinderclose.client import AuthenticationError, CannotConnect, KinderClose
from custom_components.kinderclose.const import CONF_DEVICE_ID, CONF_PUPIL_ID, CONF_TOKEN, DOMAIN
from custom_components.kinderclose.sensor import KinderCloseSensor

FETCH = "custom_components.kinderclose.client.KinderClose.fetch"
CLOSE = "custom_components.kinderclose.client.KinderClose.close"
LOGOUT = "custom_components.kinderclose.client.KinderClose.logout"


def state(hass, key):
    return hass.states.get(f"sensor.kinderclose_123_{key}")


async def test_setup_creates_sensors_and_unload_closes_session(hass, entry):
    with patch(FETCH, return_value=DATA) as fetch, patch(CLOSE) as close:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        client = entry.runtime_data.client
        assert (client.token, client.device_id) == ("tok-1", 77)
        assert fetch.call_args.args == ("123",)
        assert fetch.call_args.kwargs["tz"] is not None

        expected = {
            "ultima_ficha": "2026-10-07", "asistencia": "presente", "entrada": "09:00", "salida": "unknown",
            "desayuno": "Todo", "primero": "Bastante", "segundo": "unknown", "sueno": "33",
            "deposiciones": "0", "biberones": "1", "recordatorios": "1",
        }
        assert {key: state(hass, key).state for key in expected} == expected
        registry_entry = er.async_get(hass).async_get("sensor.kinderclose_123_asistencia")
        assert registry_entry.translation_key == "asistencia"
        assert dr.async_get(hass).async_get(registry_entry.device_id).name == "KinderClose 123"
        assert state(hass, "asistencia").attributes["friendly_name"].endswith("Attendance")

        ultima = state(hass, "ultima_ficha")
        assert ultima.attributes["ficha"] == RECORD
        assert ultima.attributes["url_ficha"] == RECORD["url"]
        assert state(hass, "recordatorios").attributes["elementos"] == ["Pañales"]
        assert state(hass, "biberones").attributes["detalles"] == RECORD["biberones"]
        assert state(hass, "entrada").attributes["entrada_tarde"] is None
        assert state(hass, "asistencia").attributes["ausencia_justificada"] is None

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    close.assert_called_once()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_no_recent_record_gives_unknown_states_not_errors(hass, entry):
    with patch(FETCH, return_value={**DATA, "ficha": None}), patch(CLOSE):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert state(hass, "ultima_ficha").state == "unknown"
    assert state(hass, "deposiciones").state == "unknown"
    assert state(hass, "ultima_ficha").attributes["fecha_ficha"] is None


async def test_new_token_is_stored_in_every_entry_of_the_account(hass, entry):
    sibling = MockConfigEntry(domain=DOMAIN, unique_id="124", data={**ENTRY_DATA, CONF_PUPIL_ID: "124", CONF_TOKEN: "otro"})
    sibling.add_to_hass(hass)

    async def fetch_with_new_token(self, pupil_id, **kwargs):
        if self.token != "tok-9":
            self.token, self.device_id = "tok-9", 99
            self.on_token("tok-9", 99)
        return DATA

    with patch.object(KinderClose, "fetch", fetch_with_new_token), patch(CLOSE):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.runtime_data.client is sibling.runtime_data.client
    for config_entry in (entry, sibling):
        assert (config_entry.data[CONF_TOKEN], config_entry.data[CONF_DEVICE_ID]) == ("tok-9", 99)


async def test_pupils_of_the_same_account_share_one_client(hass, entry):
    sibling = MockConfigEntry(domain=DOMAIN, unique_id="124", data={**ENTRY_DATA, CONF_PUPIL_ID: "124"})
    sibling.add_to_hass(hass)
    other_account = MockConfigEntry(domain=DOMAIN, unique_id="200", data={**ENTRY_DATA, "username": "otra@example.com", CONF_PUPIL_ID: "200"})
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


async def test_removing_the_last_entry_of_a_token_logs_out(hass, entry):
    sibling = MockConfigEntry(domain=DOMAIN, unique_id="124", data={**ENTRY_DATA, CONF_PUPIL_ID: "124"})
    sibling.add_to_hass(hass)
    with patch(LOGOUT) as logout, patch(CLOSE):
        await hass.config_entries.async_remove(sibling.entry_id)
        logout.assert_not_called()
        await hass.config_entries.async_remove(entry.entry_id)
        logout.assert_called_once()


def test_detailed_minor_data_is_not_recorded():
    assert {"ficha", "sesiones", "detalles", "elementos", "url_ficha", "consultado_en"} <= KinderCloseSensor._unrecorded_attributes
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
