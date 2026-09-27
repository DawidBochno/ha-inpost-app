"""Jedyny sprawdzacz: mapowanie statusow i sprzatanie odebranych.

Bez pytesta i bez HA — `python tests/test_parcels.py` z katalogu repo.
Reszta integracji to klej HA; to tutaj jest logika, ktora moze sie zepsuc cicho.
"""
from __future__ import annotations

import importlib
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ladujemy tylko dwa modulu z paczki, bez jej __init__.py — ten ciagnie HA.
_pkg = types.ModuleType("ip")
_pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components" / "inpost_konto")]
sys.modules["ip"] = _pkg
_const = importlib.import_module("ip.const")
_parcels = importlib.import_module("ip.parcels")

ST_DELIVERED = _const.ST_DELIVERED
ST_PROBLEM = _const.ST_PROBLEM
ST_READY = _const.ST_READY
ST_UNKNOWN = _const.ST_UNKNOWN
drop_old_delivered = _parcels.drop_old_delivered
map_status = _parcels.map_status
normalize_all = _parcels.normalize_all
parse_dt = _parcels.parse_dt

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


def test_map_status() -> None:
    assert map_status("ready_to_pickup", None) == ST_READY
    assert map_status("READY_TO_PICKUP", None) == ST_READY, "status z API bywa CAPSem"
    # Nieznany szczegolowy status ratuje statusGroup.
    assert map_status("cos_nowego_2027", "TO_PICKUP") == ST_READY
    assert map_status("cos_nowego_2027", "COS_NOWEGO") == ST_UNKNOWN
    assert map_status("pickup_time_expired", None) == ST_PROBLEM


def test_normalize() -> None:
    """Ksztalt wzorowany na prawdziwej odpowiedzi /v4/parcels/tracked.

    Wazne szczegoly z zywego konta: statusy sa WIELKIMI literami, zdarzenia
    przychodza w dwoch listach naraz (bogata `events`, uboga `eventLog`),
    a `type` punktu to lista.
    """
    payload = {
        "updatedUntil": "2026-09-27T10:40:54.767Z",
        "more": False,
        "parcels": [
            {
                "shipmentNumber": "653999410005825208459870",
                "shipmentType": "parcel",
                "status": "READY_TO_PICKUP",
                "statusGroup": "TO_PICKUP",
                "sender": "Allegro",
                "expiryDate": "2026-09-29T20:00:00.000Z",
                "openCode": "123456",
                "parcelSize": "B",
                "pickUpPoint": {
                    "name": "GRM02A",
                    "location": {"latitude": 52.10274, "longitude": 20.61853},
                    "locationDescription": "Przy sklepie Carrefour",
                    "openingHours": "24/7",
                    "location247": True,
                    "easyAccessZone": True,
                    "imageUrl": "https://static.easypack24.net/points/pl/images/GRM02A.jpg",
                    "type": ["parcel_locker"],
                    "addressDetails": {
                        "street": "Żyrardowska",
                        "buildingNumber": "50",
                        "postCode": "05-825",
                        "city": "Grodzisk Mazowiecki",
                    },
                },
                "events": [
                    {
                        "date": "2026-09-03T09:04:27.610Z",
                        "eventTitle": "Gotowa do odbioru",
                        "eventCode": "LMD.1005",
                    },
                    {
                        "date": "2026-09-03T06:49:02.076Z",
                        "eventTitle": "Wydana do doręczenia",
                        "eventCode": "LMD.1001",
                    },
                ],
                "eventLog": [
                    {"type": "PARCEL_STATUS", "name": "READY_TO_PICKUP", "date": "2026-09-03T09:04:27.610Z"},
                ],
            },
            {"status": "DELIVERED"},  # bez numeru — do wyrzucenia
        ],
    }
    parcels = normalize_all(payload, show_codes=False)
    assert len(parcels) == 1, "paczka bez numeru nie ma prawa zrobic encji"
    parcel = parcels[0]
    assert parcel["status"] == ST_READY, "status z API jest CAPSem"
    assert parcel["nadawca"] == "Allegro", "nadawca bywa golym stringiem, nie slownikiem"
    assert parcel["adres"] == "Żyrardowska 50 05-825 Grodzisk Mazowiecki"
    assert parcel["latitude"] == 52.10274
    assert parcel["typ_punktu"] == "parcel_locker", "lista typow ma byc splaszczona"
    assert parcel["zdjecie_punktu"].endswith("GRM02A.jpg")
    assert "kod_odbioru" not in parcel, "kod otwiera skrytke — domyslnie ukryty"
    # Regres: czytalem `type` z eventLog, wiec kazde zdarzenie bylo "PARCEL_STATUS".
    assert parcel["zdarzenia"][0]["opis"] == "Gotowa do odbioru"
    assert parcel["zdarzenia"][0]["kod"] == "LMD.1005"
    assert normalize_all(payload, show_codes=True)[0]["kod_odbioru"] == "123456"
    # Zapas, gdy API przysle tylko uboga liste.
    only_log = normalize_all(
        {"parcels": [{"shipmentNumber": "x", "eventLog": [{"type": "PARCEL_STATUS", "name": "DELIVERED", "date": "2026-09-01T10:00:00Z"}]}]},
        show_codes=False,
    )
    assert only_log[0]["zdarzenia"][0]["opis"] == "DELIVERED"
    # Sortowanie: paczka z terminem przed paczka bez terminu.
    mixed = normalize_all(
        {"parcels": [{"shipmentNumber": "b"}, {"shipmentNumber": "a", "expiryDate": "2026-09-28T10:00:00Z"}]},
        show_codes=False,
    )
    assert [p["numer"] for p in mixed] == ["a", "b"]


def test_drop_old_delivered() -> None:
    fresh = {"status": ST_DELIVERED, "data_odbioru": (NOW - timedelta(days=1)).isoformat()}
    stale = {"status": ST_DELIVERED, "data_odbioru": (NOW - timedelta(days=10)).isoformat()}
    undated = {"status": ST_DELIVERED, "data_odbioru": None}
    active = {"status": ST_READY, "data_odbioru": None}
    kept = drop_old_delivered([fresh, stale, undated, active], 3, now=NOW)
    assert fresh in kept and active in kept
    assert stale not in kept
    assert undated in kept, "bez daty nie wiemy, czy stara — zostaje"
    assert drop_old_delivered([fresh, active], 0, now=NOW) == [active]


def test_parse_dt() -> None:
    assert parse_dt("2026-09-27T08:00:00.000Z").tzinfo is not None
    assert parse_dt("kiedys") is None
    assert parse_dt(None) is None


if __name__ == "__main__":
    test_map_status()
    test_normalize()
    test_drop_old_delivered()
    test_parse_dt()
    print("OK — wszystkie sprawdzenia przeszly")
