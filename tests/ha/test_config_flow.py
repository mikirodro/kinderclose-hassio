"""Pruebas del flujo de configuración y reautenticación."""
from unittest.mock import ANY, patch

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from conftest import CREDENTIALS, PUPILS
from custom_components.kinderclose.client import AuthenticationError, CannotConnect
from custom_components.kinderclose.const import CONF_DEVICE_ID, CONF_PUPIL_ID, CONF_TOKEN, DOMAIN

LOGIN = "custom_components.kinderclose.config_flow._login"
SETUP = "custom_components.kinderclose.async_setup_entry"


def login(pupils=PUPILS):
    return patch(LOGIN, return_value=("tok-2", 88, pupils))


async def start_user_flow(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


async def test_several_pupils_ask_which_one_and_store_the_token(hass):
    result = await start_user_flow(hass)
    with login() as validate, patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {**CREDENTIALS, CONF_USERNAME: " familia@example.com "})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pupil"
        # Solo se ofrecen alumnos activos.
        options = result["data_schema"].schema[CONF_PUPIL_ID].config["options"]
        assert [option["value"] for option in options] == ["123", "124"]
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PUPIL_ID: "124"})
        await hass.async_block_till_done()
    validate.assert_called_once_with(ANY, "familia@example.com", "secreto")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "KinderClose Hermano"
    assert result["result"].unique_id == "124"
    assert result["data"] == {**CREDENTIALS, CONF_TOKEN: "tok-2", CONF_DEVICE_ID: 88, CONF_PUPIL_ID: "124"}


async def test_single_remaining_pupil_is_created_directly(hass, entry):
    result = await start_user_flow(hass)
    with login(), patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "124"


async def test_all_pupils_configured_aborts(hass, entry):
    MockConfigEntry(domain=DOMAIN, unique_id="124", data={}).add_to_hass(hass)
    result = await start_user_flow(hass)
    with login():
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (AuthenticationError, "invalid_auth"),
        (CannotConnect, "cannot_connect"),
        (ValueError, "unknown"),
        (KeyError, "unknown"),
    ],
)
async def test_user_flow_shows_specific_errors(hass, side_effect, error):
    result = await start_user_flow(hass)
    with patch(LOGIN, side_effect=side_effect):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_account_without_active_pupils(hass):
    result = await start_user_flow(hass)
    with login({"125": PUPILS["125"]}):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["errors"] == {"base": "no_pupils"}


async def test_reauth_updates_credentials_and_token_and_keeps_pupil(hass, entry):
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    with login() as validate, patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {**CREDENTIALS, CONF_PASSWORD: "nuevo"})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "nuevo"
    assert (entry.data[CONF_TOKEN], entry.data[CONF_DEVICE_ID], entry.data[CONF_PUPIL_ID]) == ("tok-2", 88, "123")
    validate.assert_called_once_with(ANY, "familia@example.com", "nuevo")


async def test_reauth_with_another_account_is_rejected(hass, entry):
    result = await entry.start_reauth_flow(hass)
    with login({"999": PUPILS["124"]}):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_USERNAME: "otra@example.com", CONF_PASSWORD: "x"})
    assert result["errors"] == {"base": "invalid_pupil"}
    assert entry.data[CONF_USERNAME] == "familia@example.com"


async def test_reauth_with_rejected_credentials_keeps_old_ones(hass, entry):
    result = await entry.start_reauth_flow(hass)
    with patch(LOGIN, side_effect=AuthenticationError):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {**CREDENTIALS, CONF_PASSWORD: "mal"})
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_PASSWORD] == "secreto"
