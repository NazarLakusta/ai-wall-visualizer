"""Seed database with demo store, admin, brands, colors, and test project assets."""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, "/app")

from sqlalchemy import select

from app.config import settings
from app.database import SyncSessionLocal
from app.models import (
    AdminRole,
    Brand,
    Color,
    ColorCategory,
    DecorativeColor,
    DecorativeMaterial,
    PlatformAdmin,
    Store,
    StoreAdmin,
    StoreColor,
)
from app.services.jwt import hash_password
from app.services.storage import StorageService

BRANDS = ["Caparol", "Farbex", "Kompozit", "Dufa", "Ceresit", "Tikkurila", "Eskaro", "Feidal"]

SAMPLE_COLORS = [
    ("Білий сніг", "#F8F8F8", "Білі", 185),
    ("Сірий туман", "#B0B0B0", "Сірі", 210),
    ("Бежевий пісок", "#D4C4A8", "Бежеві", 225),
    ("Зелений мох", "#6B8E6B", "Зелені", 245),
    ("Синій океан", "#4A6FA5", "Сині", 265),
]

DECORATIVE = [
    ("Мокрий шовк", [
        ("#C0C0C0", "Срібний", 520),
        ("#F5E6C8", "Шампань", 490),
        ("#E8E0D0", "Перлинний", 510),
    ]),
    ("Травертин", [
        ("#D4B896", "Бежевий", 480),
        ("#C8A87C", "Пісочний", 470),
        ("#C8C8C0", "Світло-сірий", 460),
    ]),
]


def create_test_images(storage: StorageService) -> None:
    """Генерує placeholder лише якщо в storage/test немає жодного original."""
    test_dir = storage.test_dir
    has_original = any((test_dir / name).exists() for name in ("original.jpg", "original.png", "original.jpeg"))
    if has_original:
        print("Test images: using files from storage/test (seed skipped).")
        return

    print("Test images: no original in storage/test, generating placeholder...")
    w, h = 800, 600
    img = Image.new("RGB", (w, h), "#E8E0D8")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w, h], fill="#E8E0D8")
    draw.rectangle([50, 50, w - 50, h - 100], fill="#D8D0C8")
    draw.rectangle([0, h - 80, w, h], fill="#A08060")
    img.save(test_dir / "original.jpg", quality=90)

    mask = Image.new("L", (w, h), 0)
    draw_m = ImageDraw.Draw(mask)
    draw_m.rectangle([50, 50, w - 50, h - 100], fill=255)
    mask.save(test_dir / "mask.png")

    illum = Image.new("L", (w, h), 180)
    draw_i = ImageDraw.Draw(illum)
    draw_i.ellipse([w // 4, 0, 3 * w // 4, h // 2], fill=220)
    illum.save(test_dir / "illumination.png")

    spec = Image.new("L", (w, h), 0)
    draw_s = ImageDraw.Draw(spec)
    draw_s.ellipse([w // 3, h // 6, 2 * w // 3, h // 3], fill=80)
    spec.save(test_dir / "specular.png")


def main() -> None:
    storage = StorageService(settings.storage_path)
    create_test_images(storage)

    with SyncSessionLocal() as db:
        store = db.scalar(select(Store).where(Store.slug == settings.default_store_slug))
        if not store:
            store = Store(name=settings.default_store_name, slug=settings.default_store_slug, active=True)
            db.add(store)
            db.flush()

        if not store.phone:
            store.phone = "+380501234567"
            store.address = "м. Київ, вул. Демонстраційна, 1"
            store.telegram_username = "demo_paint_store"

        if settings.telegram_bot_token and not store.telegram_bot_token:
            store.telegram_bot_token = settings.telegram_bot_token

        admin = db.scalar(select(StoreAdmin).where(StoreAdmin.email == settings.admin_email))
        if not admin:
            admin = StoreAdmin(
                store_id=store.id,
                email=settings.admin_email,
                password_hash=hash_password(settings.admin_password),
                role=AdminRole.OWNER,
                active=True,
            )
            db.add(admin)

        platform_admin = db.scalar(
            select(PlatformAdmin).where(PlatformAdmin.email == settings.platform_admin_email)
        )
        if not platform_admin:
            db.add(
                PlatformAdmin(
                    email=settings.platform_admin_email,
                    password_hash=hash_password(settings.platform_admin_password),
                    name="Platform Admin",
                    active=True,
                )
            )

        for brand_name in BRANDS:
            if not db.scalar(select(Brand).where(Brand.name == brand_name)):
                db.add(Brand(name=brand_name, country="UA", active=True))
        db.flush()

        caparol = db.scalar(select(Brand).where(Brand.name == "Caparol"))
        for i, (name, hex_val, cat, price) in enumerate(SAMPLE_COLORS):
            exists = db.scalar(select(Color).where(Color.name == name, Color.brand_id == caparol.id))
            if not exists:
                exists = Color(
                    brand_id=caparol.id,
                    name=name,
                    hex=hex_val,
                    manufacturer_code=f"CP-{100+i}",
                    category=ColorCategory(cat),
                    price_per_sqm=price,
                    active=True,
                )
                db.add(exists)
                db.flush()
            elif exists.price_per_sqm is None:
                exists.price_per_sqm = price

            listing = db.scalar(
                select(StoreColor).where(
                    StoreColor.store_id == store.id,
                    StoreColor.color_id == exists.id,
                )
            )
            if not listing:
                db.add(StoreColor(
                    store_id=store.id,
                    color_id=exists.id,
                    price_per_sqm=price,
                    in_stock=True,
                    active=True,
                ))
            else:
                if listing.price_per_sqm is None:
                    listing.price_per_sqm = price
                listing.active = True

        for mat_name, colors in DECORATIVE:
            mat = db.scalar(
                select(DecorativeMaterial).where(
                    DecorativeMaterial.name == mat_name,
                    DecorativeMaterial.store_id == store.id,
                )
            )
            if not mat:
                mat = DecorativeMaterial(
                    store_id=store.id,
                    name=mat_name,
                    category="Декоративна штукатурка",
                    texture_scale=1.0,
                    active=True,
                )
                db.add(mat)
                db.flush()
                for hex_val, color_name, price in colors:
                    db.add(DecorativeColor(
                        material_id=mat.id, name=color_name, hex=hex_val, price_per_sqm=price, active=True
                    ))
            else:
                for hex_val, color_name, price in colors:
                    dc = db.scalar(
                        select(DecorativeColor).where(
                            DecorativeColor.material_id == mat.id,
                            DecorativeColor.name == color_name,
                        )
                    )
                    if dc and dc.price_per_sqm is None:
                        dc.price_per_sqm = price

        db.commit()
    print("Seed completed.")


if __name__ == "__main__":
    main()
