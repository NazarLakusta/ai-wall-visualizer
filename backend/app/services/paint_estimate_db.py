from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Brand, BrandPackSize, Color, Project
from app.services.paint_estimate import PackOption, PaintEstimate, build_paint_estimate
from app.services.store_catalog import get_store_color
from app.services.store_discounts import (
    apply_discount_amount,
    load_store_discounts,
    resolve_paint_discount_percent,
)
from app.services.store_pack_prices import effective_pack_price, load_store_pack_price_overrides


async def estimate_paint_for_project(
    db: AsyncSession,
    project: Project,
    color_id: int,
    wall_area_sqm: float | None = None,
    brand_id: int | None = None,
) -> PaintEstimate | None:
    area = wall_area_sqm if wall_area_sqm is not None else project.wall_area_sqm
    if not area or area <= 0:
        return None

    pair = await get_store_color(db, project.store_id, color_id)
    if not pair:
        return None
    color, _listing = pair

    resolved_brand_id = brand_id or project.selected_brand_id or color.brand_id
    if not resolved_brand_id:
        return None

    brand = await db.scalar(
        select(Brand)
        .where(Brand.id == resolved_brand_id, Brand.active.is_(True))
        .options(selectinload(Brand.pack_sizes))
    )
    if not brand:
        return None

    discounts = await load_store_discounts(db, project.store_id)
    discount_percent = resolve_paint_discount_percent(discounts, color.id, resolved_brand_id)
    pack_overrides = await load_store_pack_price_overrides(db, project.store_id, brand_ids={brand.id})

    packs = []
    for p in sorted(brand.pack_sizes, key=lambda x: (x.sort_order, x.volume_liters)):
        base_price = effective_pack_price(p, pack_overrides)
        if not (p.active and p.volume_liters > 0 and base_price > 0):
            continue
        price, _ = apply_discount_amount(base_price, discount_percent)
        packs.append(
            PackOption(
                volume_liters=p.volume_liters,
                price_uah=price if price is not None else base_price,
                label=p.label or "",
            )
        )
    if not packs:
        return None

    return build_paint_estimate(
        area_sqm=float(area),
        coats=brand.recommended_coats or 2,
        coverage_sqm_per_liter=brand.coverage_sqm_per_liter or 10.0,
        pack_options=packs,
        tint_base=color.tint_base,
        base_surcharge_percent=color.base_surcharge_percent,
    )


def estimate_to_dict(estimate: PaintEstimate, discount_percent: float | None = None) -> dict:
    data = {
        "area_sqm": estimate.area_sqm,
        "coats": estimate.coats,
        "coverage_sqm_per_liter": estimate.coverage_sqm_per_liter,
        "waste_percent": estimate.waste_percent,
        "liters_needed": estimate.liters_needed,
        "tint_base": estimate.tint_base,
        "base_surcharge_percent": estimate.base_surcharge_percent,
        "packs": [
            {
                "label": p.label,
                "volume_liters": p.volume_liters,
                "price_uah": p.price_uah,
                "count": p.count,
                "line_total_uah": p.line_total,
            }
            for p in estimate.packs
        ],
        "packs_subtotal_uah": estimate.packs_subtotal_uah,
        "base_surcharge_uah": estimate.base_surcharge_uah,
        "total_uah": estimate.total_uah,
        "summary_short": estimate.summary_short,
        "summary_detail": estimate.summary_detail,
    }
    if discount_percent:
        data["discount_percent"] = discount_percent
    return data
