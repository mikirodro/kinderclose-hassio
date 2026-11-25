"""Un cliente por cuenta de KinderClose, compartido por los alumnos de esa cuenta."""
import aiohttp

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .client import KinderClose
from .const import CONF_DEVICE_ID, CONF_TOKEN, DOMAIN


def create_client(hass, user, password, token=None, device_id=None, on_token=None):
    """Cliente con una sesión aiohttp propia y sin cookies.

    La API se autentica con un token en cada petición. Sin cookies, ninguna
    sesión de la web puede mezclarse entre cuentas ni con otras integraciones.
    """
    session = async_create_clientsession(hass, cookie_jar=aiohttp.DummyCookieJar())
    return KinderClose(session, user, password, token, device_id, on_token)


def _account_key(data):
    return data[CONF_USERNAME].strip().lower(), data[CONF_PASSWORD]


def acquire_client(hass, entry):
    """Devuelve el cliente de la cuenta de la entrada y lo marca en uso por ella.

    Las entradas con el mismo correo y contraseña comparten cliente y token. Si
    las credenciales difieren (por ejemplo, durante una reautenticación), cada
    conjunto usa su propio cliente. Cuando el cliente obtiene un token nuevo, se
    guarda en todas las entradas que lo usan.
    """
    accounts = hass.data.setdefault(DOMAIN, {})
    key = _account_key(entry.data)
    if key not in accounts:
        entries = set()

        def store_token(token, device_id):
            for entry_id in entries:
                current = hass.config_entries.async_get_entry(entry_id)
                if current is not None:
                    _save_token(hass, current, token, device_id)

        client = create_client(hass, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], entry.data.get(CONF_TOKEN), entry.data.get(CONF_DEVICE_ID), store_token)
        accounts[key] = (client, entries)
    client, entries = accounts[key]
    entries.add(entry.entry_id)
    if client.token:
        _save_token(hass, entry, client.token, client.device_id)
    return client


def _save_token(hass, entry, token, device_id):
    if (entry.data.get(CONF_TOKEN), entry.data.get(CONF_DEVICE_ID)) != (token, device_id):
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_TOKEN: token, CONF_DEVICE_ID: device_id})


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


async def async_logout(hass, entry):
    """Cierra en KinderClose el dispositivo de la entrada si ninguna otra lo usa."""
    token = entry.data.get(CONF_TOKEN)
    others = (e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id)
    if not token or any(e.data.get(CONF_TOKEN) == token for e in others):
        return
    async with create_client(hass, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], token, entry.data.get(CONF_DEVICE_ID)) as client:
        await client.logout()
