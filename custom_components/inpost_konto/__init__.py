"""Integracja InPost App — paczki z konta InPost Mobile w Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import InPostCoordinator

type InPostConfigEntry = ConfigEntry[InPostCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: InPostConfigEntry) -> bool:
    """Postaw jedno konto InPost."""
    coordinator = InPostCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: InPostConfigEntry) -> bool:
    """Zdejmij konto."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: InPostConfigEntry) -> None:
    """Zmiana opcji zmienia interwal i zakres danych — przeladuj wpis."""
    await hass.config_entries.async_reload(entry.entry_id)
