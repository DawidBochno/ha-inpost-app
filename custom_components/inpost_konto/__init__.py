"""Integracja InPost App — paczki z konta InPost Mobile w Home Assistant."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CARD_URL, DOMAIN, PLATFORMS, VERSION
from .coordinator import InPostCoordinator

_LOGGER = logging.getLogger(__name__)

type InPostConfigEntry = ConfigEntry[InPostCoordinator]

_CARD_REGISTERED = f"{DOMAIN}_card"


async def async_setup_entry(hass: HomeAssistant, entry: InPostConfigEntry) -> bool:
    """Postaw jedno konto InPost."""
    await _async_register_card(hass)
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


async def _async_register_card(hass: HomeAssistant) -> None:
    """Podaj karte Lovelace, zeby byla do wybrania z listy „Dodaj karte".

    Serwujemy plik JS spod wlasnej sciezki i dopisujemy go do modulow frontendu.
    Bez tego uzytkownik musialby dodawac zasob recznie albo wklejac YAML.
    Rejestracja jest raz na instancje — drugie konto nie ma czego rejestrowac.
    """
    if hass.data.get(_CARD_REGISTERED):
        return
    hass.data[_CARD_REGISTERED] = True
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARD_URL, str(Path(__file__).parent / "www" / "inpost-card.js"), False
            )
        ]
    )
    # Wersja w adresie lamie cache przegladarki po aktualizacji integracji.
    frontend.add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")
    _LOGGER.debug("Karta Lovelace zarejestrowana pod %s", CARD_URL)
