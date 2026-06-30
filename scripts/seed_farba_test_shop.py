"""Full demo catalog for store farba-test-shop: matte / silk / gloss + decor + packs."""

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
    DecorativeMaterialPackSize,
    Store,
    StoreBrand,
    StoreColor,
)

STORE_SLUG = os.environ.get("STORE_SLUG", "farba-test-shop")

# (name, hex, code, category, price_per_sqm)
ColorRow = tuple[str, str, str, str, float]

BRANDS: list[dict] = [
    {
        "name": "FTS Interior Matt",
        "country": "UA",
        "paint_finish": "matte",
        "coverage_sqm_per_liter": 12.0,
        "recommended_coats": 2,
        "packs": [(1.0, 295, "1 л"), (2.5, 650, "2.5 л"), (5.0, 1180, "5 л"), (10.0, 2150, "10 л")],
        "colors": [
            ("Білий мат", "#FAFAF8", "FTS-M-001", "Білі", 185),
            ("Кремовий", "#F2EBE0", "FTS-M-012", "Бежеві", 192),
            ("Світло-сірий", "#D4D2CC", "FTS-M-028", "Сірі", 198),
            ("Тауп", "#B8AEA0", "FTS-M-041", "Бежеві", 205),
            ("Оливковий", "#C4C8B4", "FTS-M-055", "Зелені", 212),
            ("Блакитний пастель", "#C8D8E4", "FTS-M-068", "Сині", 218),
            ("Графіт", "#6E6C66", "FTS-M-082", "Темні", 228),
        ],
    },
    {
        "name": "FTS Euro Comfort",
        "country": "PL",
        "paint_finish": "matte",
        "coverage_sqm_per_liter": 11.5,
        "recommended_coats": 2,
        "packs": [(0.9, 340, "0.9 л"), (2.7, 890, "2.7 л"), (9.0, 2680, "9 л")],
        "colors": [
            ("Білий", "#FFFFFF", "FTS-EC-01", "Білі", 210),
            ("Пісочний", "#E0D0B0", "FTS-EC-18", "Бежеві", 218),
            ("Сірий дим", "#B8B6B0", "FTS-EC-32", "Сірі", 225),
            ("Салатовий", "#D0DCC0", "FTS-EC-45", "Зелені", 232),
            ("Пудровий", "#E8D4D0", "FTS-EC-58", "Пастельні", 238),
            ("Коричневий молочний", "#A89888", "FTS-EC-71", "Коричневі", 245),
        ],
    },
    {
        "name": "FTS Budget Latex",
        "country": "UA",
        "paint_finish": "matte",
        "coverage_sqm_per_liter": 13.0,
        "recommended_coats": 2,
        "packs": [(1.0, 165, "1 л"), (3.0, 420, "3 л"), (10.0, 1280, "10 л")],
        "colors": [
            ("Білий економ", "#F8F8F5", "FTS-BL-01", "Білі", 145),
            ("Світло-беж", "#EDE4D4", "FTS-BL-14", "Бежеві", 152),
            ("Сірий світлий", "#C8C4BC", "FTS-BL-27", "Сірі", 158),
            ("Жовтуватий", "#F0E8C8", "FTS-BL-40", "Жовті", 162),
            ("Блакитний", "#B0C8D8", "FTS-BL-53", "Сині", 168),
        ],
    },
    {
        "name": "FTS Silk Touch",
        "country": "DE",
        "paint_finish": "silk_matte",
        "coverage_sqm_per_liter": 11.0,
        "recommended_coats": 2,
        "packs": [(1.0, 420, "1 л"), (2.5, 950, "2.5 л"), (5.0, 1750, "5 л")],
        "colors": [
            ("Білий шовк", "#F8F6F2", "FTS-ST-01", "Білі", 265),
            ("Перлинний", "#EDE6D8", "FTS-ST-15", "Бежеві", 272),
            ("Сріблястий", "#C4C2BC", "FTS-ST-28", "Сірі", 278),
            ("М'ятний шовк", "#D0E0D4", "FTS-ST-41", "Зелені", 285),
            ("Лавандовий", "#E0DCE8", "FTS-ST-54", "Пастельні", 288),
            ("Антрацит шовк", "#5A5854", "FTS-ST-67", "Темні", 298),
        ],
    },
    {
        "name": "FTS Premium Silk",
        "country": "FI",
        "paint_finish": "silk_matte",
        "coverage_sqm_per_liter": 10.5,
        "recommended_coats": 2,
        "packs": [(1.0, 510, "1 л"), (2.5, 1150, "2.5 л"), (10.0, 4200, "10 л")],
        "colors": [
            ("Класичний білий", "#FAFAFA", "FTS-PS-01", "Білі", 295),
            ("Шампань", "#F0E4D0", "FTS-PS-12", "Бежеві", 302),
            ("Теплий сірий", "#B0AEA8", "FTS-PS-25", "Сірі", 308),
            ("Рожевий пудра", "#E8D0C8", "FTS-PS-38", "Пастельні", 312),
            ("Небесний", "#B8D0E0", "FTS-PS-51", "Сині", 318),
        ],
    },
    {
        "name": "FTS Aqua Gloss",
        "country": "PL",
        "paint_finish": "gloss",
        "coverage_sqm_per_liter": 10.5,
        "recommended_coats": 2,
        "packs": [(1.0, 320, "1 л"), (3.0, 850, "3 л"), (10.0, 2580, "10 л")],
        "colors": [
            ("Білий глянець", "#FFFFFF", "FTS-AG-01", "Білі", 205),
            ("Крем глянець", "#F0E8D8", "FTS-AG-14", "Бежеві", 212),
            ("Сірий глянець", "#B0AEA8", "FTS-AG-27", "Сірі", 218),
            ("Блакитний глянець", "#A0C0D8", "FTS-AG-40", "Сині", 225),
            ("Теракотовий", "#C87868", "FTS-AG-53", "Червоні", 235),
            ("Смарагдовий", "#78A890", "FTS-AG-66", "Зелені", 238),
        ],
    },
    {
        "name": "FTS Super Gloss",
        "country": "GB",
        "paint_finish": "gloss",
        "coverage_sqm_per_liter": 10.0,
        "recommended_coats": 2,
        "packs": [(1.0, 380, "1 л"), (2.5, 860, "2.5 л"), (5.0, 1580, "5 л")],
        "colors": [
            ("Білий W700", "#FAFAFA", "FTS-SG-01", "Білі", 225),
            ("Сірий перл", "#C4C2BC", "FTS-SG-18", "Сірі", 232),
            ("Капучіно", "#C8B8A4", "FTS-SG-31", "Бежеві", 238),
            ("Синій морський", "#6888A0", "FTS-SG-44", "Сині", 248),
            ("Червоний класик", "#B85848", "FTS-SG-57", "Червоні", 255),
        ],
    },
]

DECOR_MATERIALS: list[dict] = [
    {
        "name": "FTS Венеціанська",
        "category": "Декоративна штукатурка",
        "recommended_coats": 2,
        "packs": [(5.0, 890, "5 м²"), (15.0, 2450, "15 м²"), (25.0, 3800, "25 м²")],
        "shades": [
            ("#C8C0B0", "Травертин", 520),
            ("#E8E0D0", "Перлинний", 560),
            ("#B8A898", "Бронза", 580),
            ("#D8D0C0", "Іворі", 540),
        ],
    },
    {
        "name": "FTS Короїд",
        "category": "Декоративна штукатурка",
        "recommended_coats": 2,
        "packs": [(8.0, 620, "8 м²"), (16.0, 1150, "16 м²"), (25.0, 1680, "25 м²")],
        "shades": [
            ("#E8E4DC", "Білий короїд", 380),
            ("#D0C8B8", "Беж короїд", 395),
            ("#A8A098", "Сірий короїд", 410),
            ("#C8B8A0", "Пісок", 400),
        ],
    },
    {
        "name": "FTS Шовк декоративний",
        "category": "Декоративна штукатурка",
        "recommended_coats": 1,
        "packs": [(4.0, 720, "4 м²"), (12.0, 1980, "12 м²"), (20.0, 3100, "20 м²")],
        "shades": [
            ("#C0C0C0", "Срібний шовк", 490),
            ("#F5E6C8", "Шампань", 470),
            ("#E8E0D0", "Перлинний", 510),
            ("#B8C8C0", "М'ятний шовк", 500),
        ],
    },
]

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


def _sync_paint_packs(db, brand: Brand, packs: list[tuple[float, float, str]]) -> None:
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


def _sync_decor_packs(db, material: DecorativeMaterial, packs: list[tuple[float, float, str]]) -> None:
    existing = list(
        db.scalars(
            select(DecorativeMaterialPackSize).where(DecorativeMaterialPackSize.material_id == material.id)
        ).all()
    )
    for i, (coverage, price, label) in enumerate(packs):
        row = next((p for p in existing if abs(p.coverage_sqm - coverage) < 0.01), None)
        if row:
            row.price_uah = price
            row.label = label
            row.sort_order = i
            row.active = True
        else:
            db.add(
                DecorativeMaterialPackSize(
                    material_id=material.id,
                    coverage_sqm=coverage,
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


def _seed_decor_material(db, store_id: int, cfg: dict) -> int:
    material = db.scalar(
        select(DecorativeMaterial).where(
            DecorativeMaterial.store_id == store_id,
            DecorativeMaterial.name == cfg["name"],
        )
    )
    if not material:
        material = DecorativeMaterial(
            store_id=store_id,
            name=cfg["name"],
            category=cfg["category"],
            texture_scale=1.0,
            recommended_coats=cfg.get("recommended_coats", 2),
            active=True,
            in_stock=True,
        )
        db.add(material)
        db.flush()
    else:
        material.category = cfg["category"]
        material.recommended_coats = cfg.get("recommended_coats", 2)
        material.active = True
        material.in_stock = True

    _sync_decor_packs(db, material, cfg["packs"])

    added = 0
    for hex_val, name, price in cfg["shades"]:
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
    slug = sys.argv[1] if len(sys.argv) > 1 else STORE_SLUG
    with SyncSessionLocal() as db:
        store = db.scalar(select(Store).where(Store.slug == slug, Store.active.is_(True)))
        if not store:
            print(f"Store '{slug}' not found. Create it in /platform/ first.")
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
                    recommended_coats=cfg.get("recommended_coats", 2),
                    active=True,
                )
                db.add(brand)
                db.flush()
            else:
                brand.country = cfg["country"]
                brand.paint_finish = cfg["paint_finish"]
                brand.coverage_sqm_per_liter = cfg["coverage_sqm_per_liter"]
                brand.recommended_coats = cfg.get("recommended_coats", 2)
                brand.active = True

            _sync_paint_packs(db, brand, cfg["packs"])
            _link_brand(db, store.id, brand.id)

            for name, hex_val, code, cat_name, price in cfg["colors"]:
                _upsert_color(db, store.id, brand.id, name, hex_val, code, ColorCategory(cat_name), price)
                total_colors += 1
                finish_counts[cfg["paint_finish"]] = finish_counts.get(cfg["paint_finish"], 0) + 1

            print(
                f"  {cfg['name']} ({cfg['paint_finish']}): "
                f"{len(cfg['colors'])} colors, {len(cfg['packs'])} packs"
            )

        decor_shades = 0
        for decor_cfg in DECOR_MATERIALS:
            decor_shades += _seed_decor_material(db, store.id, decor_cfg)
            print(
                f"  {decor_cfg['name']}: {len(decor_cfg['shades'])} shades, "
                f"{len(decor_cfg['packs'])} packs"
            )

        db.commit()

        print(f"\nOK: store '{store.name}' ({slug})")
        print(f"  Paint colors: {total_colors}")
        print(
            f"  Finishes — matte: {finish_counts['matte']}, "
            f"silk: {finish_counts['silk_matte']}, gloss: {finish_counts['gloss']}"
        )
        print(f"  Decor materials: {len(DECOR_MATERIALS)} ({decor_shades} new shades)")
        print(f"  Brands: {len(BRANDS)}")
        print("\nRun inside Docker:")
        print(f"  docker compose exec api python /scripts/seed_farba_test_shop.py {slug}")


if __name__ == "__main__":
    main()
