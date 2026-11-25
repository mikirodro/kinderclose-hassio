"""Configuración mediante la interfaz de Home Assistant."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector

from .account import create_client
from .client import AuthenticationError, CannotConnect
from .const import CONF_DEVICE_ID, CONF_PUPIL_ID, CONF_TOKEN, DOMAIN

LOGGER = logging.getLogger(__name__)

PASSWORD_SELECTOR = selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))
CREDENTIALS_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL, autocomplete="username")),
    vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
})


async def _login(hass, user, password):
    """Inicia sesión y devuelve ``(token, device_id, alumnos)``. Cierra siempre la sesión HTTP.

    El token obtenido se guarda en la entrada: así la integración no vuelve a
    iniciar sesión (ni registra otro dispositivo) al arrancar.
    """
    async with create_client(hass, user, password) as client:
        pupils = await client.pupils()
        return client.token, client.device_id, pupils


class KinderCloseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._account = {}
        self._pupils = {}

    async def _async_login(self, errors, user_input):
        """Valida las credenciales y traduce las excepciones a errores del formulario."""
        user, password = user_input[CONF_USERNAME].strip(), user_input[CONF_PASSWORD]
        try:
            token, device_id, pupils = await _login(self.hass, user, password)
        except AuthenticationError:
            errors["base"] = "invalid_auth"
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001 - cualquier fallo inesperado se muestra como error del formulario
            # El traceback no incluye variables locales: no se registran credenciales.
            LOGGER.exception("Error inesperado al validar KinderClose")
            errors["base"] = "unknown"
        else:
            return {CONF_USERNAME: user, CONF_PASSWORD: password, CONF_TOKEN: token, CONF_DEVICE_ID: device_id}, pupils
        return None, None

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            account, pupils = await self._async_login(errors, user_input)
            if account:
                active = {key: pupil for key, pupil in pupils.items() if pupil["activo"]}
                configured = self._async_current_ids(include_ignore=False)
                self._account = account
                self._pupils = {key: pupil for key, pupil in active.items() if key not in configured}
                if not active:
                    errors["base"] = "no_pupils"
                elif not self._pupils:
                    return self.async_abort(reason="already_configured")
                elif len(self._pupils) == 1:
                    return await self._async_create(next(iter(self._pupils)))
                else:
                    return await self.async_step_pupil()
        suggested = {CONF_USERNAME: user_input[CONF_USERNAME]} if user_input else None
        return self.async_show_form(step_id="user", data_schema=self.add_suggested_values_to_schema(CREDENTIALS_SCHEMA, suggested), errors=errors)

    async def async_step_pupil(self, user_input=None):
        """Elegir el alumno cuando la cuenta tiene varios sin configurar."""
        if user_input is not None:
            return await self._async_create(user_input[CONF_PUPIL_ID])
        options = [selector.SelectOptionDict(value=key, label=pupil["nombre_completo"]) for key, pupil in self._pupils.items()]
        return self.async_show_form(
            step_id="pupil",
            data_schema=vol.Schema({vol.Required(CONF_PUPIL_ID): selector.SelectSelector(selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.LIST))}),
        )

    async def _async_create(self, pupil_id):
        await self.async_set_unique_id(pupil_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=f"KinderClose {self._pupils[pupil_id]['nombre']}", data={**self._account, CONF_PUPIL_ID: pupil_id})

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            account, pupils = await self._async_login(errors, user_input)
            # Comprobar el alumno guardado impide reasignar la entrada a otra cuenta sin ese alumno.
            if account and entry.data[CONF_PUPIL_ID] not in pupils:
                errors["base"] = "invalid_pupil"
            elif account:
                return self.async_update_reload_and_abort(entry, data_updates=account)
        suggested = {CONF_USERNAME: (user_input or entry.data)[CONF_USERNAME]}
        return self.async_show_form(step_id="reauth_confirm", data_schema=self.add_suggested_values_to_schema(CREDENTIALS_SCHEMA, suggested), errors=errors)
