"""Generator ikony integracji — `python brands/make_icon.py`.

Ikona jest rysowana, nie malowana recznie, zeby dalo sie ja odtworzyc i poprawic
jednym parametrem. Motyw: skrytki paczkomatu, jedna otwarta (ta z Twoja paczka).
Swiadomie NIE jest to logo InPostu — to wlasny rysunek, zeby nie podszywac sie
pod ich znak towarowy.

Wymaga tylko Pillow. Efekt: icon.png (256) i icon@2x.png (512) — dokladnie te
rozmiary i nazwy, ktorych oczekuje repozytorium home-assistant/brands.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 512  # Rysujemy duzo i zmniejszamy — krawedzie wychodza gladsze.
AMBER = (245, 197, 24, 255)      # Tlo kafelka; czytelne i na jasnym, i na ciemnym motywie.
GRAPHITE = (27, 31, 39, 255)     # Zamkniete skrytki.
OPEN = (255, 252, 245, 255)      # Skrytka otwarta — ta jedna, na ktorej Ci zalezy.

OUT = Path(__file__).parent


def _rr(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], r: float, fill) -> None:
    draw.rounded_rectangle([round(v) for v in box], radius=round(r), fill=fill)


def build() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Bez przezroczystego marginesu: walidacja home-assistant/brands wymaga
    # obrazka przycietego do tresci. Zaokraglone rogi to jedyna przezroczystosc.
    _rr(draw, (0, 0, SIZE, SIZE), SIZE * 0.22, AMBER)

    # Siatka skrytek: lewa kolumna wezsza (3 male), prawa szersza (2 duze).
    pad = SIZE * 0.175
    gap = SIZE * 0.035
    left, top, right, bottom = pad, pad, SIZE - pad, SIZE - pad
    split = left + (right - left) * 0.42
    r = SIZE * 0.028

    col_h = (bottom - top - 2 * gap) / 3
    for i in range(3):
        y = top + i * (col_h + gap)
        _rr(draw, (left, y, split - gap / 2, y + col_h), r, GRAPHITE)

    big_h = (bottom - top - gap) / 2
    for i in range(2):
        y = top + i * (big_h + gap)
        # Gorna skrytka otwarta: jasne wnetrze i ciemna ramka wokol niego.
        fill = OPEN if i == 0 else GRAPHITE
        _rr(draw, (split + gap / 2, y, right, y + big_h), r, fill)
        if i == 0:
            b = SIZE * 0.022
            _rr(
                draw,
                (split + gap / 2 + b, y + b, right - b, y + big_h - b),
                r * 0.6,
                AMBER,
            )
            # Paczka w srodku otwartej skrytki.
            w = (right - split - gap / 2) * 0.42
            cx = (split + gap / 2 + right) / 2
            cy = y + big_h / 2
            _rr(draw, (cx - w / 2, cy - w / 2, cx + w / 2, cy + w / 2), r * 0.5, GRAPHITE)
    return img


if __name__ == "__main__":
    icon = build()
    icon.save(OUT / "icon@2x.png")
    icon.resize((256, 256), Image.LANCZOS).save(OUT / "icon.png")
    print(f"zapisano {OUT / 'icon.png'} (256) i icon@2x.png (512)")
