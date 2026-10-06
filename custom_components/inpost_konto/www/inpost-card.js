const STATUSY = {
  do_odbioru: { etykieta: "do odbioru", ikona: "mdi:package-variant", kolor: "var(--warning-color, #ffa600)" },
  w_dostawie: { etykieta: "dziś u Ciebie", ikona: "mdi:truck-delivery", kolor: "var(--info-color, #39b0ff)" },
  w_drodze: { etykieta: "w drodze", ikona: "mdi:truck-fast", kolor: "var(--info-color, #39b0ff)" },
  zarejestrowana: { etykieta: "zarejestrowana", ikona: "mdi:package-variant-closed", kolor: "var(--secondary-text-color)" },
  odebrana: { etykieta: "odebrana", ikona: "mdi:package-variant-closed-check", kolor: "var(--success-color, #0da035)" },
  zwrot: { etykieta: "zwrot", ikona: "mdi:keyboard-return", kolor: "var(--warning-color, #ffa600)" },
  problem: { etykieta: "problem", ikona: "mdi:package-variant-remove", kolor: "var(--error-color, #db4437)" },
  nieznany: { etykieta: "nieznany", ikona: "mdi:help-circle-outline", kolor: "var(--secondary-text-color)" },
};

// Liczniki na górze karty. Liczymy z listy paczek, a nie z osobnych encji —
// karta potrzebuje wtedy jednej encji i działa od razu po wybraniu z listy.
const LICZNIKI = [
  ["do odbioru", (p) => p.status === "do_odbioru"],
  ["w drodze", (p) => ["zarejestrowana", "w_drodze", "w_dostawie"].includes(p.status)],
  ["wszystkie", () => true],
  ["problemy", (p) => ["problem", "zwrot"].includes(p.status)],
];

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function terminTekst(iso) {
  const kiedy = new Date(iso);
  if (isNaN(kiedy)) return null;
  const zostalo = kiedy - Date.now();
  const data = kiedy.toLocaleString("pl-PL", { weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  if (zostalo <= 0) return `termin minął (${data})`;
  const godziny = Math.floor(zostalo / 3600000);
  const ile = godziny >= 48 ? `zostało ${Math.floor(godziny / 24)} dni` : `zostało ${godziny} h`;
  return `odbierz do ${data} — ${ile}`;
}

// Kod QR rysowany lokalnie: tresc otwiera skrytke, wiec nie wysylamy jej do zadnego serwisu.
// Tryb bajtowy, korekcja M, wersje 1–6 (do ~100 znakow). Algorytm wg ISO 18004 (jak u Nayuki).
// ponytail: stala maska 0 zamiast wyboru najlepszej — czytniki odczytuja maske z pola formatu.
const QR_ECC = [0, 10, 16, 26, 18, 24, 16]; // bajty korekcji na blok, poziom M
const QR_BLOKI = [0, 1, 1, 1, 2, 2, 4];

function qrMacierz(tekst) {
  const dane = [...new TextEncoder().encode(tekst)];
  const surowe = (v) => (16 * v + 128) * v + 64 - (v >= 2 ? (25 * (Math.floor(v / 7) + 2) - 10) * (Math.floor(v / 7) + 2) - 55 : 0);
  let v = 1;
  while (v <= 6 && Math.floor(surowe(v) / 8) - QR_ECC[v] * QR_BLOKI[v] < dane.length + 2) v++;
  if (v > 6) return null;
  const pojemnosc = Math.floor(surowe(v) / 8) - QR_ECC[v] * QR_BLOKI[v];

  // Bity: tryb 0100, dlugosc na 8 bitach, dane, terminator, dopelnienie.
  const bity = [];
  const dopisz = (wart, ile) => { for (let i = ile - 1; i >= 0; i--) bity.push((wart >>> i) & 1); };
  dopisz(4, 4); dopisz(dane.length, 8); dane.forEach((b) => dopisz(b, 8));
  dopisz(0, Math.min(4, pojemnosc * 8 - bity.length));
  dopisz(0, (8 - (bity.length % 8)) % 8);
  const slowa = [];
  for (let i = 0; i < bity.length; i += 8) slowa.push(parseInt(bity.slice(i, i + 8).join(""), 2));
  for (let pad = 0xec; slowa.length < pojemnosc; pad ^= 0xec ^ 0x11) slowa.push(pad);

  // Reed-Solomon w GF(256) i przeplot blokow.
  const mnoz = (x, y) => { let z = 0; for (let i = 7; i >= 0; i--) { z = (z << 1) ^ ((z >>> 7) * 0x11d); z ^= ((y >>> i) & 1) * x; } return z; };
  const st = QR_ECC[v];
  const dzielnik = Array(st).fill(0); dzielnik[st - 1] = 1;
  for (let i = 0, r = 1; i < st; i++, r = mnoz(r, 2)) {
    for (let j = 0; j < st; j++) { dzielnik[j] = mnoz(dzielnik[j], r); if (j + 1 < st) dzielnik[j] ^= dzielnik[j + 1]; }
  }
  const reszta = (d) => { const w = Array(st).fill(0); for (const b of d) { const f = b ^ w.shift(); w.push(0); dzielnik.forEach((c, i) => (w[i] ^= mnoz(c, f))); } return w; };
  const nb = QR_BLOKI[v], wszystkie = Math.floor(surowe(v) / 8), krotkie = nb - (wszystkie % nb), dl = Math.floor(wszystkie / nb);
  const bloki = [];
  for (let i = 0, k = 0; i < nb; i++) {
    const d = slowa.slice(k, (k += dl - st + (i < krotkie ? 0 : 1)));
    const ecc = reszta(d);
    if (i < krotkie) d.push(0);
    bloki.push(d.concat(ecc));
  }
  const wynik = [];
  for (let i = 0; i < bloki[0].length; i++) bloki.forEach((b, j) => { if (i !== dl - st || j >= krotkie) wynik.push(b[i]); });

  // Wzory stale: wyszukiwania, synchronizacji, wyrownania, ciemny modul.
  const n = 17 + 4 * v;
  const m = Array.from({ length: n }, () => Array(n).fill(false));
  const stale = Array.from({ length: n }, () => Array(n).fill(false));
  const ustaw = (x, y, c) => { m[y][x] = c; stale[y][x] = true; };
  for (let i = 0; i < n; i++) { ustaw(6, i, i % 2 === 0); ustaw(i, 6, i % 2 === 0); }
  for (const [cx, cy] of [[3, 3], [n - 4, 3], [3, n - 4]]) {
    for (let dy = -4; dy <= 4; dy++) for (let dx = -4; dx <= 4; dx++) {
      const odl = Math.max(Math.abs(dx), Math.abs(dy)), x = cx + dx, y = cy + dy;
      if (x >= 0 && x < n && y >= 0 && y < n) ustaw(x, y, odl !== 2 && odl !== 4);
    }
  }
  if (v >= 2) {
    const p = n - 7; // dla wersji 2–6 jest tylko jeden wzor wyrownania
    for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) ustaw(p + dx, p + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
  }
  // Pole formatu: poziom M (00) + maska 0 = same zera, wiec BCH tez 0 i zostaje tylko XOR 0x5412.
  const fmt = 0x5412;
  const bit = (i) => ((fmt >>> i) & 1) === 1;
  for (let i = 0; i <= 5; i++) ustaw(8, i, bit(i));
  ustaw(8, 7, bit(6)); ustaw(8, 8, bit(7)); ustaw(7, 8, bit(8));
  for (let i = 9; i < 15; i++) ustaw(14 - i, 8, bit(i));
  for (let i = 0; i < 8; i++) ustaw(n - 1 - i, 8, bit(i));
  for (let i = 8; i < 15; i++) ustaw(8, n - 15 + i, bit(i));
  ustaw(8, n - 8, true);

  // Dane zygzakiem od prawego dolnego rogu, z maska 0: (x + y) % 2 == 0.
  let i = 0;
  for (let prawa = n - 1; prawa >= 1; prawa -= 2) {
    if (prawa === 6) prawa = 5;
    for (let pion = 0; pion < n; pion++) for (let j = 0; j < 2; j++) {
      const x = prawa - j, y = ((prawa + 1) & 2) === 0 ? n - 1 - pion : pion;
      if (stale[y][x]) continue;
      const b = i < wynik.length * 8 ? ((wynik[i >>> 3] >>> (7 - (i & 7))) & 1) === 1 : false;
      i++;
      m[y][x] = b !== ((x + y) % 2 === 0);
    }
  }
  return m;
}

function qrSvg(tekst) {
  const m = qrMacierz(tekst);
  if (!m) return "";
  const n = m.length, r = 4; // margines 4 moduly — wymog czytnikow
  let d = "";
  m.forEach((wiersz, y) => wiersz.forEach((c, x) => { if (c) d += `M${x + r},${y + r}h1v1h-1z`; }));
  return `<svg viewBox="0 0 ${n + 2 * r} ${n + 2 * r}" shape-rendering="crispEdges" style="width:100%;height:100%;background:#fff;border-radius:6px"><path d="${d}" fill="#000"/></svg>`;
}

class InpostCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) throw new Error("Wskaż encję licznika paczek, np. sensor.inpost_paczki");
    this._config = config;
    this._ostatni = null;
  }

  set hass(hass) {
    this._hass = hass;
    const stan = hass.states[this._config.entity];
    // Renderujemy tylko przy zmianie — hass sypie aktualizacjami przy każdej encji w systemie.
    const odcisk = stan ? stan.last_updated + stan.state : "brak";
    if (odcisk === this._ostatni) return;
    this._ostatni = odcisk;
    this._render(stan);
  }

  _render(stan) {
    if (!stan) {
      this.innerHTML = `<ha-card><div style="padding:16px;color:var(--error-color)">Nie ma encji ${esc(this._config.entity)}</div></ha-card>`;
      return;
    }
    const paczki = stan.attributes.paczki || [];
    const naglowek = this._config.title ?? "InPost";

    const liczniki = LICZNIKI.map(
      ([nazwa, filtr]) => `
      <div style="flex:1;text-align:center">
        <div style="font-size:26px;line-height:1.2">${paczki.filter(filtr).length}</div>
        <div style="font-size:12px;color:var(--secondary-text-color)">${nazwa}</div>
      </div>`
    ).join("");

    const wiersze = paczki.length
      ? paczki
          .map((p) => {
            const s = STATUSY[p.status] || STATUSY.nieznany;
            const punkt = p.punkt ? `${esc(p.punkt)}${p.adres ? ", " + esc(p.adres) : ""}` : null;
            const termin = p.termin_odbioru ? terminTekst(p.termin_odbioru) : null;
            // Kod przychodzi tylko przy włączonej opcji "Publikuj kody otwarcia skrytki".
            const kod = p.status === "do_odbioru" && p.kod_odbioru ? p.kod_odbioru : null;
            // QR z API (pole qrCode) — paczkomat skanuje go z ekranu zamiast wpisywania kodu.
            const qr = p.status === "do_odbioru" && p.kod_qr ? qrSvg(p.kod_qr) : "";
            const przygaszone = p.status === "odebrana" ? "opacity:.6;" : "";
            return `
        <div style="display:flex;gap:12px;padding:12px 0;border-top:1px solid var(--divider-color);${przygaszone}">
          <ha-icon icon="${s.ikona}" style="color:${s.kolor};--mdc-icon-size:22px"></ha-icon>
          <div style="flex:1;min-width:0">
            <div>${esc(p.nadawca || "Nieznany nadawca")} · <span style="color:${s.kolor}">${s.etykieta}</span></div>
            ${punkt ? `<div style="font-size:13px;color:var(--secondary-text-color)">${punkt}</div>` : ""}
            ${termin ? `<div style="font-size:13px;color:var(--warning-color, #ffa600)">${esc(termin)}</div>` : ""}
            ${qr ? `<div style="width:180px;max-width:100%;aspect-ratio:1;margin-top:10px">${qr}</div>` : ""}
          </div>
          ${kod ? `<div style="text-align:right"><div style="font-size:11px;color:var(--secondary-text-color)">kod odbioru</div><div style="font-size:20px;font-weight:500;letter-spacing:2px;font-family:var(--code-font-family, monospace)">${esc(kod)}</div></div>` : ""}
        </div>`;
          })
          .join("")
      : `<div style="padding:12px 0;border-top:1px solid var(--divider-color);color:var(--secondary-text-color)">Brak paczek.</div>`;

    this.innerHTML = `
      <ha-card header="${esc(naglowek)}">
        <div style="padding:0 16px 16px">
          <div style="display:flex;padding:4px 0 14px">${liczniki}</div>
          ${wiersze}
        </div>
      </ha-card>`;
  }

  getCardSize() {
    const stan = this._hass?.states[this._config?.entity];
    return 2 + (stan?.attributes.paczki?.length || 1);
  }

  // Dzięki temu karta po wybraniu z listy od razu pokazuje dane, bez konfiguracji.
  static getStubConfig(hass) {
    const encja = Object.keys(hass.states).find(
      (e) => e.startsWith("sensor.") && Array.isArray(hass.states[e].attributes.paczki)
    );
    return { type: "custom:inpost-card", entity: encja || "sensor.inpost_paczki" };
  }
}

// Gwardia na `typeof`: ten sam plik jest wczytywany przez test w node,
// gdzie ani customElements, ani window nie istnieja.
// Karta laduje sie przez add_extra_js_url, czyli PRZED zasobami Lovelace. Czesc kart
// z HACS (np. mini-graph-card, stack-in-card) wozi polyfill "scoped custom element
// registry", ktory podmienia window.customElements na nowy rejestr - i ten nie zna
// elementow zdefiniowanych wczesniej. HA widzi wtedy "Custom element doesn't exist".
// Ponowne define() w podmienionym rejestrze przyjmuje nasza klase i HA sam przebudowuje karte.
function zarejestruj() {
  if (typeof customElements !== "undefined" && !customElements.get("inpost-card")) {
    customElements.define("inpost-card", InpostCard);
  }
}
zarejestruj();
if (typeof window !== "undefined") {
  // ponytail: sprawdzanie przez 30 s po starcie; polyfill doladowany pozniej znow by zgubil karte
  let proby = 0;
  const t = setInterval(() => { zarejestruj(); if (++proby >= 30) clearInterval(t); }, 1000);
}

if (typeof window !== "undefined") {
window.customCards = window.customCards || [];
window.customCards.push({
  type: "inpost-card",
  name: "InPost — paczki",
  description: "Paczki z konta InPost: liczniki, paczkomat i termin odbioru.",
  preview: true,
  documentationURL: "https://github.com/DawidBochno/ha-inpost-app",
});
}

if (typeof module !== "undefined") module.exports = { terminTekst, LICZNIKI, STATUSY, esc, InpostCard, qrMacierz, qrSvg };
