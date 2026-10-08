"""Configuración mediante la interfaz de Home Assistant."""
import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector

from .client import AuthenticationError, KinderClose
from .const import CONF_PUPIL_ID, CONF_PUPIL_NAME, DOMAIN



def _validate(user, password, pupil_id="", pupil_name=""):
    """Comprueba credenciales con una consulta mínima y cierra siempre la sesión."""
    with KinderClose(user, password, pupil_id, pupil_name) as client:
        return client.fetch(limit=1)


class KinderCloseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                result = await self.hass.async_add_executor_job(
                    _validate, user_input[CONF_USERNAME], user_input[CONF_PASSWORD], user_input.get(CONF_PUPIL_ID, ""), user_input.get(CONF_PUPIL_NAME, "")
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except requests.RequestException:
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["base"] = "invalid_pupil"
            else:
                await self.async_set_unique_id(result["alumno_id"])
                self._abort_if_unique_id_configured()
                data = {**user_input, CONF_PUPIL_ID: result["alumno_id"]}
                return self.async_create_entry(title="KinderClose " + result["alumno_id"], data=data)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
                vol.Optional(CONF_PUPIL_ID): str,
                vol.Optional(CONF_PUPIL_NAME): str,
            }),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            entry = self._get_reauth_entry()
            data = {**entry.data, **user_input}
            try:
                await self.hass.async_add_executor_job(
                    _validate, data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_PUPIL_ID]
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except requests.RequestException:
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["base"] = "invalid_pupil"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            }),
            errors=errors,
        )
