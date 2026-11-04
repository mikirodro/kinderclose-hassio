"""Actualización coordinada sin bloquear Home Assistant."""
from datetime import timedelta
import logging

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AuthenticationError, CannotConnect
from .const import CONF_PUPIL_ID, DOMAIN

LOGGER = logging.getLogger(__name__)


class KinderCloseCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, client):
        super().__init__(hass, LOGGER, name=DOMAIN, config_entry=entry, update_interval=timedelta(minutes=15))
        self.entry = entry
        # Cliente asíncrono de la cuenta, compartido con otros alumnos de la misma
        # cuenta: la sesión se reutiliza y solo se vuelve a iniciar sesión cuando
        # KinderClose la invalida.
        self.client = client

    async def _async_update_data(self):
        try:
            return await self.client.fetch(self.entry.data[CONF_PUPIL_ID])
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed("KinderClose ha rechazado las credenciales") from error
        except CannotConnect as error:
            raise UpdateFailed("No se puede conectar con KinderClose") from error
        except ValueError as error:
            raise UpdateFailed(str(error)) from error
