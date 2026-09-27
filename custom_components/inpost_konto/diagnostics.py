"""Diagnostyka — bez tokenow i bez kodow otwarcia skrytki."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import InPostConfigEntry
from .const import CONF_TOKENS

TO_REDACT = {CONF_TOKENS, "device_uid", "phone", "kod_odbioru", "openCode", "qrCode"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: InPostConfigEntry
) -> dict[str, Any]:
    """Zrzut stanu do zgloszenia bledu."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "parcels": async_redact_data(
            [dict(p) for p in coordinator.data.parcels], TO_REDACT
        ),
        "notifications_count": len(coordinator.data.notifications),
        "last_update_success": coordinator.last_update_success,
    }
