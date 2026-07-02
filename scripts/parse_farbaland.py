"""Парсер каталогів кольорів з farbaland.com.

Дістає з обраних каталогів (RAL, NCS, Tikkurila тощо) назву, код та HEX
кожного кольору і зберігає у CSV, сумісний з імпортом кольорів в адмінці
(колонки: name, hex, category, brand_name, manufacturer_code).

Використовує лише стандартну бібліотеку Python — жодних залежностей.

Приклади:
    # один каталог RAL у бренд "RAL"
    python scripts/parse_farbaland.py --catalog ral --brand "RAL" -o ral.csv

    # кілька каталогів одразу (кожен у свій бренд = назва каталогу)
    python scripts/parse_farbaland.py --catalog ral,ncs-colour-system,dulux-colour-palette -o colors.csv

    # усі відомі каталоги
    python scripts/parse_farbaland.py --all -o all_colors.csv
"""

from __future__ import annotations

import argparse
import colorsys
import csv
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "https://farbaland.com"
LIST_URL = BASE + "/uk/colors/category/{slug}/?page={page}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "uk,en;q=0.8",
}

# Слаги каталогів на сайті -> зручна назва бренду за замовчуванням.
KNOWN_CATALOGS: dict[str, str] = {
    "ral": "RAL",
    "ncs-colour-system": "NCS",
    "tikkurila-symphony": "Tikkurila Symphony",
    "3d-system-plus": "Caparol 3D-System plus",
    "monicolor-nova": "Monicolor NOVA",
    "sadolin-colour-palette": "Sadolin",
    "dulux-colour-palette": "Dulux",
    "oikos-color": "Oikos",
    "baumit-life": "Baumit Life",
    "san-marco": "San Marco",
    "pantone-solid-coated": "Pantone Solid Coated",
    "benjamin-moore-classic-colors": "Benjamin Moore",
    "sherwin-williams-color": "Sherwin-Williams",
}

PRODUCT_RE = re.compile(r'href="/uk/colors/product/([^"/]+)/"')
ALT_RE = re.compile(r'alt="([^"]+)"')
HEX_RE = re.compile(r"(?:%23|#)([0-9A-Fa-f]{6})")


def fetch(url: str, retries: int = 3) -> str:
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            if attempt == retries:
                raise
            print(f"  ! помилка {exc}, спроба {attempt}/{retries}", file=sys.stderr)
            time.sleep(2 * attempt)
    return ""


def classify_category(hex_code: str) -> str:
    """Груба класифікація кольору у категорію ColorCategory за HEX."""
    h = hex_code.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    hue_deg = hue * 360

    if light >= 0.92 and sat < 0.15:
        return "Білі"
    if light <= 0.18:
        return "Темні"
    if sat < 0.12:
        return "Сірі"
    if light >= 0.80 and sat < 0.45:
        return "Пастельні"

    if hue_deg < 20 or hue_deg >= 345:
        return "Червоні"
    if hue_deg < 45:
        # помаранчево-коричнева зона: темніше -> коричневий, світліше -> бежевий
        return "Коричневі" if light < 0.55 else "Бежеві"
    if hue_deg < 70:
        return "Жовті"
    if hue_deg < 170:
        return "Зелені"
    if hue_deg < 260:
        return "Сині"
    return "Червоні"


def parse_page(html: str) -> list[dict]:
    """Витягує кольори з HTML сторінки каталогу."""
    rows: list[dict] = []
    seen: set[str] = set()
    for m in PRODUCT_RE.finditer(html):
        slug = m.group(1)
        if slug in seen:
            continue
        seen.add(slug)
        window = html[m.start() : m.start() + 900]
        alt_m = ALT_RE.search(window)
        hex_m = HEX_RE.search(window)
        if not hex_m:
            continue
        name = alt_m.group(1).strip() if alt_m else slug
        hex_code = "#" + hex_m.group(1).upper()
        rows.append(
            {
                "name": name,
                "hex": hex_code,
                "manufacturer_code": name,
                "slug": slug,
            }
        )
    return rows


def scrape_catalog(slug: str, delay: float = 0.7, max_pages: int = 200) -> list[dict]:
    all_rows: list[dict] = []
    seen_slugs: set[str] = set()
    first_slug_prev_page: str | None = None
    page = 1
    while page <= max_pages:
        url = LIST_URL.format(slug=slug, page=page)
        html = fetch(url)
        rows = parse_page(html)
        if not rows:
            break
        # Якщо сайт зациклив на останній сторінці — зупиняємось.
        if rows[0]["slug"] == first_slug_prev_page:
            break
        first_slug_prev_page = rows[0]["slug"]
        new = [r for r in rows if r["slug"] not in seen_slugs]
        if not new:
            break
        for r in new:
            seen_slugs.add(r["slug"])
        all_rows.extend(new)
        print(f"  сторінка {page}: +{len(new)} (усього {len(all_rows)})")
        page += 1
        time.sleep(delay)
    return all_rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Парсер кольорів з farbaland.com")
    ap.add_argument(
        "--catalog",
        help="Слаг(и) каталогу через кому, напр.: ral,ncs-colour-system",
    )
    ap.add_argument("--all", action="store_true", help="Спарсити всі відомі каталоги")
    ap.add_argument(
        "--brand",
        help="Назва бренду для CSV (за замовч. — назва каталогу). "
        "Діє лише коли вказано один каталог.",
    )
    ap.add_argument("-o", "--output", default="colors.csv", help="Файл CSV")
    ap.add_argument("--delay", type=float, default=0.7, help="Пауза між сторінками, сек")
    args = ap.parse_args()

    if args.all:
        slugs = list(KNOWN_CATALOGS.keys())
    elif args.catalog:
        slugs = [s.strip() for s in args.catalog.split(",") if s.strip()]
    else:
        ap.error("Вкажіть --catalog <slug> або --all")

    out_rows: list[dict] = []
    for slug in slugs:
        brand = args.brand if (args.brand and len(slugs) == 1) else KNOWN_CATALOGS.get(slug, slug)
        print(f"Каталог '{slug}' -> бренд '{brand}'")
        rows = scrape_catalog(slug, delay=args.delay)
        for r in rows:
            out_rows.append(
                {
                    "name": r["name"],
                    "hex": r["hex"],
                    "category": classify_category(r["hex"]),
                    "palette_name": brand,
                    "manufacturer_code": r["manufacturer_code"],
                }
            )
        print(f"  готово: {len(rows)} кольорів\n")

    fields = ["name", "hex", "category", "palette_name", "manufacturer_code"]
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Збережено {len(out_rows)} кольорів у {args.output}")


if __name__ == "__main__":
    main()
