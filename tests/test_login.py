"""Wklejanie adresu zwrotnego (issue #1) — `python tests/test_login.py` z katalogu repo."""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

# Jak w test_parcels: bez __init__.py paczki (ciagnie HA), aiohttp tylko jako atrapa.
_pkg = types.ModuleType("ip")
_pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components" / "inpost_konto")]
sys.modules["ip"] = _pkg
_aiohttp = types.ModuleType("aiohttp")
_aiohttp.ClientTimeout = lambda **_: None
sys.modules.setdefault("aiohttp", _aiohttp)
InPostLogin = importlib.import_module("ip.api").InPostLogin


def _blad(login: InPostLogin, pasted: str) -> str:
    try:
        login.extract_code(pasted)
    except ValueError as err:
        return str(err)
    raise AssertionError(f"przyjeto {pasted!r}")


def main() -> None:
    login = InPostLogin()
    state = login._state
    url = f"https://account.inpost-group.com/callback?code=ABC&state={state}"
    assert login.extract_code(url) == "ABC"
    assert login.extract_code(f"  {url}\n") == "ABC"

    # Kod SMS to nie kod OAuth — wczesniej szedl do InPostu i wracal jako "odrzucony".
    assert _blad(login, "123456") == "sms"
    assert _blad(login, "123 456") == "sms"
    assert _blad(login, "https://account.inpost-group.com/") == "brak kodu"
    assert _blad(login, "") == "brak kodu"

    # Adres z innej proby logowania — config flow szuka wtedy wsrod starszych linkow.
    assert _blad(InPostLogin(), url) == "state"
    print("OK — logowanie przeszlo sprawdzenia")


if __name__ == "__main__":
    main()
