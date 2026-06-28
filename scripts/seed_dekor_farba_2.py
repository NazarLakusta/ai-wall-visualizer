"""Seed test paint catalog for store dekor-farba-2 (matte / silk / gloss mix)."""

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
    Color,
    ColorCategory,
    DecorativeColor,
    DecorativeMaterial,
    Store,
    StoreBrand,
    StoreColor,
)

STORE_SLUG = os.environ.get("STORE_SLUG", "dekor-farba-2")

# Popular UA-market style brands with finish spread for testing.
BRANDS: list[dict] = [
    {
        "name": "Dulux Trade Vinyl Matt",
        "country": "GB",
        "paint_finish": "matte",
        "coverage_sqm_per_liter": 12.0,
        "packs": [(1.0, 420, "1 л"), (2.5, 950, "2.5 л"), (5.0, 1780, "5 л")],
        "colors": [
            ("Білий сніг", "#F8F8F5", "DX-M-001", "Білі", 248),
            ("Світло-сірий", "#D4D2CC", "DX-M-032", "Сірі", 255),
            ("Тауп ніжний", "#B8AEA0", "DX-M-048", "Бежеві", 262),
            ("Оливковий пастель", "#C4C8B4", "DX-M-071", "Зелені", 268),
            ("Антрацит світлий", "#6E6C66", "DX-M-090", "Темні", 278),
        ],
    },
    {
        "name": "Tikkurila Euro 7",
        "country": "FI",
        "paint_finish": "matte",
        "coverage_sqm_per_liter": 11.5,
        "packs": [(0.9, 385, "0.9 л"), (2.7, 1020, "2.7 л"), (9.0, 3100, "9 л")],
        "colors": [
            ("Білий", "#FFFFFF", "TK-E7-01", "Білі", 235),
            ("Сірий дим", "#C0BEB8", "TK-E7-22", "Сірі", 242),
            ("Пісочний", "#DCC8A8", "TK-E7-35", "Бежеві", 248),
            ("Блакитний світлий", "#B8CCD8", "TK-E7-58", "Сині", 255),
            ("Графіт", "#5A5854", "TK-E7-77", "Темні", 265),
        ],
    },
    {
        "name": "Caparol Samtex 7",
        "country": "DE",
        "paint_finish": "silk_matte",
        "coverage_sqm_per_liter": 11.0,
        "packs": [(1.0, 480, "1 л"), (2.5, 1080, "2.5 л"), (5.0, 1980, "5 л")],
        "colors": [
            ("Класичний білий", "#FAFAF8", "CP-S7-01", "Білі", 285),
            ("Перлинний беж", "#EDE4D4", "CP-S7-14", "Бежеві", 292),
            ("Сріблястий сірий", "#B8B6B0", "CP-S7-28", "Сірі", 298),
            ("М'ятний шовк", "#D0E0D4", "CP-S7-42", "Зелені", 305),
            ("Лавандовий", "#E0DCE8", "CP-S7-55", "Пастельні", 308),
        ],
    },
    {
        "name": "Alpina Das Klassische",
        "country": "DE",
        "paint_finish": "silk_matte",
        "coverage_sqm_per_liter": 11.0,
        "packs": [(1.0, 395, "1 л"), (2.5, 880, "2.5 л"), (10.0, 3200, "10 л")],
        "colors": [
            ("Білий шовк", "#F6F4EF", "AL-KL-01", "Білі", 268),
            ("Кремовий", "#F0E6D4", "AL-KL-12", "Бежеві", 275),
            ("Сірий шелк", "#C8C4BC", "AL-KL-25", "Сірі", 282),
            ("Рожевий пудра", "#E8D4D0", "AL-KL-38", "Пастельні", 288),
        ],
    },
    {
        "name": "Śnieżka Akrylit GT",
        "country": "PL",
        "paint_finish": "gloss",
        "coverage_sqm_per_liter": 10.5,
        "packs": [(1.0, 310, "1 л"), (3.0, 820, "3 л"), (10.0, 2450, "10 л")],
        "colors": [
            ("Білий глянець", "#FFFFFF", "SN-GT-01", "Білі", 198),
            ("Світло-бежевий", "#EDE0CC", "SN-GT-15", "Бежеві", 205),
            ("Сірий глянець", "#B0AEA8", "SN-GT-28", "Сірі", 212),
            ("Блакитний", "#A8C0D0", "SN-GT-41", "Сині", 218),
            ("Червоний теракотовий", "#C87868", "SN-GT-54", "Червоні", 228),
        ],
    },
    {
        "name": "Marshall W700",
        "country": "PL",
        "paint_finish": "gloss",
        "coverage_sqm_per_liter": 10.0,
        "packs": [(1.0, 340, "1 л"), (2.5, 780, "2.5 л"), (5.0, 1450, "5 л")],
        "colors": [
            ("Білий W700", "#FAFAFA", "MW7-01", "Білі", 215),
            ("Сірий перл", "#C4C2BC", "MW7-18", "Сірі", 222),
            ("Капучіно", "#C8B8A4", "MW7-31", "Бежеві", 228),
            ("Смарагдовий", "#88A898", "MW7-44", "Зелені", 235),
        ],
    },
]

DECOR = {
    "name": "Венеціанська штукатурка",
    "category": "Декоративна штукатурка",
    "shades": [
        ("#C8C0B0", "Травертин", 580),
        ("#E8E0D0", "Перлинний", 620),
    ],
}

BASE_A = {ColorCategory.WHITE, ColorCategory.PASTEL, ColorCategory.YELLOW}
BASE_C = {ColorCategory.DARK, ColorCategory.RED, ColorCategory.BLUE, ColorCategory.BROWN}
SURCHARGE = {"A": 0.0, "B": 5.0, "C": 15.0}


def tint_for_category(category: ColorCategory) -> str:
    if category in BASE_C:
        return "C"
    if category in BASE_A:
        return "A"
    return "B"


def _upsert_color(
    db,
    store_id: int,
    brand_id: int,
    name: str,
    hex_val: str,
    code: str,
    category: ColorCategory,
    price: float,
) -> None:
    color = db.scalar(select(Color).where(Color.brand_id == brand_id, Color.manufacturer_code == code))
    if not color:
        color = db.scalar(select(Color).where(Color.brand_id == brand_id, Color.name == name, Color.hex == hex_val))
    if not color:
        color = Color(
            brand_id=brand_id,
            name=name,
            hex=hex_val,
            manufacturer_code=code,
            category=category,
            active=True,
        )
        db.add(color)
        db.flush()

    base = tint_for_category(category)
    color.tint_base = base
    color.base_surcharge_percent = SURCHARGE[base]
    color.active = True

    listing = db.scalar(select(StoreColor).where(StoreColor.store_id == store_id, StoreColor.color_id == color.id))
    if listing:
        listing.active = True
        listing.price_per_sqm = price
        listing.in_stock = True
    else:
        db.add(
            StoreColor(
                store_id=store_id,
                color_id=color.id,
                price_per_sqm=price,
                in_stock=True,
                active=True,
            )
        )


def _sync_packs(db, brand: Brand, packs: list[tuple[float, float, str]]) -> None:
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


def _link_brand(db, store_id: int, brand_id: int) -> None:
    link = db.scalar(
        select(StoreBrand).where(StoreBrand.store_id == store_id, StoreBrand.brand_id == brand_id)
    )
    if link:
        link.active = True
    else:
        db.add(StoreBrand(store_id=store_id, brand_id=brand_id, active=True))


def _seed_decor(db, store_id: int) -> int:
    material = db.scalar(
        select(DecorativeMaterial).where(
            DecorativeMaterial.store_id == store_id,
            DecorativeMaterial.name == DECOR["name"],
        )
    )
    if not material:
        material = DecorativeMaterial(
            store_id=store_id,
            name=DECOR["name"],
            category=DECOR["category"],
            texture_scale=1.0,
            active=True,
            in_stock=True,
        )
        db.add(material)
        db.flush()

    added = 0
    for hex_val, name, price in DECOR["shades"]:
        row = db.scalar(
            select(DecorativeColor).where(
                DecorativeColor.material_id == material.id,
                DecorativeColor.name == name,
            )
        )
        if row:
            row.hex = hex_val
            row.price_per_sqm = price
            row.active = True
            row.in_stock = True
        else:
            db.add(
                DecorativeColor(
                    material_id=material.id,
                    name=name,
                    hex=hex_val,
                    price_per_sqm=price,
                    active=True,
                    in_stock=True,
                )
            )
            added += 1
    return added


def main() -> None:
    with SyncSessionLocal() as db:
        store = db.scalar(select(Store).where(Store.slug == STORE_SLUG, Store.active.is_(True)))
        if not store:
            print(f"Store '{STORE_SLUG}' not found. Create it in super-admin first.")
            sys.exit(1)

        total_colors = 0
        finish_counts: dict[str, int] = {"matte": 0, "silk_matte": 0, "gloss": 0}

        for cfg in BRANDS:
            brand = db.scalar(select(Brand).where(Brand.name == cfg["name"]))
            if not brand:
                brand = Brand(
                    name=cfg["name"],
                    country=cfg["country"],
                    paint_finish=cfg["paint_finish"],
                    coverage_sqm_per_liter=cfg["coverage_sqm_per_liter"],
                    recommended_coats=2,
                    active=True,
                )
                db.add(brand)
                db.flush()
            else:
                brand.country = cfg["country"]
                brand.paint_finish = cfg["paint_finish"]
                brand.coverage_sqm_per_liter = cfg["coverage_sqm_per_liter"]
                brand.recommended_coats = 2
                brand.active = True

            _sync_packs(db, brand, cfg["packs"])
            _link_brand(db, store.id, brand.id)

            for name, hex_val, code, cat_name, price in cfg["colors"]:
                _upsert_color(db, store.id, brand.id, name, hex_val, code, ColorCategory(cat_name), price)
                total_colors += 1
                finish_counts[cfg["paint_finish"]] = finish_counts.get(cfg["paint_finish"], 0) + 1

            print(f"  {cfg['name']} ({cfg['paint_finish']}): {len(cfg['colors'])} colors")

        decor_added = _seed_decor(db, store.id)
        db.commit()

        print(f"\nOK: store '{store.name}' ({STORE_SLUG})")
        print(f"  Paint colors: {total_colors}")
        print(f"  Finishes — matte: {finish_counts['matte']}, silk: {finish_counts['silk_matte']}, gloss: {finish_counts['gloss']}")
        print(f"  Decor shades: {len(DECOR['shades'])} ({decor_added} new)")
        print(f"  Brands: {len(BRANDS)}")


if __name__ == "__main__":
    main()
