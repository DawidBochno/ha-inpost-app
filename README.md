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
2. Zaloguj się jak w apce: numer telefonu → kod SMS → captcha. Kod SMS wpisujesz na stronie
   InPostu — **nie** w HA. Jeśli InPost poprosi o logowanie e-mailem („znamy się”), zrób to
   w tej samej przeglądarce; gdy potem trafisz na stronę konta zamiast na `callback`, kliknij
   link z okienka HA jeszcze raz — będąc zalogowanym, powinieneś od razu dostać adres z kodem.
3. Przeglądarka wyląduje na `https://account.inpost-group.com/callback?code=...`. Strona
   może wyglądać na pustą lub błędną — to normalne, liczy się adres.
4. Skopiuj **cały adres z paska** i wklej w HA.

Kod w adresie jest jednorazowy. Wszystkie linki pokazane w tym samym okienku pozostają ważne,
więc logowanie rozpoczęte wcześniejszym linkiem też da się dokończyć.

**„Nie znalazłem kodu w tym adresie"** mimo poprawnego `callback?code=...`: InPost pamięta w przeglądarce
starszą próbę logowania i odsyła jej kod (inny `state` w adresie niż w linku). Otwórz link w oknie prywatnym (incognito).

### Logowanie od nowa albo na inne konto

Jeśli przeglądarka jest już zalogowana do InPostu, link z HA nie zapyta o numer — od razu wróci
z kodem **tego** konta. Żeby zalogować się od nowa (np. numerem telefonu albo na inne konto):

**Okno prywatne (najprościej):**
1. W okienku HA kliknij **prawym przyciskiem** na „ten link” → **Kopiuj adres linku**
   (zwykłe kliknięcie otworzy go w normalnym oknie).
2. Otwórz okno prywatne — **Ctrl+Shift+N** (Chrome, Edge, Opera), **Ctrl+Shift+P** (Firefox).
3. Wklej link, zaloguj się, skopiuj adres `…/callback?code=…` **z tego okna** i wklej w HA.
4. Zamknij okno prywatne — sesja InPostu zniknie razem z nim.

**Albo wyczyść sesję w zwykłej przeglądarce:** wejdź na `https://account.inpost-group.com`,
kliknij kłódkę przy adresie → **Ustawienia witryny / Pliki cookie i dane witryny** → **Usuń dane**,
potem kliknij link z okienka HA jeszcze raz.

Jeśli numer telefonu jest powiązany z kontem e-mail, InPost i tak może powiedzieć „znamy się” i poprosić
o e-mail — dokończ wtedy logowanie e-mailem **w tym samym oknie**. Gdy link z maila otworzy się
w nowej karcie, po komunikacie o udanym logowaniu **wróć do pierwszej karty**. Jeśli pokaże formularz
danych konta (jak przy zakładaniu), zatwierdź go przyciskiem na dole, niczego nie wpisując — dopiero
wtedy pojawi się adres `…/callback?code=…` do wklejenia w HA (za
[#1](https://github.com/DawidBochno/ha-inpost-app/issues/1)).

Integracja obsługuje jedno konto na wpis. Drugie konto (np. domownika) dodajesz jako kolejny wpis:
Ustawienia → Urządzenia i usługi → InPost App → **Dodaj wpis** — i logujesz się w oknie prywatnym jak wyżej.

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
| `sensor.*_paczka_<numer>` | status paczki | nadawca, paczkomat + adres + współrzędne, zdjęcie paczkomatu, godziny otwarcia / 24-7, strefa łatwego dostępu, rozmiar, terminy, historia zdarzeń (z opisami InPostu i kodami typu `LMD.1005`), link do śledzenia, kod odbioru (opcjonalnie) |

Statusy są mapowane na 8 kubełków: `zarejestrowana`, `w_drodze`, `w_dostawie`,
`do_odbioru`, `odebrana`, `zwrot`, `problem`, `nieznany` — w automatyzacjach porównuj do
nich, nie do surowych stringów InPostu (tych jest ~60 i dochodzą nowe).

## Opcje (⋮ → Konfiguruj)

- **Częstotliwość odpytywania** — domyślnie 5 min.
- **Publikuj kody otwarcia skrytki** — domyślnie **wyłączone**. Po włączeniu kod jest
  w atrybucie `kod_odbioru` encji paczki i w liście `paczki` liczników, a karta pokazuje go
  przy paczce do odbioru. Obok jest `kod_qr`, czyli treść kodu QR z aplikacji InPost: karta
  rysuje go sama (w przeglądarce, bez wysyłania gdziekolwiek), a paczkomat skanuje go z ekranu.
  Kod otwiera skrytkę, a atrybuty encji lądują w bazie recordera
  i we wszystkim, co ją czyta.
- **Ile dni trzymać odebrane paczki** — domyślnie 7, `0` = usuwaj od razu. Bez tego lista
  rośnie bez końca. Uwaga: jeśli wszystkie Twoje paczki są odebrane i starsze niż ten próg,
  **wszystkie liczniki pokażą 0** — to nie awaria, tylko pusta skrzynka.

## Karta na panelu

<img src="docs/karta.svg" width="560" alt="Karta InPost: liczniki paczek, paczka w paczkomacie z terminem, kodem odbioru i kodem QR">

<sup>Podgląd karty na przykładowych danych — paczka czekająca w paczkomacie, z włączonym „Publikuj kody” (QR zakodowany z fikcyjnym numerem).</sup>

Integracja wozi własną kartę Lovelace, więc **nic nie trzeba wklejać ani rejestrować**:

1. Otwórz panel → Edytuj → **Dodaj kartę**.
2. Wpisz „InPost" w wyszukiwarce kart — pozycja **„InPost — paczki"** ma podgląd na żywo.
3. Dodaj. Karta sama znajduje właściwą encję, więc działa od razu, bez konfiguracji.

Pokazuje cztery liczniki (do odbioru / w drodze / wszystkie / problemy), a pod nimi listę
paczek: nadawca, status, paczkomat z adresem, odliczanie do terminu odbioru i — przy włączonej
opcji „Publikuj kody” — kod odbioru i kod QR paczki czekającej w paczkomacie. Wiersze
odebranych paczek są przygaszone.

**Kod odbioru i QR na karcie** (domyślnie ukryte): Ustawienia → Urządzenia i usługi →
InPost App → ⚙️ **Konfiguruj** → zaznacz **„Publikuj kody otwarcia skrytki”**. Przy paczce
„do odbioru” pojawi się 6-cyfrowy kod, a pod nią QR — w paczkomacie wybierz skanowanie
i przyłóż ekran telefonu.

Opcjonalnie:

```yaml
type: custom:inpost-card
entity: sensor.inpost_paczki
title: Paczki
```

### Alternatywy

- **Karta surowa, jednym kliknięciem:** Ustawienia → Urządzenia i usługi → InPost App →
  urządzenie → **„Dodaj do panelu"**. HA pyta, na który panel i zakładkę, i sam wstawia kartę
  ze wszystkimi encjami. Bez paczkomatu i terminu — to zwykła lista encji.
- **Same karty wbudowane** (gdybyś nie chciał własnej karty — np. na panelu w trybie
  ścisłego YAML-a):

```yaml
type: vertical-stack
cards:
  - type: glance
    title: InPost
    entities:
      - entity: sensor.inpost_do_odbioru
        name: Do odbioru
      - entity: sensor.inpost_w_drodze
        name: W drodze
      - entity: sensor.inpost_paczki
        name: Wszystkie
      - entity: sensor.inpost_problemy
        name: Problemy
  - type: markdown
    content: >-
      {% set paczki = state_attr('sensor.inpost_paczki','paczki') or [] %}

      {% if not paczki %}Brak paczek.{% endif %}

      {% for p in paczki %}

      **{{ p.nadawca or 'Nieznany nadawca' }}** — {{ p.status }}

      {% if p.punkt %}- {{ p.punkt }}, {{ p.adres }}

      {% endif %}{% endfor %}
```

Wszystkie warianty czytają atrybut `paczki` z licznika — ten sam mają wszystkie cztery
liczniki. Encje pojedynczych paczek przydają się osobno: w automatyzacjach i na kartach
jednej przesyłki (mają m.in. zdjęcie paczkomatu i pełną historię zdarzeń).

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
python tests/test_login.py
node tests/test_card.cjs
```

Pierwszy sprawdza mapowanie statusów, normalizację paczki, sprzątanie odebranych i to, że kod
odbioru nie wycieka przy wyłączonej opcji; drugi — wklejanie adresu zwrotnego przy logowaniu
(kod SMS, adres z innej próby); trzeci — odliczanie do terminu odbioru, kubełki liczników
i kod odbioru w karcie. Czyli te części, które mogą się
zepsuć po cichu. Ani HA, ani pytesta, ani przeglądarki.
