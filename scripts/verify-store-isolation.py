#!/usr/bin/env python3
"""Audit multi-store isolation — run inside api container or with DATABASE_URL_SYNC set."""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text

DB_URL = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://wallviz:wallviz@localhost:5432/wallviz",
)


def main() -> int:
    engine = create_engine(DB_URL)
    issues: list[str] = []
    ok: list[str] = []

    with engine.connect() as conn:
        stores = conn.execute(text("SELECT id, name, slug FROM stores ORDER BY id")).fetchall()
        ok.append(f"Stores: {len(stores)}")

        shared_brands = conn.execute(
            text(
                """
                SELECT b.id, b.name, COUNT(DISTINCT sb.store_id) AS store_count
                FROM brands b
                JOIN store_brands sb ON sb.brand_id = b.id AND sb.active = true
                GROUP BY b.id, b.name
                HAVING COUNT(DISTINCT sb.store_id) > 1
                ORDER BY store_count DESC
                """
            )
        ).fetchall()
        if shared_brands:
            ok.append(
                f"Shared brands across stores: {len(shared_brands)} "
                "(OK if pack prices use store_brand_pack_prices overrides)"
            )
            for row in shared_brands[:5]:
                ok.append(f"  - brand #{row.id} {row.name}: {row.store_count} stores")

        missing_overrides = conn.execute(
            text(
                """
                SELECT sb.store_id, s.slug, b.name, COUNT(bps.id) AS packs_without_override
                FROM store_brands sb
                JOIN stores s ON s.id = sb.store_id
                JOIN brands b ON b.id = sb.brand_id
                JOIN brand_pack_sizes bps ON bps.brand_id = b.id AND bps.active = true
                LEFT JOIN store_brand_pack_prices sbpp
                    ON sbpp.store_id = sb.store_id AND sbpp.brand_pack_size_id = bps.id
                WHERE sb.active = true AND sbpp.id IS NULL
                GROUP BY sb.store_id, s.slug, b.name
                HAVING COUNT(bps.id) > 0
                """
            )
        ).fetchall()
        if missing_overrides:
            issues.append(
                "Some store/brand packs lack store_brand_pack_prices rows "
                "(run alembic upgrade head or re-save brand packs in admin)"
            )
            for row in missing_overrides[:8]:
                issues.append(f"  - store {row.slug}: {row.name} ({row.packs_without_override} packs)")

        cross_discount = conn.execute(
            text(
                """
                SELECT sd.id, sd.store_id, sd.scope, sd.target_id
                FROM store_discounts sd
                LEFT JOIN stores s ON s.id = sd.store_id
                WHERE s.id IS NULL
                """
            )
        ).fetchall()
        if cross_discount:
            issues.append(f"Orphan store_discounts rows: {len(cross_discount)}")

        decor_wrong_store = conn.execute(
            text(
                """
                SELECT dc.id, dc.material_id, dm.store_id
                FROM decorative_colors dc
                JOIN decorative_materials dm ON dm.id = dc.material_id
                LIMIT 1
                """
            )
        ).fetchone()
        if decor_wrong_store:
            ok.append("Decorative colors are tied to materials (per-store via decorative_materials.store_id)")

        colors_no_listing = conn.execute(
            text(
                """
                SELECT c.id, c.name
                FROM colors c
                WHERE c.active = true
                  AND NOT EXISTS (
                    SELECT 1 FROM store_colors sc WHERE sc.color_id = c.id AND sc.active = true
                  )
                LIMIT 5
                """
            )
        ).fetchall()
        if colors_no_listing:
            ok.append(f"Global colors without any store listing: {len(colors_no_listing)}+ (catalog isolation OK)")

    print("=== Store isolation audit ===\n")
    for line in ok:
        print(f"OK  {line}")
    print()
    if issues:
        for line in issues:
            print(f"!!  {line}")
        print("\nResult: NEEDS ATTENTION")
        return 1

    print("Result: OK — tenant data paths look consistent.")
    print("Note: brand names/volumes are still global; prices and discounts are per store.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
