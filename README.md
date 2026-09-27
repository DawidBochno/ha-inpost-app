# InPost App — integracja Home Assistant

<img src="custom_components/inpost_konto/brand/icon.png" width="96" align="right" alt="">

Wyciąga z konta **InPost Mobile** to, co widzi aplikacja: paczki przychodzące, ich statusy,
paczkomat/punkt odbioru, termin odbioru, kod otwarcia skrytki (opcjonalnie) i powiadomienia
z apki.

Napisana od zera, świadomie **na nowym API** (OAuth2 + PKCE, `account.inpost-group.com`),
a nie na starym `sendSMSCode`/`confirmSMSCode`, na którym sesje w innych integracjach
padają co kilka dni.

## Czym się różni od integracji, które się rozsypują

| | stare API (`/v1/confirmSMSCode`) | ta integracja |
|---|---|---|
| Logowanie | HA wysyła SMS i zgaduje captchę | logujesz się na stronie InPostu, HA dostaje tylko kod |
| Sesja | krótki token, częste „session expired" | refresh token rotowany przy każdym odświeżeniu, zapisywany do config entry |
| Gdy sesja padnie | integracja w `setup_retry`, cisza | `reauth` — HA sam pyta o ponowne logowanie |

## Instalacja

### HACS (zalecane)

1. HACS → ⋮ (prawy górny róg) → **Custom repositories**.
2. Wklej `https://github.com/DawidBochno/ha-inpost-app`, kategoria **Integration** → Add.
3. Znajdź „InPost App" na liście HACS → Download.
4. Zrestartuj Home Assistanta.
5. **Ustawienia → Urządzenia i usługi → Dodaj integrację → „InPost App"**.

[![Otwórz w HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=DawidBochno&repository=ha-inpost-app&category=integration)

### Ręcznie

1. Skopiuj katalog `custom_components/inpost_konto` do `/config/custom_components/` w HA
   (Studio Code Server, Samba albo `scp` na `core_ssh`).
2. Zrestartuj Home Assistanta, potem jak w punkcie 5 powyżej.

> Uwagi o nazwach: repo, integracja w HACS i wpis w HA nazywają się **InPost App**,
> ale domena (katalog integracji) to `inpost_konto`. Nazwę repo można zmienić w każdej chwili,
> domeny nie — siedzi w nazwach encji i w zapisanym wpisie konfiguracji.

## Logowanie

1. Kliknij link pokazany w okienku konfiguracji — otworzy stronę logowania InPostu.
2. Zaloguj się jak w apce: numer telefonu → kod SMS → captcha.
3. Przeglądarka wyląduje na `https://account.inpost-group.com/callback?code=...`. Strona
   może wyglądać na pustą lub błędną — to normalne, liczy się adres.
4. Skopiuj **cały adres z paska** i wklej w HA.

Link i kod są jednorazowe. Jeśli się nie udało — wróć do okienka, weź nowy link.

## Co dostajesz

Encje na urządzeniu „InPost +48…":

| Encja | Stan | Atrybuty |
|---|---|---|
| `sensor.*_paczki` | liczba paczek | lista wszystkich (numer, status, nadawca, punkt, termin) |
| `sensor.*_do_odbioru` | ile czeka w paczkomacie | jak wyżej |
| `sensor.*_w_drodze` | ile w drodze | jak wyżej |
| `sensor.*_problemy` | ile z problemem/zwrotem | jak wyżej |
| `sensor.*_najblizszy_termin_odbioru` | timestamp | — |
| `sensor.*_ostatnie_powiadomienie` | treść | `powiadomienia` (ostatnie 20) |
| `sensor.*_paczka_<numer>` | status paczki | nadawca, paczkomat + adres + współrzędne, godziny otwarcia, rozmiar, terminy, historia zdarzeń, link do śledzenia, kod odbioru (opcjonalnie) |

Statusy są mapowane na 8 kubełków: `zarejestrowana`, `w_drodze`, `w_dostawie`,
`do_odbioru`, `odebrana`, `zwrot`, `problem`, `nieznany` — w automatyzacjach porównuj do
nich, nie do surowych stringów InPostu (tych jest ~60 i dochodzą nowe).

## Opcje (⋮ → Konfiguruj)

- **Częstotliwość odpytywania** — domyślnie 5 min.
- **Publikuj kody otwarcia skrytki** — domyślnie **wyłączone**. Kod otwiera skrytkę, a stany
  encji lądują w bazie recordera i we wszystkim, co ją czyta.
- **Ile dni trzymać odebrane paczki** — domyślnie 3, `0` = usuwaj od razu. Bez tego lista
  rośnie bez końca.

## Przykład automatyzacji

Podstaw swój numer — encje nazywają się od numeru konta (`sensor.inpost_48<numer>_*`).

```yaml
automation:
  - alias: Paczka czeka w paczkomacie
    triggers:
      - trigger: state
        entity_id: sensor.inpost_48xxxxxxxxx_do_odbioru
    conditions:
      - condition: template
        value_template: "{{ trigger.to_state.state | int > trigger.from_state.state | int }}"
    actions:
      - action: notify.mobile_app_telefon
        data:
          title: Paczka do odbioru
          message: >
            {{ state_attr('sensor.inpost_48xxxxxxxxx_do_odbioru', 'paczki')
               | selectattr('status', 'eq', 'do_odbioru') | map(attribute='punkt')
               | join(', ') }}
```

## Ograniczenia / czego tu nie ma

- **Tylko paczki przychodzące.** Nadane/zwroty (`/v4/parcels/sent`) nie są odpytywane — nie
  potwierdziłem kształtu tej odpowiedzi.
- **Nie otwiera skrytki.** Integracja tylko czyta; otwieranie z HA to osobna decyzja
  (i osobne ryzyko).
- **Kod QR** nie jest publikowany — jest duży i i tak nieczytelny jako atrybut stanu.
- API jest niepubliczne. InPost może je zmienić bez ostrzeżenia; wtedy w logu pojawi się
  `blad wywolania /v4/parcels/tracked`, a nowe, nieznane statusy zgłoszą się same
  ostrzeżeniem `Nieznany status paczki InPost`.

## Sprawdzenie

```bash
python tests/test_parcels.py
```

Sprawdza mapowanie statusów, normalizację paczki i sprzątanie odebranych — czyli jedyną
część, która może się zepsuć po cichu. Nie wymaga ani HA, ani pytesta.
