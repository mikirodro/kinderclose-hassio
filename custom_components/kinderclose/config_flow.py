"""Configuración mediante la interfaz de Home Assistant."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector

from .account import create_client
from .client import AuthenticationError, CannotConnect, NoRecords, PupilNotFound
from .const import CONF_PUPIL_ID, CONF_PUPIL_NAME, DOMAIN

LOGGER = logging.getLogger(__name__)

PASSWORD_SELECTOR = selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))


async def _validate(hass, user, password, pupil_id="", pupil_name=""):
    """Comprueba credenciales con una consulta mínima y cierra siempre la sesión."""
    async with create_client(hass, user, password) as client:
        return await client.fetch(pupil_id, pupil_name, limit=1)


class KinderCloseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _async_validate(self, errors, *args):
        """Valida con KinderClose y traduce las excepciones a errores del formulario."""
        try:
            return await _validate(self.hass, *args)
        except AuthenticationError:
            errors["base"] = "invalid_auth"
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except PupilNotFound:
            errors["base"] = "invalid_pupil"
        except NoRecords:
            errors["base"] = "no_records"
        except Exception:  # noqa: BLE001 - cualquier fallo inesperado se muestra como error del formulario
            # El traceback no incluye variables locales: no se registran credenciales.
            LOGGER.exception("Error inesperado al validar KinderClose")
            errors["base"] = "unknown"
        return None

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            result = await self._async_validate(
                errors, user_input[CONF_USERNAME], user_input[CONF_PASSWORD], user_input.get(CONF_PUPIL_ID, ""), user_input.get(CONF_PUPIL_NAME, "")
            )
            if not errors:
                await self.async_set_unique_id(result["alumno_id"])
                self._abort_if_unique_id_configured()
                data = {**user_input, CONF_PUPIL_ID: result["alumno_id"]}
                return self.async_create_entry(title="KinderClose " + result["alumno_id"], data=data)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
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
            # Validar con el ID guardado impide reasignar la entrada a otra cuenta sin ese alumno.
            await self._async_validate(errors, data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_PUPIL_ID])
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
            }),
            errors=errors,
        )
