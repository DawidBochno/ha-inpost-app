"""Diagnostyka — bez tokenow i bez kodow otwarcia skrytki."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import InPostConfigEntry
from .const import CONF_TOKENS

# Wartosci znikaja, klucze zostaja — o to chodzi: ksztalt odpowiedzi widac,
# danych osobowych i kodow do skrytki nie.
TO_REDACT = {
    CONF_TOKENS,
    "device_uid",
    "phone",
    "kod_odbioru",
    "kod_qr",
    "openCode",
    "qrCode",
    "sender",
    "receiver",
    "nadawca",
    "phoneNumber",
    "email",
}


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
        # Surowa odpowiedz API: jedyny sposob, zeby zobaczyc, czy pusta lista
        # paczek to naprawde brak paczek, czy inny ksztalt JSON-a.
        "raw_tracked": async_redact_data(coordinator.raw_tracked or {}, TO_REDACT),
        "notifications_count": len(coordinator.data.notifications),
        "last_update_success": coordinator.last_update_success,
    }
