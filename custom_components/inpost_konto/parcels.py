"""Normalizacja paczek — czyste funkcje, bez I/O i bez obiektow HA.

Trzymane osobno od koordynatora, bo to jedyna czesc, ktora zalezy od kaprysow
API InPostu, i jedyna, ktora da sie przetestowac bez uruchamiania HA
(patrz tests/test_parcels.py).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from .const import (
    MAX_EVENTS,
    ST_DELIVERED,
    ST_UNKNOWN,
    STATUS_GROUP_MAP,
    STATUS_MAP,
    TRACKING_URL,
)

_LOGGER = logging.getLogger(__name__)

# Statusy, o ktorych juz krzyknelismy — zeby nie zasmiecac logu przy kazdym odpytaniu.
_warned: set[str] = set()


def parse_dt(value: Any) -> datetime | None:
    """Zamien znacznik czasu z API na aware datetime, albo None."""
    if not isinstance(value, str) or not value:
        return None
    try:
        # API zwraca ISO 8601, czasem z 'Z' zamiast offsetu.
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def map_status(raw_status: Any, raw_group: Any) -> str:
    """Zmapuj szczegolowy status; statusGroup to siatka bezpieczenstwa.

    Dzieki dwustopniowosci nieznany status i tak trafia w sensowny kubelek,
    zamiast ladowac jako `nieznany`.
    """
    status = str(raw_status or "").strip().lower()
    if status in STATUS_MAP:
        return STATUS_MAP[status]
    group = str(raw_group or "").strip().lower()
    mapped = STATUS_GROUP_MAP.get(group)
    if status and status not in _warned:
        _warned.add(status)
        _LOGGER.warning(
            "Nieznany status paczki InPost: %r (grupa %r) -> %s. "
            "Zglos go, zeby dorobic mapowanie.",
            raw_status,
            raw_group,
            mapped or ST_UNKNOWN,
        )
    return mapped or ST_UNKNOWN


def _pickup_point(raw: Any) -> dict[str, Any]:
    """Splaszcz pickUpPoint do tego, co da sie pokazac na dashboardzie."""
    if not isinstance(raw, dict):
        return {}
    location = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    kind = raw.get("type")
    address = raw.get("addressDetails") if isinstance(raw.get("addressDetails"), dict) else {}
    parts = [
        address.get("street"),
        address.get("buildingNumber"),
        address.get("postCode"),
        address.get("city"),
    ]
    return {
        "punkt": raw.get("name"),
        "adres": " ".join(str(p) for p in parts if p) or raw.get("locationDescription"),
        "opis_lokalizacji": raw.get("locationDescription"),
        "typ_punktu": ", ".join(kind) if isinstance(kind, list) else kind,
        "godziny_otwarcia": raw.get("openingHours"),
        "calodobowy": raw.get("location247"),
        "strefa_latwego_dostepu": raw.get("easyAccessZone"),
        "zdjecie_punktu": raw.get("imageUrl"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
    }


def _events(raw_events: Any, raw_log: Any) -> list[dict[str, Any]]:
    """Ostatnie MAX_EVENTS zdarzen, najnowsze pierwsze.

    API zwraca dwie listy naraz: bogata ``events`` (ludzki tytul + kod typu
    ``EOL.1001``) i uboga ``eventLog`` (``{type: "PARCEL_STATUS", name: "DELIVERED"}``).
    Bierzemy bogata, uboga jest zapasem — w niej opis siedzi w ``name``,
    a ``type`` dla kazdego zdarzenia to ta sama stala i nie niesie nic.
    """
    if isinstance(raw_events, list) and raw_events:
        items = [
            {"kiedy": e.get("date"), "opis": e.get("eventTitle"), "kod": e.get("eventCode")}
            for e in raw_events
            if isinstance(e, dict)
        ]
    elif isinstance(raw_log, list):
        items = [
            {"kiedy": e.get("date"), "opis": e.get("name"), "kod": None}
            for e in raw_log
            if isinstance(e, dict)
        ]
    else:
        return []
    items.sort(key=lambda e: str(e.get("kiedy") or ""), reverse=True)
    return items[:MAX_EVENTS]


def _text(value: Any) -> str | None:
    """Nadawca/odbiorca bywa slownikiem, bywa golym stringiem."""
    if isinstance(value, dict):
        return value.get("name") or value.get("companyName") or None
    return str(value) if value else None


def normalize_parcel(raw: dict[str, Any], *, show_codes: bool) -> dict[str, Any]:
    """Jedna paczka z API -> plaski slownik, z ktorego zyje encja."""
    number = str(raw.get("shipmentNumber") or raw.get("number") or "")
    multi = raw.get("multiCompartment") if isinstance(raw.get("multiCompartment"), dict) else {}

    parcel: dict[str, Any] = {
        "numer": number,
        "status": map_status(raw.get("status"), raw.get("statusGroup")),
        "status_api": raw.get("status"),
        "grupa_statusu": raw.get("statusGroup"),
        "nadawca": _text(raw.get("sender")) or _text(raw.get("senderName")),
        "rozmiar": raw.get("parcelSize"),
        "typ_przesylki": raw.get("shipmentType"),
        "data_nadania": raw.get("storedDate"),
        "data_odbioru": raw.get("pickUpDate"),
        "termin_odbioru": raw.get("expiryDate"),
        "zwrot_do_nadawcy": raw.get("returnedToSenderDate"),
        "wielo_skrytka": bool(multi.get("uuid")),
        "url": TRACKING_URL.format(number=number) if number else None,
        "zdarzenia": _events(raw.get("events"), raw.get("eventLog")),
        **_pickup_point(raw.get("pickUpPoint")),
    }
    if show_codes:
        # Kod otwiera skrytke — publikowany tylko na wyrazne zyczenie.
        parcel["kod_odbioru"] = raw.get("openCode")
    return parcel


def compact_parcel(parcel: dict[str, Any]) -> dict[str, Any]:
    """Skrocony opis paczki na liste w atrybutach licznikow (bez historii zdarzen)."""
    short = {
        k: parcel.get(k)
        for k in ("numer", "status", "nadawca", "punkt", "adres", "termin_odbioru")
    }
    # Klucz jest w paczce tylko przy wlaczonym "Publikuj kody" (normalize_parcel) — karta go wyswietla.
    if "kod_odbioru" in parcel:
        short["kod_odbioru"] = parcel["kod_odbioru"]
    return short


def normalize_all(payload: Any, *, show_codes: bool) -> list[dict[str, Any]]:
    """Cala odpowiedz /parcels/tracked -> lista znormalizowanych paczek."""
    if isinstance(payload, dict):
        raw_list = payload.get("parcels") or payload.get("items") or []
        if payload.get("more"):
            # ponytail: bez stronicowania. Doloz `updatedUntil` do zapytania,
            # jesli komus faktycznie urwie liste paczek.
            _LOGGER.warning(
                "InPost zwrocil `more: true` — lista paczek moze byc niepelna. Zglos to."
            )
    else:
        raw_list = payload if isinstance(payload, list) else []
    parcels = [
        normalize_parcel(raw, show_codes=show_codes)
        for raw in raw_list
        if isinstance(raw, dict) and (raw.get("shipmentNumber") or raw.get("number"))
    ]
    # Najpilniejsze na gorze: paczki z terminem odbioru, potem reszta.
    parcels.sort(key=lambda p: (p["termin_odbioru"] is None, str(p["termin_odbioru"] or "")))
    return parcels


def drop_old_delivered(
    parcels: list[dict[str, Any]], keep_days: int, *, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Wyrzuc odebrane paczki starsze niz `keep_days` dni.

    Bez tego lista rosnie bez konca i co odebrana paczka zostaje encja na wieki.
    Paczka bez daty odbioru zostaje — nie wiemy, jak stara jest.
    """
    if keep_days <= 0:
        return [p for p in parcels if p["status"] != ST_DELIVERED]
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=keep_days)
    kept = []
    for parcel in parcels:
        if parcel["status"] != ST_DELIVERED:
            kept.append(parcel)
            continue
        picked = parse_dt(parcel.get("data_odbioru"))
        if picked is None or picked >= cutoff:
            kept.append(parcel)
    return kept
