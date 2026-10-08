"""Actualización coordinada sin bloquear Home Assistant."""
from datetime import timedelta
import logging

import requests
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AuthenticationError, KinderClose
from .const import CONF_PUPIL_ID, DOMAIN

LOGGER = logging.getLogger(__name__)


class KinderCloseCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, LOGGER, name=DOMAIN, config_entry=entry, update_interval=timedelta(minutes=15))
        self.entry = entry
        # Cliente persistente: la sesión se reutiliza entre actualizaciones y solo
        # se vuelve a iniciar sesión cuando KinderClose la invalida.
        # Crear el objeto no hace E/S; todas las peticiones HTTP van al executor.
        data = entry.data
        self.client = KinderClose(data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_PUPIL_ID])

    async def async_close(self):
        await self.hass.async_add_executor_job(self.client.close)

    async def _async_update_data(self):
        try:
            return await self.hass.async_add_executor_job(self.client.fetch)
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed("KinderClose ha rechazado las credenciales") from error
        except requests.RequestException as error:
            raise UpdateFailed("No se puede conectar con KinderClose") from error
        except ValueError as error:
            raise UpdateFailed(str(error)) from error
