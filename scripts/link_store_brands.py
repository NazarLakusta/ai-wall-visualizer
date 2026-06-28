"""Link brands to a store from its store_colors (required for admin + mini-app catalog)."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, "/app")

from sqlalchemy import select

from app.database import SyncSessionLocal
from app.models import Brand, Color, Store, StoreBrand, StoreColor


def link_brands_for_store(db, store_id: int) -> list[str]:
    brand_ids = list(
        db.scalars(
            select(Color.brand_id)
            .join(StoreColor, StoreColor.color_id == Color.id)
            .where(
                StoreColor.store_id == store_id,
                StoreColor.active.is_(True),
                Color.active.is_(True),
            )
            .distinct()
        ).all()
    )
    linked: list[str] = []
    for brand_id in brand_ids:
        brand = db.get(Brand, brand_id)
        if not brand:
            continue
        row = db.scalar(
            select(StoreBrand).where(
                StoreBrand.store_id == store_id,
                StoreBrand.brand_id == brand_id,
            )
        )
        if row:
            row.active = True
        else:
            db.add(StoreBrand(store_id=store_id, brand_id=brand_id, active=True))
        linked.append(brand.name)
    return linked


def main() -> None:
    slug = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("STORE_SLUG", "dekor-showroom")
    with SyncSessionLocal() as db:
        store = db.scalar(select(Store).where(Store.slug == slug, Store.active.is_(True)))
        if not store:
            print(f"Store not found: {slug}")
            sys.exit(1)

        colors_count = db.scalar(
            select(StoreColor.id)
            .where(StoreColor.store_id == store.id, StoreColor.active.is_(True))
            .limit(1)
        )
        linked = link_brands_for_store(db, store.id)
        db.commit()
        print(f"Store '{store.name}' ({slug}): linked {len(linked)} brands from catalog")
        if linked:
            print("  " + ", ".join(sorted(linked)))
        if not linked:
            print("  No store_colors found — run seed_dekor_showroom_catalog.py first")


if __name__ == "__main__":
    main()
