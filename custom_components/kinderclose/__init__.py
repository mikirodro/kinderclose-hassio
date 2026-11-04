"""Integración nativa de KinderClose."""


async def async_setup_entry(hass, entry):
    # Importaciones diferidas: el paquete se importa también en las pruebas del cliente, sin Home Assistant.
    from .account import acquire_client, async_release_client
    from .coordinator import KinderCloseCoordinator

    client = acquire_client(hass, entry)
    coordinator = KinderCloseCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        # Si el primer refresco falla (no listo / reautenticación), no dejar la sesión abierta.
        await async_release_client(hass, entry, client)
        raise
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True


async def async_unload_entry(hass, entry):
    from .account import async_release_client

    unloaded = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unloaded:
        await async_release_client(hass, entry, entry.runtime_data.client)
    return unloaded
