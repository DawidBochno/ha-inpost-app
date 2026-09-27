"""Koordynator odpytywania konta InPost."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import InPostApi, InPostAuthError, InPostError
from .const import (
    CONF_KEEP_DELIVERED_DAYS,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_CODES,
    CONF_TOKENS,
    DEFAULT_KEEP_DELIVERED_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SHOW_CODES,
    DOMAIN,
)
from .parcels import drop_old_delivered, normalize_all

_LOGGER = logging.getLogger(__name__)


@dataclass
class InPostData:
    """To, co koordynator oddaje encjom."""

    parcels: list[dict[str, Any]] = field(default_factory=list)
    notifications: list[dict[str, Any]] = field(default_factory=list)


class InPostCoordinator(DataUpdateCoordinator[InPostData]):
    """Odpytuje konto i normalizuje wynik."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        options = entry.options
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                minutes=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.api = InPostApi(
            session=async_get_clientsession(hass),
            device_uid=entry.data["device_uid"],
            tokens=entry.data[CONF_TOKENS],
            on_tokens=self._async_store_tokens,
        )

    async def _async_store_tokens(self, tokens: dict[str, Any]) -> None:
        """Zapisz zrotowany zestaw tokenow, zanim bedzie potrzebny ponownie."""
        entry = self.config_entry
        self.hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_TOKENS: tokens}
        )

    async def _async_update_data(self) -> InPostData:
        options = self.config_entry.options
        try:
            tracked = await self.api.async_get_tracked()
        except InPostAuthError as err:
            # Jedyna sciezka, ktora wolno przelozyc na ponowne logowanie.
            raise ConfigEntryAuthFailed(str(err)) from err
        except InPostError as err:
            raise UpdateFailed(str(err)) from err

        parcels = normalize_all(
            tracked, show_codes=options.get(CONF_SHOW_CODES, DEFAULT_SHOW_CODES)
        )
        parcels = drop_old_delivered(
            parcels, options.get(CONF_KEEP_DELIVERED_DAYS, DEFAULT_KEEP_DELIVERED_DAYS)
        )

        # Powiadomienia to dodatek — ich awaria nie moze wywalic calej aktualizacji.
        notifications: list[dict[str, Any]] = []
        try:
            payload = await self.api.async_get_notifications()
        except InPostError as err:
            _LOGGER.debug("Nie udalo sie pobrac powiadomien: %s", err)
        else:
            raw = payload.get("notifications") or payload.get("items") or []
            notifications = [n for n in raw if isinstance(n, dict)][:20]

        return InPostData(parcels=parcels, notifications=notifications)
