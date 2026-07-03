"""Seed KROINZ decorative materials for dekor-showroom (RRP from price list 16.05.2026).

Usage:
    docker compose exec api alembic upgrade head
    docker compose exec api python /scripts/seed_kroinz_decor.py dekor-showroom
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, "/app")

from sqlalchemy import select

from app.database import SyncSessionLocal
from app.models import DecorativeColor, DecorativeMaterial, DecorativeMaterialPackSize, Store

STORE_SLUG_DEFAULT = "dekor-showroom"

# volume_l, weight_kg, price_uah, label
DECOR_MATERIALS: list[dict] = [
    {
        "name": "KROINZ Beige German Silk",
        "category": "Декоративна фарба",
        "pack_sizing_mode": "volume",
        "coverage_sqm_per_liter": 8.0,
        "recommended_coats": 1,
        "texture_scale": 1.2,
        "packs": [
            (1.0, 1.2, 1150, "1 л / 1.2 кг"),
            (2.5, 3.0, 2350, "2.5 л / 3 кг"),
            (5.0, 6.0, 4200, "5 л / 6 кг"),
            (10.0, 12.0, 8200, "10 л / 12 кг"),
        ],
        "shades": [
            ("Беж шовк", "#E8DCC8"),
            ("Пісочний", "#D4C4A8"),
            ("Капучіно", "#C8B8A0"),
            ("Перлинний беж", "#F0E6D4"),
        ],
    },
    {
        "name": "KROINZ White German Silk",
        "category": "Декоративна фарба",
        "pack_sizing_mode": "volume",
        "coverage_sqm_per_liter": 8.0,
        "recommended_coats": 1,
        "texture_scale": 1.2,
        "packs": [
            (1.0, None, 1450, "1 л"),
            (2.5, 3.0, 2750, "2.5 л / 3 кг"),
            (5.0, 6.0, 5200, "5 л / 6 кг"),
            (10.0, 12.0, 9150, "10 л / 12 кг"),
        ],
        "shades": [
            ("Білий шовк", "#FAFAF8"),
            ("Перлинний", "#F2EDE4"),
            ("Сріблястий", "#E4E4E0"),
            ("Айворі", "#F5F0E6"),
        ],
    },
    {
        "name": "KROINZ Sahara Velvet",
        "category": "Декоративна штукатурка",
        "pack_sizing_mode": "volume",
        "coverage_sqm_per_liter": 6.0,
        "recommended_coats": 2,
        "texture_scale": 1.5,
        "packs": [
            (1.0, None, 1050, "1 л"),
            (5.0, None, 3850, "5 л"),
        ],
        "shades": [
            ("Сахара", "#D8C8A8"),
            ("Теракота", "#C8A080"),
            ("Пісок", "#E0D0B0"),
            ("Карамель", "#B89870"),
        ],
    },
]

LEGACY_DECOR_NAMES = {
    "Китайський шовк",
    "Мокрий шовк",
    "Венеціанська",
    "Короїд",
}


def _sync_packs(db, material: DecorativeMaterial, packs: list[tuple]) -> None:
    existing = list(
        db.scalars(
            select(DecorativeMaterialPackSize).where(DecorativeMaterialPackSize.material_id == material.id)
        ).all()
    )
    seen: set[int] = set()
    for i, (vol, weight, price, label) in enumerate(packs):
        row = next((p for p in existing if p.volume_liters and abs(p.volume_liters - vol) < 0.01), None)
        if row:
            seen.add(row.id)
        else:
            row = DecorativeMaterialPackSize(material_id=material.id)
            db.add(row)
            db.flush()
            seen.add(row.id)
        row.volume_liters = vol
        row.weight_kg = weight
        row.coverage_sqm = None
        row.price_uah = price
        row.label = label
        row.sort_order = i
        row.active = True
    for pack in existing:
        if pack.id not in seen:
            pack.active = False


def _seed_material(db, store_id: int, cfg: dict) -> int:
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
            category=cfg.get("category"),
            texture_scale=cfg.get("texture_scale", 1.0),
            recommended_coats=cfg.get("recommended_coats", 1),
            pack_sizing_mode=cfg.get("pack_sizing_mode", "volume"),
            coverage_sqm_per_liter=cfg.get("coverage_sqm_per_liter"),
            active=True,
            in_stock=True,
        )
        db.add(material)
        db.flush()
    else:
        material.category = cfg.get("category")
        material.texture_scale = cfg.get("texture_scale", 1.0)
        material.recommended_coats = cfg.get("recommended_coats", 1)
        material.pack_sizing_mode = cfg.get("pack_sizing_mode", "volume")
        material.coverage_sqm_per_liter = cfg.get("coverage_sqm_per_liter")
        material.active = True
        material.in_stock = True

    _sync_packs(db, material, cfg["packs"])

    added = 0
    for name, hex_val in cfg["shades"]:
        row = db.scalar(
            select(DecorativeColor).where(
                DecorativeColor.material_id == material.id,
                DecorativeColor.name == name,
            )
        )
        if not row:
            row = DecorativeColor(material_id=material.id, name=name, hex=hex_val, active=True, in_stock=True)
            db.add(row)
            added += 1
        else:
            row.hex = hex_val
            row.active = True
            row.in_stock = True
    return added


def _hide_legacy_decor(db, store_id: int) -> None:
    materials = db.scalars(
        select(DecorativeMaterial).where(
            DecorativeMaterial.store_id == store_id,
            DecorativeMaterial.active.is_(True),
        )
    ).all()
    for m in materials:
        if m.name in LEGACY_DECOR_NAMES or any(m.name.startswith(p) for p in ("FTS ", "IW-", "IL-", "LM-")):
            m.active = False


def main() -> None:
    slug = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("STORE_SLUG", STORE_SLUG_DEFAULT)
    with SyncSessionLocal() as db:
        store = db.scalar(select(Store).where(Store.slug == slug))
        if not store:
            print(f"Store not found: {slug}")
            sys.exit(1)

        total_shades = 0
        for cfg in DECOR_MATERIALS:
            total_shades += _seed_material(db, store.id, cfg)
            print(f"  {cfg['name']}: {len(cfg['packs'])} packs, {len(cfg['shades'])} shades")

        _hide_legacy_decor(db, store.id)
        db.commit()

        print(f"\nOK: KROINZ decor for '{store.name}' ({slug})")
        print(f"  Materials: {len(DECOR_MATERIALS)}")
        print(f"  New shades: {total_shades}")
        print("\nTextures: see docs/TEXTURE_PROMPTS.md, upload via admin.")


if __name__ == "__main__":
    main()
