"""Seed paint catalog for dekor.showroom store (Innen Wunder, Latex Matt, Innen Latex, Koala)."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, "/app")

from sqlalchemy import select

from app.database import SyncSessionLocal
from app.models import Brand, Color, ColorCategory, Store, StoreColor

STORE_SLUG = os.environ.get("STORE_SLUG", "dekor-showroom")

CATALOG: dict[str, list[tuple[str, str, str, str, float]]] = {
    "Innen Wunder": [
        ("Білий сніг", "#F7F7F2", "IW-001", "Білі", 245),
        ("Кремова класика", "#F3ECE0", "IW-012", "Бежеві", 258),
        ("Світло-бежевий", "#E8DCC8", "IW-024", "Бежеві", 262),
        ("Сірий шелк", "#C8C5BE", "IW-045", "Сірі", 268),
        ("Туманний сірий", "#B5B2AB", "IW-052", "Сірі", 272),
        ("Пастельний м'ятний", "#D4E4D8", "IW-078", "Зелені", 278),
        ("Ніжний блакитний", "#D8E4EC", "IW-091", "Сині", 278),
        ("Лавандовий відтінок", "#E0DCE8", "IW-104", "Пастельні", 282),
        ("Теплий пісок", "#D9C4A0", "IW-118", "Бежеві", 285),
        ("Графіт світлий", "#8A8880", "IW-136", "Темні", 290),
    ],
    "Latex Matt": [
        ("Білий мат", "#FAFAF8", "LM-001", "Білі", 198),
        ("Інней білий", "#F4F2ED", "LM-010", "Білі", 205),
        ("Світло-сірий мат", "#D8D6D0", "LM-032", "Сірі", 212),
        ("Сірий середній", "#B8B5AD", "LM-048", "Сірі", 218),
        ("Тауп", "#A89F92", "LM-061", "Бежеві", 222),
        ("Капучіно", "#C4B5A0", "LM-074", "Бежеві", 225),
        ("Оливковий пастель", "#C5C9B8", "LM-089", "Зелені", 228),
        ("Блакитний мат", "#B8C8D4", "LM-102", "Сині", 232),
        ("Рожевий пудра", "#E8D4D0", "LM-115", "Пастельні", 235),
        ("Антрацит світлий", "#6E6C66", "LM-140", "Темні", 248),
    ],
    "Innen Latex": [
        ("Білий латекс", "#FFFFFF", "IL-001", "Білі", 175),
        ("Жовтувато-білий", "#F8F6EE", "IL-015", "Білі", 182),
        ("Світло-беж", "#EDE4D4", "IL-028", "Бежеві", 188),
        ("Пісочний", "#DCC8A8", "IL-042", "Бежеві", 192),
        ("Сірий дим", "#C0BEB6", "IL-055", "Сірі", 195),
        ("Сірий глибокий", "#9A9690", "IL-068", "Сірі", 198),
        ("Салатовий пастель", "#D8E0C8", "IL-081", "Зелені", 202),
        ("Бірюзовий світлий", "#C8D8D8", "IL-094", "Сині", 205),
        ("Персиковий", "#F0D8C8", "IL-107", "Пастельні", 208),
        ("Коричневий молочний", "#B8A898", "IL-120", "Коричневі", 215),
        ("Червоний теракотовий", "#C88878", "IL-133", "Червоні", 225),
        ("Синій приглушений", "#8898A8", "IL-146", "Сині", 228),
    ],
    "Koala": [
        ("Koala White", "#F9F8F5", "KL-001", "Білі", 165),
        ("Koala Cream", "#F0E8D8", "KL-014", "Бежеві", 172),
        ("Koala Sand", "#DCCAB0", "KL-027", "Бежеві", 178),
        ("Koala Grey Light", "#D0CEC8", "KL-040", "Сірі", 182),
        ("Koala Grey", "#A8A6A0", "KL-053", "Сірі", 185),
        ("Koala Greige", "#B8B0A4", "KL-066", "Бежеві", 188),
        ("Koala Sage", "#B8C4B0", "KL-079", "Зелені", 192),
        ("Koala Sky", "#B0C4D0", "KL-092", "Сині", 195),
        ("Koala Blush", "#E8D0C8", "KL-105", "Пастельні", 198),
        ("Koala Charcoal", "#686660", "KL-128", "Темні", 205),
    ],
}


def _upsert(db, store_id: int, brand_id: int, name: str, hex_val: str, code: str, category: ColorCategory, price: float) -> None:
    color = db.scalar(
        select(Color).where(Color.brand_id == brand_id, Color.manufacturer_code == code)
    )
    if not color:
        color = db.scalar(
            select(Color).where(Color.brand_id == brand_id, Color.name == name, Color.hex == hex_val)
        )
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

    listing = db.scalar(
        select(StoreColor).where(StoreColor.store_id == store_id, StoreColor.color_id == color.id)
    )
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


def main() -> None:
    with SyncSessionLocal() as db:
        store = db.scalar(select(Store).where(Store.slug == STORE_SLUG))
        if not store:
            print(f"Store '{STORE_SLUG}' not found.")
            return

        total = 0
        for brand_name, colors in CATALOG.items():
            brand = db.scalar(select(Brand).where(Brand.name == brand_name))
            if not brand:
                brand = Brand(name=brand_name, country="UA", active=True)
                db.add(brand)
                db.flush()
            elif not brand.active:
                brand.active = True

            for name, hex_val, code, cat_name, price in colors:
                _upsert(db, store.id, brand.id, name, hex_val, code, ColorCategory(cat_name), price)
                total += 1

        db.commit()
        print(f"OK: {total} colors for '{store.name}' ({STORE_SLUG})")


if __name__ == "__main__":
    main()
