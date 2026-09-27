// Sprawdzenie logiki karty: liczenie terminu i kubelki licznikow.
// `node tests/test_card.cjs` z katalogu repo. Bez frameworka, bez przegladarki.
const assert = require("assert");

// Karta dziedziczy po HTMLElement — w node tej klasy nie ma, wiec dajemy atrape.
globalThis.HTMLElement = class {};
const { terminTekst, LICZNIKI, STATUSY } = require("../custom_components/inpost_konto/www/inpost-card.js");

const za = (ms) => new Date(Date.now() + ms).toISOString();

// Zaokraglamy w dol: "zostalo 2 h" przy 2 h 59 min niedoszacowuje termin, czyli myli
// sie w bezpieczna strone. Stad minuta zapasu w tescie.
assert.match(terminTekst(za(3 * 3600e3 + 60e3)), /zostało 3 h/, "kilka godzin liczymy w godzinach");
assert.match(terminTekst(za(72 * 3600e3 + 60e3)), /zostało 3 dni/, "powyzej 48 h liczymy w dniach");
assert.match(terminTekst(za(-3600e3)), /termin minął/, "przeterminowana paczka ma to powiedziec wprost");
assert.strictEqual(terminTekst("cokolwiek"), null, "smieciowa data nie moze wysypac karty");

// Kazdy status z integracji musi miec swoj wpis — inaczej karta pokaze "nieznany".
for (const s of ["do_odbioru", "w_drodze", "w_dostawie", "odebrana", "zwrot", "problem", "zarejestrowana", "nieznany"]) {
  assert.ok(STATUSY[s], `brak opisu dla statusu ${s}`);
}

const paczki = [
  { status: "do_odbioru" },
  { status: "w_drodze" },
  { status: "w_dostawie" },
  { status: "odebrana" },
  { status: "problem" },
];
const liczby = LICZNIKI.map(([nazwa, filtr]) => [nazwa, paczki.filter(filtr).length]);
assert.deepStrictEqual(liczby, [
  ["do odbioru", 1],
  ["w drodze", 2],
  ["wszystkie", 5],
  ["problemy", 1],
]);

console.log("OK — karta przeszla sprawdzenia");
