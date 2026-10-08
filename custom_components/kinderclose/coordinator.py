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

    async def _async_update_data(self):
        data = self.entry.data
        try:
            # La sesión y todas las operaciones HTTP se crean dentro del executor.
            return await self.hass.async_add_executor_job(
                lambda: KinderClose(data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_PUPIL_ID]).fetch()
            )
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed("KinderClose ha rechazado las credenciales") from error
        except requests.RequestException as error:
            raise UpdateFailed("No se puede conectar con KinderClose") from error
        except ValueError as error:
            raise UpdateFailed(str(error)) from error
