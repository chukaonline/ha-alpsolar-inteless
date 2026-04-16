from .const import DOMAIN

async def async_setup_entry(hass, entry):
    """Set up Alpsolar Inteless from a config entry."""
    # Note the 's' at the end of setups and the [brackets] around "sensor"
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
