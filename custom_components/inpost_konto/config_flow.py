"""Przeplyw konfiguracji: logowanie w przegladarce, wklejenie adresu zwrotnego."""
from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    ConfigEntry,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .api import InPostApi, InPostAuthError, InPostError, InPostLogin
from .const import (
    CONF_DEVICE_UID,
    CONF_KEEP_DELIVERED_DAYS,
    CONF_PHONE,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_CODES,
    CONF_TOKENS,
    DEFAULT_KEEP_DELIVERED_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SHOW_CODES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONF_CALLBACK = "callback_url"
STEP_SCHEMA = vol.Schema({vol.Required(CONF_CALLBACK): TextSelector()})


def _phone_of(profile: dict[str, Any]) -> str | None:
    """Wyciagnij numer telefonu z profilu, niezaleznie od zagniezdzenia."""
    phone = profile.get("phoneNumber") or profile.get("phone")
    if isinstance(phone, dict):
        # Bywa {"prefix": "+48", "value": "512..."}.
        return f"{phone.get('prefix') or ''}{phone.get('value') or ''}" or None
    return str(phone) if phone else None


class InPostConfigFlow(ConfigFlow, domain=DOMAIN):
    """Logowanie przez strone InPostu — captcha nie przejdzie z HA."""

    VERSION = 1

    def __init__(self) -> None:
        self._login = InPostLogin()
        # Jeden device-uid na wpis, staly: API wiaze z nim sesje.
        self._device_uid = str(uuid.uuid4())

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pokaz link do logowania i przyjmij wklejony adres zwrotny."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                code = self._login.extract_code(user_input[CONF_CALLBACK])
            except ValueError:
                errors["base"] = "invalid_callback"
            else:
                session = async_get_clientsession(self.hass)
                try:
                    tokens = await self._login.async_exchange(
                        session, self._device_uid, code
                    )
                    api = InPostApi(session, self._device_uid, tokens)
                    profile = await api.async_get_me()
                except InPostAuthError:
                    errors["base"] = "invalid_auth"
                except InPostError:
                    errors["base"] = "cannot_connect"
                else:
                    phone = _phone_of(profile)
                    unique_id = str(profile.get("id") or profile.get("uuid") or phone or code)
                    data = {
                        CONF_DEVICE_UID: self._device_uid,
                        CONF_TOKENS: api.tokens,
                        CONF_PHONE: phone,
                    }
                    if self.source == "reauth":
                        entry = self._get_reauth_entry()
                        await self.async_set_unique_id(unique_id)
                        self._abort_if_unique_id_mismatch(reason="wrong_account")
                        return self.async_update_reload_and_abort(entry, data=data)
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"InPost {phone or ''}".strip(), data=data
                    )
            # Kod jednorazowy jest spalony — nastepna proba potrzebuje nowego linku.
            self._login = InPostLogin()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_SCHEMA,
            errors=errors,
            description_placeholders={"login_url": self._login.url},
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Sesja padla — to samo logowanie, ten sam formularz."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> InPostOptionsFlow:
        return InPostOptionsFlow()


class InPostOptionsFlow(OptionsFlow):
    """Interwal, kody odbioru, ile trzymac odebrane."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    CONF_SHOW_CODES: user_input[CONF_SHOW_CODES],
                    CONF_KEEP_DELIVERED_DAYS: int(user_input[CONF_KEEP_DELIVERED_DAYS]),
                }
            )
        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=60, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_SHOW_CODES,
                        default=options.get(CONF_SHOW_CODES, DEFAULT_SHOW_CODES),
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_KEEP_DELIVERED_DAYS,
                        default=options.get(
                            CONF_KEEP_DELIVERED_DAYS, DEFAULT_KEEP_DELIVERED_DAYS
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=30, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )
