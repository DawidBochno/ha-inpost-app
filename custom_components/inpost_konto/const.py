"""Stałe integracji InPost App."""
from __future__ import annotations

DOMAIN = "inpost_konto"
VERSION = "0.2.3"  # trzymaj zgodnie z manifest.json — leci do URL-a karty jako cache-buster

# Własna karta Lovelace serwowana przez integrację: dzięki niej karta jest do
# wybrania z listy „Dodaj kartę", bez wklejania YAML-a i bez dodawania zasobu ręcznie.
CARD_URL = "/inpost_konto/inpost-card.js"
PLATFORMS = ["sensor"]  # string, zeby const.py dal sie zaimportowac bez HA (testy)
ATTRIBUTION = "Dane z konta InPost Mobile"

# --- API konsumenckie apki InPost Mobile (PL) ---------------------------------
# Logowanie idzie przez OAuth2 authorization code + PKCE na stronach InPostu
# (numer telefonu -> SMS -> captcha). Captcha jest nie do przejścia z HA, więc
# użytkownik loguje się w przeglądarce i wkleja adres, na którym wyląduje.
# Sprawdzone 2026-09-27: /oauth2/authorize -> 302 na ekran logowania,
# /global/oauth2/token -> 400 na podrobiony refresh_token (czyli endpoint żyje).
API_BASE = "https://api-inmobile-pl.easypack24.net"
OAUTH_AUTHORIZE_URL = "https://account.inpost-group.com/oauth2/authorize"
OAUTH_REDIRECT_URI = "https://account.inpost-group.com/callback"
OAUTH_CLIENT_ID = "inpost-mobile"

ENDPOINT_TOKEN = "/global/oauth2/token"
ENDPOINT_ME = "/global/api/v1/user-catalogue/people/me"
ENDPOINT_TRACKED = "/v4/parcels/tracked"
ENDPOINT_NOTIFICATIONS = "/v3/notifications"

# API odpowiada tylko na ruch, który wygląda jak z apki.
APP_ID = "pl.inpost.inpostmobile"
USER_AGENT = "InPost-Mobile/4.19.0 (4)-release (iOS 26.7; iPhone14,3; pl)"

# --- Konfiguracja ------------------------------------------------------------
CONF_DEVICE_UID = "device_uid"
CONF_TOKENS = "tokens"
CONF_PHONE = "phone"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SHOW_CODES = "show_codes"
CONF_KEEP_DELIVERED_DAYS = "keep_delivered_days"

DEFAULT_SCAN_INTERVAL = 5           # minut; paczka rusza się kilka razy dziennie
# Kod odbioru otwiera skrytkę, więc domyślnie go nie publikujemy — stany i
# atrybuty lądują w bazie recordera i we wszystkim, co ją czyta.
DEFAULT_SHOW_CODES = False
DEFAULT_KEEP_DELIVERED_DAYS = 7

# Ile ostatnich zdarzeń trzymać w atrybucie (limit atrybutu stanu w HA ~16 kB).
MAX_EVENTS = 15

# --- Statusy -----------------------------------------------------------------
# Kanoniczne kubełki, na które mapujemy ~60 szczegółowych statusów InPostu.
ST_REGISTERED = "zarejestrowana"
ST_IN_TRANSIT = "w_drodze"
ST_OUT_FOR_DELIVERY = "w_dostawie"
ST_READY = "do_odbioru"
ST_DELIVERED = "odebrana"
ST_RETURNING = "zwrot"
ST_PROBLEM = "problem"
ST_UNKNOWN = "nieznany"

STATUS_MAP: dict[str, str] = {
    "created": ST_REGISTERED,
    "confirmed": ST_REGISTERED,
    "dispatched_by_sender": ST_REGISTERED,
    "dispatched_by_sender_to_pok": ST_REGISTERED,
    "taken_by_courier": ST_IN_TRANSIT,
    "taken_by_courier_from_pok": ST_IN_TRANSIT,
    "collected_from_sender": ST_IN_TRANSIT,
    "adopted_at_source_branch": ST_IN_TRANSIT,
    "sent_from_source_branch": ST_IN_TRANSIT,
    "adopted_at_sorting_center": ST_IN_TRANSIT,
    "sent_from_sorting_center": ST_IN_TRANSIT,
    "adopted_at_target_branch": ST_IN_TRANSIT,
    "redirect_to_box": ST_IN_TRANSIT,
    "permanently_redirected_to_box_machine": ST_IN_TRANSIT,
    "permanently_redirected_to_customer_service_point": ST_IN_TRANSIT,
    "readdressed": ST_IN_TRANSIT,
    "out_for_delivery": ST_OUT_FOR_DELIVERY,
    "out_for_delivery_to_address": ST_OUT_FOR_DELIVERY,
    "ready_to_pickup": ST_READY,
    "ready_for_collection": ST_READY,
    "ready_to_pickup_from_branch": ST_READY,
    "ready_to_pickup_from_pok": ST_READY,
    "ready_to_pickup_from_pok_registered": ST_READY,
    "stack_in_box_machine": ST_READY,
    "stack_in_customer_service_point": ST_READY,
    "pickup_reminder_sent": ST_READY,
    "pickup_reminder_sent_address": ST_READY,
    "delivered": ST_DELIVERED,
    "collected_by_customer": ST_DELIVERED,
    "claimed": ST_DELIVERED,
    "returned_to_sender": ST_RETURNING,
    "return_pickup_confirmation_to_sender": ST_RETURNING,
    "delay_in_delivery": ST_PROBLEM,
    "delivery_attempt_failed": ST_PROBLEM,
    "rejected_by_receiver": ST_PROBLEM,
    "not_collected": ST_PROBLEM,
    "missing": ST_PROBLEM,
    "oversized": ST_PROBLEM,
    "canceled": ST_PROBLEM,
    "cancelled": ST_PROBLEM,
    "pickup_time_expired": ST_PROBLEM,
    "stack_parcel_pickup_time_expired": ST_PROBLEM,
    "stack_parcel_in_box_machine_pickup_time_expired": ST_PROBLEM,
    "avizo": ST_PROBLEM,
    "avizo_rejected": ST_PROBLEM,
    "undelivered": ST_PROBLEM,
}

# Zgrubny statusGroup — siatka bezpieczeństwa dla statusu, którego nie znamy.
STATUS_GROUP_MAP: dict[str, str] = {
    "to_send": ST_REGISTERED,
    "in_delivery": ST_IN_TRANSIT,
    "to_pickup": ST_READY,
    "delivered": ST_DELIVERED,
}

TRACKING_URL = "https://inpost.pl/sledzenie-przesylek?number={number}"
