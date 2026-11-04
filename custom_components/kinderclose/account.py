"""Un cliente por cuenta de KinderClose, compartido por los alumnos de esa cuenta."""
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .client import KinderClose
from .const import DOMAIN


def create_client(hass, user, password):
    """Cliente con una sesión aiohttp propia.

    No se usa la sesión compartida de Home Assistant para que las cookies de
    KinderClose no se mezclen con las de otras integraciones ni entre cuentas.
    """
    return KinderClose(async_create_clientsession(hass), user, password)


def acquire_client(hass, entry):
    """Devuelve el cliente de la cuenta de la entrada y lo marca en uso por ella.

    Las entradas con el mismo correo y contraseña comparten cliente, sesión y
    login. Si las credenciales difieren (por ejemplo, durante una
    reautenticación), cada conjunto usa su propio cliente.
    """
    accounts = hass.data.setdefault(DOMAIN, {})
    key = (entry.data[CONF_USERNAME].strip().lower(), entry.data[CONF_PASSWORD])
    if key not in accounts:
        accounts[key] = (create_client(hass, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]), set())
    client, entries = accounts[key]
    entries.add(entry.entry_id)
    return client


async def async_release_client(hass, entry, client):
    """Deja de usar el cliente y lo cierra cuando ya no lo usa ninguna entrada."""
    accounts = hass.data.get(DOMAIN, {})
    for key, (account_client, entries) in list(accounts.items()):
        if account_client is client:
            entries.discard(entry.entry_id)
            if not entries:
                del accounts[key]
                await client.close()
            return
