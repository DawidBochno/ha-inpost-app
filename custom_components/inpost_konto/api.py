"""Klient API konta InPost Mobile (OAuth2 + PKCE)."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import aiohttp

from .const import (
    API_BASE,
    APP_ID,
    ENDPOINT_ME,
    ENDPOINT_NOTIFICATIONS,
    ENDPOINT_TOKEN,
    ENDPOINT_TRACKED,
    OAUTH_AUTHORIZE_URL,
    OAUTH_CLIENT_ID,
    OAUTH_REDIRECT_URI,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=30)
# Odswiezamy token z zapasem, zeby nie trafic w wygasniecie w polowie requestu.
_EXPIRY_MARGIN = 60


class InPostError(Exception):
    """Blad przejsciowy — warto ponowic."""


class InPostAuthError(InPostError):
    """Sesja nie do odratowania — trzeba zalogowac sie od nowa."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _headers(device_uid: str) -> dict[str, str]:
    return {
        "x-app-id": APP_ID,
        "device-uid": device_uid,
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Language": "pl-PL",
    }


class InPostLogin:
    """Jedna proba logowania: buduje link i wymienia wklejony kod na tokeny."""

    def __init__(self) -> None:
        self._verifier = _b64url(secrets.token_bytes(48))
        self._state = _b64url(secrets.token_bytes(24))

    @property
    def url(self) -> str:
        """Link do otwarcia w przegladarce."""
        params = {
            "response_type": "code",
            "client_id": OAUTH_CLIENT_ID,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "scope": "openid",
            "code_challenge": _b64url(hashlib.sha256(self._verifier.encode()).digest()),
            "code_challenge_method": "S256",
            "state": self._state,
            "nonce": _b64url(secrets.token_bytes(24)),
            "response_mode": "query",
            "lang": "pl",
            "supported_markets": "PL",
        }
        return f"{OAUTH_AUTHORIZE_URL}?{urlencode(params)}"

    def extract_code(self, pasted: str) -> str:
        """Wyciagnij `code` z wklejonego adresu zwrotnego (albo z samego kodu)."""
        value = pasted.strip()
        if "code=" not in value:
            # Ktos wklejil sam kod, bez adresu.
            if value and " " not in value and "/" not in value:
                return value
            raise ValueError("brak kodu")
        query = parse_qs(urlsplit(value).query or value)
        code = (query.get("code") or [""])[0]
        if not code:
            raise ValueError("brak kodu")
        state = (query.get("state") or [None])[0]
        if state is not None and state != self._state:
            # Adres z innej (starszej) proby logowania — kod i verifier sie rozjada.
            raise ValueError("niezgodny state")
        return code

    async def async_exchange(
        self, session: aiohttp.ClientSession, device_uid: str, code: str
    ) -> dict[str, Any]:
        """Wymien kod autoryzacyjny na zestaw tokenow."""
        return await _async_token_request(
            session,
            device_uid,
            {
                "client_id": OAUTH_CLIENT_ID,
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": self._verifier,
                "redirect_uri": OAUTH_REDIRECT_URI,
            },
        )


def _tokens_from_response(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InPostAuthError("odpowiedz tokenowa nie jest obiektem JSON")
    access = payload.get("access_token")
    refresh = payload.get("refresh_token")
    if not access or not refresh:
        raise InPostAuthError("odpowiedz tokenowa bez tokenow")
    return {
        "access_token": access,
        "refresh_token": refresh,
        "expires_at": time.time() + float(payload.get("expires_in") or 0),
    }


async def _async_token_request(
    session: aiohttp.ClientSession, device_uid: str, form: dict[str, str]
) -> dict[str, Any]:
    try:
        async with session.post(
            f"{API_BASE}{ENDPOINT_TOKEN}",
            data=form,
            headers=_headers(device_uid),
            timeout=_TIMEOUT,
        ) as response:
            if response.status in (400, 401, 403):
                # invalid_grant: kod albo refresh token zuzyty/uniewazniony.
                raise InPostAuthError(f"endpoint tokenow HTTP {response.status}")
            response.raise_for_status()
            payload = await response.json(content_type=None)
    except aiohttp.ClientError as err:
        # Padnieta siec w trakcie odswiezania to awaria lacza, nie martwa sesja.
        raise InPostError(f"nieudane zadanie tokenu: {err}") from err
    return _tokens_from_response(payload)


class InPostApi:
    """Klient jednego konta.

    InPost rotuje refresh tokeny: kazde odswiezenie zwraca nowy i uniewaznia
    stary. Dlatego `on_tokens` jest wolane po kazdym odswiezeniu — nowy zestaw
    musi trafic do config entry, zanim bedzie potrzebny ponownie.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        device_uid: str,
        tokens: dict[str, Any],
        on_tokens: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self._session = session
        self._device_uid = device_uid
        self._tokens = dict(tokens)
        self._on_tokens = on_tokens
        # Dwa rownolegle 401 nie moga odswiezac naraz — drugie zuzyloby
        # refresh token uniewazniony przez pierwsze.
        self._lock = asyncio.Lock()

    @property
    def tokens(self) -> dict[str, Any]:
        return dict(self._tokens)

    async def _async_refresh(self, seen_access: str | None = None) -> None:
        async with self._lock:
            if seen_access is not None and self._tokens["access_token"] != seen_access:
                return  # Ktos inny odswiezyl, gdy czekalismy na blokade.
            _LOGGER.debug("Odswiezanie tokenu InPost")
            tokens = await _async_token_request(
                self._session,
                self._device_uid,
                {
                    "client_id": OAUTH_CLIENT_ID,
                    "grant_type": "refresh_token",
                    "refresh_token": self._tokens["refresh_token"],
                },
            )
            self._tokens = tokens
            if self._on_tokens is not None:
                await self._on_tokens(dict(tokens))

    async def _get(self, endpoint: str, params: dict[str, str] | None = None) -> Any:
        if time.time() > float(self._tokens.get("expires_at") or 0) - _EXPIRY_MARGIN:
            await self._async_refresh()
        for attempt in (1, 2):
            access = self._tokens["access_token"]
            headers = {**_headers(self._device_uid), "Authorization": f"Bearer {access}"}
            try:
                async with self._session.get(
                    f"{API_BASE}{endpoint}",
                    params=params,
                    headers=headers,
                    timeout=_TIMEOUT,
                ) as response:
                    if response.status == 401 and attempt == 1:
                        # Token uniewazniony przedwczesnie (np. wylogowanie w apce).
                        await self._async_refresh(seen_access=access)
                        continue
                    if response.status in (401, 403):
                        raise InPostAuthError(f"{endpoint} HTTP {response.status}")
                    response.raise_for_status()
                    return await response.json(content_type=None)
            except aiohttp.ClientError as err:
                raise InPostError(f"blad wywolania {endpoint}: {err}") from err
        raise InPostAuthError(f"{endpoint}: brak autoryzacji po odswiezeniu")

    async def async_get_me(self) -> dict[str, Any]:
        """Profil konta — identyfikuje konto (id osoby, numer telefonu)."""
        data = await self._get(ENDPOINT_ME)
        return data if isinstance(data, dict) else {}

    async def async_get_tracked(self) -> dict[str, Any]:
        """Paczki przychodzace, pelna lista."""
        data = await self._get(ENDPOINT_TRACKED)
        return data if isinstance(data, dict) else {}

    async def async_get_notifications(self) -> dict[str, Any]:
        """Powiadomienia, ktore apka pokazuje w swojej skrzynce."""
        data = await self._get(ENDPOINT_NOTIFICATIONS, {"type": "PUSH,SYNERISE"})
        return data if isinstance(data, dict) else {}
