"""Integración nativa de KinderClose."""


async def async_setup_entry(hass, entry):
    from .coordinator import KinderCloseCoordinator

    coordinator = KinderCloseCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        # Si el primer refresco falla (no listo / reautenticación), no dejar la sesión abierta.
        await coordinator.async_close()
        raise
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True


async def async_unload_entry(hass, entry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unloaded:
        await entry.runtime_data.async_close()
    return unloaded
