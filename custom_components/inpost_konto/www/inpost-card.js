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
            const przygaszone = p.status === "odebrana" ? "opacity:.6;" : "";
            return `
        <div style="display:flex;gap:12px;padding:12px 0;border-top:1px solid var(--divider-color);${przygaszone}">
          <ha-icon icon="${s.ikona}" style="color:${s.kolor};--mdc-icon-size:22px"></ha-icon>
          <div style="flex:1;min-width:0">
            <div>${esc(p.nadawca || "Nieznany nadawca")} · <span style="color:${s.kolor}">${s.etykieta}</span></div>
            ${punkt ? `<div style="font-size:13px;color:var(--secondary-text-color)">${punkt}</div>` : ""}
            ${termin ? `<div style="font-size:13px;color:var(--warning-color, #ffa600)">${esc(termin)}</div>` : ""}
          </div>
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

if (typeof module !== "undefined") module.exports = { terminTekst, LICZNIKI, STATUSY, esc };
