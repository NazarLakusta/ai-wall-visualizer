"""Seed brand packaging and tint bases for dekor.showroom catalog brands."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, "/app")

from sqlalchemy import select

from app.database import SyncSessionLocal
from app.models import Brand, BrandPackSize, Color, ColorCategory, Store, StoreColor

STORE_SLUG = "dekor-showroom"

GLOSS_LINE_NAME = "Latex Gloss"
GLOSS_SOURCE_BRAND = "Latex Matt"
GLOSS_COLOR_COUNT = 8

BRAND_CONFIG: dict[str, dict] = {
    "Innen Wunder": {
        "paint_finish": "silk_matte",
        "coverage_sqm_per_liter": 11.0,
        "recommended_coats": 2,
        "packs": [
            (1.0, 320, "1 л"),
            (2.5, 720, "2.5 л"),
            (5.0, 1350, "5 л"),
            (10.0, 2500, "10 л"),
        ],
    },
    "Latex Matt": {
        "paint_finish": "matte",
        "coverage_sqm_per_liter": 12.0,
        "recommended_coats": 2,
        "packs": [
            (1.0, 280, "1 л"),
            (2.5, 620, "2.5 л"),
            (5.0, 1150, "5 л"),
            (10.0, 2100, "10 л"),
        ],
    },
    "Innen Latex": {
        "paint_finish": "matte",
        "coverage_sqm_per_liter": 13.0,
        "recommended_coats": 2,
        "packs": [
            (0.9, 195, "0.9 л"),
            (2.5, 480, "2.5 л"),
            (5.0, 890, "5 л"),
            (10.0, 1650, "10 л"),
        ],
    },
    "Koala": {
        "paint_finish": "matte",
        "coverage_sqm_per_liter": 12.0,
        "recommended_coats": 2,
        "packs": [
            (1.0, 175, "1 л"),
            (2.5, 420, "2.5 л"),
            (5.0, 780, "5 л"),
            (10.0, 1450, "10 л"),
        ],
    },
}

BASE_A = {ColorCategory.WHITE, ColorCategory.PASTEL, ColorCategory.YELLOW}
BASE_B = {ColorCategory.GREY, ColorCategory.BEIGE, ColorCategory.GREEN, ColorCategory.PASTEL}
BASE_C = {ColorCategory.DARK, ColorCategory.RED, ColorCategory.BLUE, ColorCategory.BROWN}

SURCHARGE = {"A": 0.0, "B": 5.0, "C": 15.0}


def tint_for_category(category: ColorCategory) -> str:
    if category in BASE_C:
        return "C"
    if category in BASE_A:
        return "A"
    return "B"


def sync_packs(db, brand: Brand, packs: list[tuple[float, float, str]]) -> None:
    existing = list(
        db.scalars(select(BrandPackSize).where(BrandPackSize.brand_id == brand.id)).all()
    )
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


def seed_gloss_line(db) -> None:
    store = db.scalar(select(Store).where(Store.slug == STORE_SLUG))
    source = db.scalar(select(Brand).where(Brand.name == GLOSS_SOURCE_BRAND))
    if not store or not source:
        return

    gloss = db.scalar(select(Brand).where(Brand.name == GLOSS_LINE_NAME))
    if not gloss:
        gloss = Brand(
            name=GLOSS_LINE_NAME,
            country="UA",
            paint_finish="gloss",
            coverage_sqm_per_liter=source.coverage_sqm_per_liter or 12.0,
            recommended_coats=source.recommended_coats or 2,
            active=True,
        )
        db.add(gloss)
        db.flush()
    else:
        gloss.paint_finish = "gloss"
        gloss.active = True

    source_packs = list(
        db.scalars(select(BrandPackSize).where(BrandPackSize.brand_id == source.id, BrandPackSize.active.is_(True))).all()
    )
    for i, p in enumerate(source_packs):
        row = db.scalar(
            select(BrandPackSize).where(
                BrandPackSize.brand_id == gloss.id,
                BrandPackSize.volume_liters == p.volume_liters,
            )
        )
        if row:
            row.price_uah = round(p.price_uah * 1.08)
            row.label = p.label
            row.active = True
        else:
            db.add(
                BrandPackSize(
                    brand_id=gloss.id,
                    volume_liters=p.volume_liters,
                    price_uah=round(p.price_uah * 1.08),
                    label=p.label,
                    sort_order=i,
                    active=True,
                )
            )

    source_colors = list(
        db.scalars(select(Color).where(Color.brand_id == source.id, Color.active.is_(True)).limit(GLOSS_COLOR_COUNT)).all()
    )
    for c in source_colors:
        code = (c.manufacturer_code or "C").replace("LM-", "LG-").replace("LM", "LG")
        if not code.startswith("LG"):
            code = f"LG-{code}"
        existing = db.scalar(
            select(Color).where(Color.brand_id == gloss.id, Color.manufacturer_code == code)
        )
        if not existing:
            existing = Color(
                brand_id=gloss.id,
                name=c.name,
                hex=c.hex,
                manufacturer_code=code,
                category=c.category,
                tint_base=c.tint_base,
                base_surcharge_percent=c.base_surcharge_percent,
                active=True,
            )
            db.add(existing)
            db.flush()

        listing = db.scalar(
            select(StoreColor).where(StoreColor.store_id == store.id, StoreColor.color_id == existing.id)
        )
        src_listing = db.scalar(
            select(StoreColor).where(StoreColor.store_id == store.id, StoreColor.color_id == c.id)
        )
        price = round((src_listing.price_per_sqm if src_listing and src_listing.price_per_sqm else c.price_per_sqm or 0) * 1.1, 2)
        if listing:
            listing.price_per_sqm = price
            listing.active = True
            listing.in_stock = True
        else:
            db.add(
                StoreColor(
                    store_id=store.id,
                    color_id=existing.id,
                    price_per_sqm=price,
                    in_stock=True,
                    active=True,
                )
            )
    print(f"Gloss line '{GLOSS_LINE_NAME}': {len(source_colors)} colors for {STORE_SLUG}")


def main() -> None:
    with SyncSessionLocal() as db:
        for brand_name, cfg in BRAND_CONFIG.items():
            brand = db.scalar(select(Brand).where(Brand.name == brand_name))
            if not brand:
                print(f"Skip missing brand: {brand_name}")
                continue

            brand.coverage_sqm_per_liter = cfg["coverage_sqm_per_liter"]
            brand.recommended_coats = cfg["recommended_coats"]
            brand.paint_finish = cfg.get("paint_finish", "matte")
            sync_packs(db, brand, cfg["packs"])
            print(f"Brand {brand_name}: {cfg.get('paint_finish', 'matte')}, {len(cfg['packs'])} pack sizes")

            colors = list(db.scalars(select(Color).where(Color.brand_id == brand.id)).all())
            for color in colors:
                base = tint_for_category(color.category)
                color.tint_base = base
                color.base_surcharge_percent = SURCHARGE[base]
            print(f"  → {len(colors)} colors with tint base")

        seed_gloss_line(db)
        db.commit()
        print("Done.")


if __name__ == "__main__":
    main()
