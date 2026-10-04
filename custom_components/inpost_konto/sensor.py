"""Sensory: podsumowanie konta + jedna encja na paczke."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import InPostConfigEntry
from .const import (
    ATTRIBUTION,
    DOMAIN,
    ST_DELIVERED,
    ST_IN_TRANSIT,
    ST_OUT_FOR_DELIVERY,
    ST_READY,
    ST_REGISTERED,
    ST_RETURNING,
    ST_PROBLEM,
)
from .coordinator import InPostCoordinator, InPostData
from .parcels import parse_dt

# Statusy skladajace sie na "w drodze" na dashboardzie.
_ON_THE_WAY = (ST_REGISTERED, ST_IN_TRANSIT, ST_OUT_FOR_DELIVERY)

# Podsumowania konta: (klucz, nazwa, ikona, funkcja licząca).
_SUMMARIES: tuple[tuple[str, str, str, Callable[[InPostData], int]], ...] = (
    ("paczki", "Paczki", "mdi:package-variant-closed", lambda d: len(d.parcels)),
    (
        "do_odbioru",
        "Do odbioru",
        "mdi:package-variant",
        lambda d: sum(p["status"] == ST_READY for p in d.parcels),
    ),
    (
        "w_drodze",
        "W drodze",
        "mdi:truck-delivery",
        lambda d: sum(p["status"] in _ON_THE_WAY for p in d.parcels),
    ),
    (
        "problemy",
        "Problemy",
        "mdi:package-variant-remove",
        lambda d: sum(p["status"] in (ST_PROBLEM, ST_RETURNING) for p in d.parcels),
    ),
)


def _compact(parcel: dict[str, Any]) -> dict[str, Any]:
    """Skrocony opis paczki na liste w atrybutach (bez historii zdarzen)."""
    short = {
        k: parcel.get(k)
        for k in ("numer", "status", "nadawca", "punkt", "adres", "termin_odbioru")
    }
    # Klucz jest w paczce tylko przy wlaczonym "Publikuj kody" (parcels.py) — karta go wyswietla.
    if "kod_odbioru" in parcel:
        short["kod_odbioru"] = parcel["kod_odbioru"]
    return short


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InPostConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Postaw podsumowania, a paczki dokladaj w miare jak sie pojawiaja."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        InPostSummarySensor(coordinator, entry, key, name, icon, fn)
        for key, name, icon, fn in _SUMMARIES
    ]
    entities.append(InPostNextExpirySensor(coordinator, entry))
    entities.append(InPostNotificationSensor(coordinator, entry))
    async_add_entities(entities)

    known: set[str] = set()

    @callback
    def _add_new_parcels() -> None:
        new = [
            InPostParcelSensor(coordinator, entry, p["numer"])
            for p in coordinator.data.parcels
            if p["numer"] not in known
        ]
        known.update(e.number for e in new)
        if new:
            async_add_entities(new)

    _add_new_parcels()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_parcels))


class InPostEntity(CoordinatorEntity[InPostCoordinator], SensorEntity):
    """Wspolny rodzic: atrybucja i urzadzenie = konto InPost."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: InPostCoordinator, entry: InPostConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="InPost",
            model="Konto InPost Mobile",
        )


class InPostSummarySensor(InPostEntity):
    """Licznik paczek w danym stanie; lista paczek w atrybutach."""

    _attr_native_unit_of_measurement = "szt."
    _attr_state_class = None

    def __init__(
        self,
        coordinator: InPostCoordinator,
        entry: InPostConfigEntry,
        key: str,
        name: str,
        icon: str,
        count: Callable[[InPostData], int],
    ) -> None:
        super().__init__(coordinator, entry)
        self._count = count
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    @property
    def native_value(self) -> int:
        return self._count(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"paczki": [_compact(p) for p in self.coordinator.data.parcels]}


class InPostNextExpirySensor(InPostEntity):
    """Najblizszy termin odbioru — do automatyzacji "zostaly 24 h"."""

    _attr_name = "Najbliższy termin odbioru"
    _attr_icon = "mdi:clock-alert-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: InPostCoordinator, entry: InPostConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_najblizszy_termin"

    @property
    def native_value(self) -> datetime | None:
        terms = [
            dt
            for p in self.coordinator.data.parcels
            if p["status"] == ST_READY and (dt := parse_dt(p.get("termin_odbioru")))
        ]
        return min(terms) if terms else None


class InPostNotificationSensor(InPostEntity):
    """Ostatnie powiadomienie z apki; reszta w atrybutach."""

    _attr_name = "Ostatnie powiadomienie"
    _attr_icon = "mdi:bell-outline"

    def __init__(self, coordinator: InPostCoordinator, entry: InPostConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_powiadomienie"

    @property
    def native_value(self) -> str | None:
        notifications = self.coordinator.data.notifications
        if not notifications:
            return None
        first = notifications[0]
        text = first.get("title") or first.get("body") or first.get("message")
        # Stan w HA ma limit 255 znakow — dluzsze i tak by odpadlo.
        return str(text)[:255] if text else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"powiadomienia": self.coordinator.data.notifications}


class InPostParcelSensor(InPostEntity):
    """Jedna paczka: stan = status, szczegoly w atrybutach."""

    _attr_icon = "mdi:package-variant-closed"

    def __init__(
        self,
        coordinator: InPostCoordinator,
        entry: InPostConfigEntry,
        number: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self.number = number
        self._attr_name = f"Paczka {number}"
        self._attr_unique_id = f"{entry.entry_id}_{number}"

    @property
    def _parcel(self) -> dict[str, Any] | None:
        return next(
            (p for p in self.coordinator.data.parcels if p["numer"] == self.number), None
        )

    @property
    def available(self) -> bool:
        # Paczka wypadla z listy (odebrana dawno / usunieta z konta).
        return super().available and self._parcel is not None

    @property
    def native_value(self) -> str | None:
        parcel = self._parcel
        return parcel["status"] if parcel else None

    @property
    def icon(self) -> str:
        parcel = self._parcel
        if parcel is None:
            return self._attr_icon
        return {
            ST_READY: "mdi:package-variant",
            ST_OUT_FOR_DELIVERY: "mdi:truck-delivery",
            ST_IN_TRANSIT: "mdi:truck-fast",
            ST_DELIVERED: "mdi:package-variant-closed-check",
            ST_PROBLEM: "mdi:package-variant-remove",
            ST_RETURNING: "mdi:keyboard-return",
        }.get(parcel["status"], self._attr_icon)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        parcel = self._parcel or {}
        return {k: v for k, v in parcel.items() if k != "status"}
