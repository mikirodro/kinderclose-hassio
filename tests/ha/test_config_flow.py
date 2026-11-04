"""Pruebas del flujo de configuración y reautenticación."""
from unittest.mock import ANY, patch

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType

from conftest import DATA, USER_INPUT
from custom_components.kinderclose.client import AuthenticationError, CannotConnect, NoRecords, PupilNotFound
from custom_components.kinderclose.const import CONF_PUPIL_ID, DOMAIN

VALIDATE = "custom_components.kinderclose.config_flow._validate"
SETUP = "custom_components.kinderclose.async_setup_entry"


async def start_user_flow(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    return result


async def test_user_flow_creates_entry_with_resolved_pupil_id(hass):
    result = await start_user_flow(hass)
    with patch(VALIDATE, return_value=DATA), patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {**USER_INPUT, CONF_PUPIL_ID: " 123 "})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "123"
    assert result["data"][CONF_PUPIL_ID] == "123"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (AuthenticationError, "invalid_auth"),
        (CannotConnect, "cannot_connect"),
        (PupilNotFound, "invalid_pupil"),
        (NoRecords, "no_records"),
        (ValueError, "unknown"),
        (KeyError, "unknown"),
    ],
)
async def test_user_flow_shows_specific_errors(hass, side_effect, error):
    result = await start_user_flow(hass)
    with patch(VALIDATE, side_effect=side_effect):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_same_pupil_cannot_be_configured_twice(hass, entry):
    result = await start_user_flow(hass)
    with patch(VALIDATE, return_value=DATA):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_credentials_and_keeps_pupil(hass, entry):
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    new_credentials = {CONF_USERNAME: "familia@example.com", CONF_PASSWORD: "nuevo"}
    with patch(VALIDATE, return_value=DATA) as validate, patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], new_credentials)
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "nuevo"
    assert entry.data[CONF_PUPIL_ID] == "123"
    validate.assert_called_once_with(ANY, "familia@example.com", "nuevo", "123")


async def test_reauth_with_rejected_credentials_keeps_old_ones(hass, entry):
    result = await entry.start_reauth_flow(hass)
    with patch(VALIDATE, side_effect=AuthenticationError):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_USERNAME: "familia@example.com", CONF_PASSWORD: "mal"})
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_PASSWORD] == "secreto"
