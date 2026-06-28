"""Seed popular decorative shades for Китайський шовк at dekor.showroom."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, "/app")

from sqlalchemy import select

from app.database import SyncSessionLocal
from app.models import DecorativeColor, DecorativeMaterial, Store

STORE_SLUG = os.environ.get("STORE_SLUG", "dekor-showroom")
MATERIAL_NAME = "Китайський шовк"

# Same popular shades as demo «Мокрий шовк»
SHADES: list[tuple[str, str, float]] = [
    ("#C0C0C0", "Срібний", 520),
    ("#F5E6C8", "Шампань", 490),
    ("#E8E0D0", "Перлинний", 510),
]


def main() -> None:
    with SyncSessionLocal() as db:
        store = db.scalar(select(Store).where(Store.slug == STORE_SLUG, Store.active.is_(True)))
        if not store:
            print(f"Store not found: {STORE_SLUG}")
            sys.exit(1)

        material = db.scalar(
            select(DecorativeMaterial).where(
                DecorativeMaterial.store_id == store.id,
                DecorativeMaterial.name == MATERIAL_NAME,
            )
        )
        if not material:
            material = DecorativeMaterial(
                store_id=store.id,
                name=MATERIAL_NAME,
                category="Декоративна штукатурка",
                texture_scale=1.0,
                active=True,
                in_stock=True,
            )
            db.add(material)
            db.flush()
            print(f"Created material: {MATERIAL_NAME}")

        added = 0
        for hex_val, name, price in SHADES:
            existing = db.scalar(
                select(DecorativeColor).where(
                    DecorativeColor.material_id == material.id,
                    DecorativeColor.name == name,
                )
            )
            if existing:
                existing.hex = hex_val
                existing.price_per_sqm = price
                existing.active = True
                existing.in_stock = True
                print(f"Updated: {name}")
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
                print(f"Added: {name} ({hex_val}) — ₴{price}/м²")

        db.commit()
        print(f"Done. New shades: {added}, total target: {len(SHADES)}")


if __name__ == "__main__":
    main()
