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
    payload = {
        "parcels": [
            {
                "shipmentNumber": "123",
                "status": "ready_to_pickup",
                "statusGroup": "TO_PICKUP",
                "sender": {"name": "Allegro"},
                "expiryDate": "2026-09-29T20:00:00.000Z",
                "openCode": "123456",
                "parcelSize": "A",
                "pickUpPoint": {
                    "name": "KRA01A",
                    "addressDetails": {
                        "street": "Długa",
                        "buildingNumber": "1",
                        "postCode": "30-001",
                        "city": "Kraków",
                    },
                    "location": {"latitude": 50.06, "longitude": 19.94},
                },
                "eventLog": [
                    {"type": "ready_to_pickup", "date": "2026-09-27T08:00:00.000Z"},
                    {"type": "out_for_delivery", "date": "2026-09-26T08:00:00.000Z"},
                ],
            },
            {"status": "delivered"},  # bez numeru — do wyrzucenia
        ]
    }
    parcels = normalize_all(payload, show_codes=False)
    assert len(parcels) == 1, "paczka bez numeru nie ma prawa zrobic encji"
    parcel = parcels[0]
    assert parcel["status"] == ST_READY
    assert parcel["nadawca"] == "Allegro"
    assert parcel["adres"] == "Długa 1 30-001 Kraków"
    assert parcel["latitude"] == 50.06
    assert "kod_odbioru" not in parcel, "kod otwiera skrytke — domyslnie ukryty"
    assert parcel["zdarzenia"][0]["kiedy"].startswith("2026-09-27"), "najnowsze pierwsze"
    assert normalize_all(payload, show_codes=True)[0]["kod_odbioru"] == "123456"
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
