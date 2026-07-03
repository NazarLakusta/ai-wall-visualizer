"""Seed KROINZ paint catalog: RAL palette + RAL colors + products from official RRP.

Usage (inside Docker):
    docker compose exec api alembic upgrade head
    docker compose exec api python /scripts/seed_kroinz_shop.py dekor-showroom

Paint only (no facade, no decor, no primers).
Pack prices follow KROINZ Base A / Base C lines from the price list.
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

STORE_SLUG_DEFAULT = "dekor-showroom"
RAL_PALETTE_NAME = "RAL"

# Old demo / guessed product names to hide from the store.
LEGACY_BRAND_NAMES = {
    "Innen Wunder",
    "Latex Matt",
    "Innen Latex",
    "Koala",
    "Latex Matt Gloss",
    "KROINZ Whitex Farbe",
    "KROINZ Extra weise",
    "KROINZ Seiden Matt Latex",
}

BASE_A_CATEGORIES = {
    ColorCategory.WHITE,
    ColorCategory.PASTEL,
    ColorCategory.YELLOW,
}
BASE_C_CATEGORIES = {
    ColorCategory.DARK,
    ColorCategory.RED,
    ColorCategory.BLUE,
    ColorCategory.BROWN,
}

# finish, coverage m²/l, coats, packs: (volume_l, price_uah, label, tint_base A|C)
PRODUCTS: list[dict] = [
    {
        "name": "KROINZ Latex Matt",
        "finish": "matte",
        "coverage": 10.0,
        "coats": 2,
        "packs": [
            (1.0, 375, "1 л", "A"),
            (5.0, 1550, "5 л", "A"),
            (10.0, 2990, "10 л", "A"),
            (1.0, 320, "1 л", "C"),
            (4.7, 1200, "4.7 л", "C"),
            (9.4, 2280, "9.4 л", "C"),
        ],
    },
    {
        "name": "KROINZ Innen Wunder",
        "finish": "matte",
        "coverage": 10.0,
        "coats": 2,
        "packs": [
            (1.0, 300, "1 л", "A"),
            (5.0, 890, "5 л", "A"),
            (10.0, 1850, "10 л", "A"),
            (1.0, 210, "1 л", "C"),
            (4.7, 690, "4.7 л", "C"),
            (9.4, 1270, "9.4 л", "C"),
        ],
    },
    {
        "name": "KROINZ Seidenmatt Farbe",
        "finish": "silk_matte",
        "coverage": 10.0,
        "coats": 2,
        "packs": [
            (1.0, 450, "1 л", "A"),
            (5.0, 1950, "5 л", "A"),
            (10.0, 3850, "10 л", "A"),
            (1.0, 370, "1 л", "C"),
            (4.7, 1500, "4.7 л", "C"),
            (9.4, 2950, "9.4 л", "C"),
        ],
    },
    {
        "name": "KROINZ ExtraWeiße Waschbare",
        "finish": "matte",
        "coverage": 8.0,
        "coats": 2,
        "packs": [
            (1.0, 500, "1 л", "A"),
            (5.0, 2300, "5 л", "A"),
            (10.0, 4500, "10 л", "A"),
            (14.0, 6200, "14 л", "A"),
            (1.0, 400, "1 л", "C"),
            (4.7, 1700, "4.7 л", "C"),
            (12.2, 3700, "12.2 л", "C"),
        ],
    },
    {
        "name": "KROINZ Eco White",
        "finish": "matte",
        "coverage": 8.0,
        "coats": 2,
        "packs": [
            (5.0, 550, "5 л", "A"),
            (10.0, 950, "10 л", "A"),
        ],
    },
]


def tint_for_category(category: ColorCategory) -> str:
    if category in BASE_C_CATEGORIES:
        return "C"
    if category in BASE_A_CATEGORIES:
        return "A"
    return "B"


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
        print(f"  ! CSV {csv_path} not found — RAL colors skipped.")
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
            print("  ! CSV must have columns: name, hex, category")
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

            tint_base = tint_for_category(category)
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
                    tint_base=tint_base,
                    base_surcharge_percent=0.0,
                    active=True,
                )
                db.add(color)
                db.flush()
                added += 1
            else:
                color.manufacturer_code = code or color.manufacturer_code
                color.category = category
                color.tint_base = tint_base
                color.base_surcharge_percent = 0.0
                color.active = True

            listing = db.scalar(
                select(StoreColor).where(
                    StoreColor.store_id == store_id,
                    StoreColor.color_id == color.id,
                )
            )
            if listing:
                listing.active = True
                listing.in_stock = True
            else:
                db.add(StoreColor(store_id=store_id, color_id=color.id, active=True, in_stock=True))
    return added


def sync_packs(db, brand: Brand, packs: list[tuple[float, float, str, str | None]]) -> None:
    existing = list(db.scalars(select(BrandPackSize).where(BrandPackSize.brand_id == brand.id)).all())
    for i, (vol, price, label, tint_base) in enumerate(packs):
        base = (tint_base or "").upper() or None
        row = next(
            (
                p
                for p in existing
                if abs(p.volume_liters - vol) < 0.01 and (p.tint_base or None) == base
            ),
            None,
        )
        if row:
            row.price_uah = price
            row.label = label
            row.tint_base = base
            row.sort_order = i
            row.active = True
        else:
            db.add(
                BrandPackSize(
                    brand_id=brand.id,
                    volume_liters=vol,
                    price_uah=price,
                    tint_base=base,
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


def deactivate_legacy_catalog(db, store_id: int) -> tuple[int, int]:
    legacy_brands = list(db.scalars(select(Brand).where(Brand.name.in_(LEGACY_BRAND_NAMES))).all())
    legacy_ids = [brand.id for brand in legacy_brands]
    if not legacy_ids:
        return 0, 0

    disabled_brands = 0
    for link in db.scalars(
        select(StoreBrand).where(
            StoreBrand.store_id == store_id,
            StoreBrand.brand_id.in_(legacy_ids),
            StoreBrand.active.is_(True),
        )
    ).all():
        link.active = False
        disabled_brands += 1

    disabled_colors = 0
    for listing in db.scalars(
        select(StoreColor)
        .join(Color, Color.id == StoreColor.color_id)
        .where(
            StoreColor.store_id == store_id,
            Color.brand_id.in_(legacy_ids),
            StoreColor.active.is_(True),
        )
    ).all():
        listing.active = False
        disabled_colors += 1

    return disabled_brands, disabled_colors


def main() -> None:
    slug = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("STORE_SLUG", STORE_SLUG_DEFAULT)
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
                    country="DE",
                    paint_finish=cfg["finish"],
                    coverage_sqm_per_liter=cfg["coverage"],
                    recommended_coats=cfg["coats"],
                    active=True,
                )
                db.add(brand)
                db.flush()
            else:
                brand.country = "DE"
                brand.paint_finish = cfg["finish"]
                brand.coverage_sqm_per_liter = cfg["coverage"]
                brand.recommended_coats = cfg["coats"]
                brand.active = True

            sync_packs(db, brand, cfg["packs"])
            link_store_brand(db, store.id, brand.id)
            link_brand_palette(db, brand.id, palette.id)
            print(f"  Product: {cfg['name']} ({cfg['finish']}) — {len(cfg['packs'])} pack lines")

        disabled_brands, disabled_colors = deactivate_legacy_catalog(db, store.id)
        db.commit()

        print(f"\nOK: store '{store.name}' ({slug})")
        print(f"  Paint products: {len(PRODUCTS)} (RAL palette linked)")
        print(f"  Legacy hidden: {disabled_brands} products, {disabled_colors} colors")


if __name__ == "__main__":
    main()
