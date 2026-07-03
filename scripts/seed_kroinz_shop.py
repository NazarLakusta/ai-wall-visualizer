"""Seed KROINZ shop: RAL palette + RAL colors + KROINZ paint products linked to RAL.

Usage (inside Docker):
    docker compose exec api python /scripts/seed_kroinz_shop.py <store_slug> [ral_csv_path]

- <store_slug>       slug магазину (напр. kroinz-shop)
- [ral_csv_path]     шлях до CSV з RAL-кольорами (за замовч. /scripts/ral.csv)
                     колонки: name, hex, category, palette_name|brand_name, manufacturer_code

Скрипт ідемпотентний: повторний запуск оновлює, а не дублює.
"""

import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, "/app")

from sqlalchemy import select

from app.database import SyncSessionLocal
from app.models import (
    Brand,
    BrandPackSize,
    BrandPalette,
    Color,
    ColorCategory,
    ColorPalette,
    Store,
    StoreBrand,
    StoreColor,
)

RAL_PALETTE_NAME = "RAL"

# (name, finish, coverage m2/l, coats, [(volume_l, price_uah, label), ...])
PRODUCTS: list[dict] = [
    {
        "name": "KROINZ Whitex Farbe",
        "finish": "matte",
        "coverage": 8.0,
        "coats": 2,
        "packs": [(1.0, 280, "1 л"), (5.0, 1050, "5 л"), (10.0, 1950, "10 л")],
    },
    {
        "name": "KROINZ Latex Matt",
        "finish": "matte",
        "coverage": 10.0,
        "coats": 2,
        "packs": [(1.0, 360, "1 л"), (5.0, 1450, "5 л"), (10.0, 2650, "10 л")],
    },
    {
        "name": "KROINZ Innen Wunder",
        "finish": "silk_matte",
        "coverage": 10.0,
        "coats": 2,
        "packs": [(1.0, 420, "1 л"), (5.0, 1750, "5 л"), (10.0, 3200, "10 л")],
    },
    {
        "name": "KROINZ Extra weise",
        "finish": "matte",
        "coverage": 8.0,
        "coats": 2,
        "packs": [(1.0, 300, "1 л"), (5.0, 1200, "5 л"), (10.0, 2200, "10 л")],
    },
    {
        "name": "KROINZ Seiden Matt Latex",
        "finish": "silk_matte",
        "coverage": 10.0,
        "coats": 2,
        "packs": [(1.0, 480, "1 л"), (5.0, 2050, "5 л"), (10.0, 3800, "10 л")],
    },
]


def ensure_ral_palette(db) -> ColorPalette:
    palette = db.scalar(select(ColorPalette).where(ColorPalette.name == RAL_PALETTE_NAME))
    if not palette:
        palette = ColorPalette(name=RAL_PALETTE_NAME, code_system="ral", active=True)
        db.add(palette)
        db.flush()
    else:
        palette.code_system = "ral"
        palette.active = True
    return palette


def load_ral_colors(db, store_id: int, palette_id: int, csv_path: Path) -> int:
    if not csv_path.exists():
        print(f"  ! CSV {csv_path} не знайдено — кольори RAL пропущено.")
        print("    Спарсіть: py -3 scripts/parse_farbaland.py --catalog ral -o scripts/ral.csv")
        return 0

    added = 0
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = {c.lower(): c for c in (reader.fieldnames or [])}
        name_c = cols.get("name")
        hex_c = cols.get("hex")
        cat_c = cols.get("category")
        code_c = cols.get("manufacturer_code")
        if not (name_c and hex_c and cat_c):
            print("  ! У CSV мають бути колонки name, hex, category")
            return 0
        for row in reader:
            name = (row.get(name_c) or "").strip()
            hex_val = (row.get(hex_c) or "").strip()
            if hex_val and not hex_val.startswith("#"):
                hex_val = f"#{hex_val}"
            cat_raw = (row.get(cat_c) or "").strip()
            code = (row.get(code_c) or "").strip() if code_c else None
            if not name or not hex_val:
                continue
            try:
                category = ColorCategory(cat_raw)
            except ValueError:
                category = ColorCategory.WHITE

            color = db.scalar(
                select(Color).where(
                    Color.palette_id == palette_id,
                    Color.name == name,
                    Color.hex == hex_val,
                )
            )
            if not color:
                color = Color(
                    palette_id=palette_id,
                    name=name,
                    hex=hex_val,
                    manufacturer_code=code or None,
                    category=category,
                    active=True,
                )
                db.add(color)
                db.flush()
                added += 1
            else:
                color.manufacturer_code = code or color.manufacturer_code
                color.category = category
                color.active = True

            listing = db.scalar(
                select(StoreColor).where(
                    StoreColor.store_id == store_id,
                    StoreColor.color_id == color.id,
                )
            )
            if listing:
                listing.active = True
            else:
                db.add(StoreColor(store_id=store_id, color_id=color.id, active=True, in_stock=True))
    return added


def sync_packs(db, brand: Brand, packs: list[tuple[float, float, str]]) -> None:
    existing = list(db.scalars(select(BrandPackSize).where(BrandPackSize.brand_id == brand.id)).all())
    for i, (vol, price, label) in enumerate(packs):
        row = next((p for p in existing if abs(p.volume_liters - vol) < 0.01), None)
        if row:
            row.price_uah = price
            row.label = label
            row.sort_order = i
            row.active = True
        else:
            db.add(
                BrandPackSize(
                    brand_id=brand.id,
                    volume_liters=vol,
                    price_uah=price,
                    label=label,
                    sort_order=i,
                    active=True,
                )
            )


def link_store_brand(db, store_id: int, brand_id: int) -> None:
    link = db.scalar(
        select(StoreBrand).where(StoreBrand.store_id == store_id, StoreBrand.brand_id == brand_id)
    )
    if link:
        link.active = True
    else:
        db.add(StoreBrand(store_id=store_id, brand_id=brand_id, active=True))


def link_brand_palette(db, brand_id: int, palette_id: int) -> None:
    link = db.scalar(
        select(BrandPalette).where(
            BrandPalette.brand_id == brand_id,
            BrandPalette.palette_id == palette_id,
        )
    )
    if not link:
        db.add(BrandPalette(brand_id=brand_id, palette_id=palette_id))


def main() -> None:
    slug = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("STORE_SLUG", "kroinz-shop")
    csv_arg = sys.argv[2] if len(sys.argv) > 2 else "/scripts/ral.csv"
    csv_path = Path(csv_arg)
    if not csv_path.is_absolute() and not csv_path.exists():
        alt = Path(__file__).resolve().parent / csv_path.name
        if alt.exists():
            csv_path = alt

    with SyncSessionLocal() as db:
        store = db.scalar(select(Store).where(Store.slug == slug, Store.active.is_(True)))
        if not store:
            print(f"Store '{slug}' not found. Create it in /platform/ first.")
            sys.exit(1)

        palette = ensure_ral_palette(db)
        db.flush()
        print(f"Palette: {palette.name} (id={palette.id})")

        added = load_ral_colors(db, store.id, palette.id, csv_path)
        print(f"RAL colors linked to store: +{added} new")

        for cfg in PRODUCTS:
            brand = db.scalar(select(Brand).where(Brand.name == cfg["name"]))
            if not brand:
                brand = Brand(
                    name=cfg["name"],
                    country="UA",
                    paint_finish=cfg["finish"],
                    coverage_sqm_per_liter=cfg["coverage"],
                    recommended_coats=cfg["coats"],
                    active=True,
                )
                db.add(brand)
                db.flush()
            else:
                brand.paint_finish = cfg["finish"]
                brand.coverage_sqm_per_liter = cfg["coverage"]
                brand.recommended_coats = cfg["coats"]
                brand.active = True

            sync_packs(db, brand, cfg["packs"])
            link_store_brand(db, store.id, brand.id)
            link_brand_palette(db, brand.id, palette.id)
            print(f"  Product: {cfg['name']} ({cfg['finish']}) -> RAL")

        db.commit()
        print(f"\nOK: store '{store.name}' ({slug})")
        print(f"  Products: {len(PRODUCTS)}, all linked to palette RAL")


if __name__ == "__main__":
    main()
