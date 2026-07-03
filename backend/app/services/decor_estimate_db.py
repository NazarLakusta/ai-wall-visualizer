from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import DecorativeColor, DecorativeMaterial, Project
from app.services.material_ops import _pack_sort_key
from app.services.paint_estimate import (
    PackOption,
    PaintEstimate,
    WASTE_PERCENT,
    calc_liters_needed,
    optimize_paint_packs,
    pack_label,
)
from app.services.store_discounts import (
    apply_discount_amount,
    load_store_discounts,
    resolve_decor_discount_percent,
)


def _area_pack_label(coverage_sqm: float, label: str | None) -> str:
    if label:
        return label
    if coverage_sqm == int(coverage_sqm):
        return f"{int(coverage_sqm)} м²"
    return f"{coverage_sqm:g} м²"


def build_decor_area_estimate(
    area_sqm: float,
    coats: int,
    pack_options: list[PackOption],
    material_name: str,
    waste_percent: float = WASTE_PERCENT,
) -> PaintEstimate | None:
    if area_sqm <= 0 or coats <= 0 or not pack_options:
        return None

    sqm_needed = area_sqm * coats * (1 + waste_percent / 100.0)
    packs = optimize_paint_packs(sqm_needed, pack_options)
    if not packs:
        return None

    packs_subtotal = round(sum(p.line_total for p in packs), 2)
    total = packs_subtotal

    pack_text = ", ".join(f"{p.count}×{p.label} (₴{p.line_total:g})" for p in packs)
    summary_short = f"{pack_text} = ₴{total:g}"
    summary_detail = (
        f"Декор «{material_name}»: {area_sqm:g} м² × {coats} шар(и), запас {waste_percent:g}%\n"
        f"Потрібно покрити ~{sqm_needed:.1f} м²\n"
        f"Фасування: {pack_text}\n"
        f"Разом: ₴{total:g}"
    )

    return PaintEstimate(
        area_sqm=area_sqm,
        coats=coats,
        coverage_sqm_per_liter=0.0,
        waste_percent=waste_percent,
        liters_needed=round(sqm_needed, 2),
        tint_base=None,
        base_surcharge_percent=0.0,
        packs=packs,
        packs_subtotal_uah=packs_subtotal,
        base_surcharge_uah=0.0,
        total_uah=total,
        summary_short=summary_short,
        summary_detail=summary_detail,
    )


def build_decor_volume_estimate(
    area_sqm: float,
    coats: int,
    coverage_sqm_per_liter: float,
    pack_options: list[PackOption],
    material_name: str,
    waste_percent: float = WASTE_PERCENT,
) -> PaintEstimate | None:
    if area_sqm <= 0 or coats <= 0 or coverage_sqm_per_liter <= 0 or not pack_options:
        return None

    liters_needed = calc_liters_needed(area_sqm, coats, coverage_sqm_per_liter, waste_percent)
    packs = optimize_paint_packs(liters_needed, pack_options)
    if not packs:
        return None

    packs_subtotal = round(sum(p.line_total for p in packs), 2)
    total = packs_subtotal

    pack_text = ", ".join(f"{p.count}×{p.label} (₴{p.line_total:g})" for p in packs)
    summary_short = f"{pack_text} = ₴{total:g}"
    summary_detail = (
        f"Декор «{material_name}»: {area_sqm:g} м² × {coats} шар(и), запас {waste_percent:g}%\n"
        f"Витрата {coverage_sqm_per_liter:g} м²/л\n"
        f"Потрібно ~{liters_needed:.1f} л\n"
        f"Фасування: {pack_text}\n"
        f"Разом: ₴{total:g}"
    )

    return PaintEstimate(
        area_sqm=area_sqm,
        coats=coats,
        coverage_sqm_per_liter=coverage_sqm_per_liter,
        waste_percent=waste_percent,
        liters_needed=round(liters_needed, 2),
        tint_base=None,
        base_surcharge_percent=0.0,
        packs=packs,
        packs_subtotal_uah=packs_subtotal,
        base_surcharge_uah=0.0,
        total_uah=total,
        summary_short=summary_short,
        summary_detail=summary_detail,
    )


async def estimate_decor_for_project(
    db: AsyncSession,
    project: Project,
    material_id: int | None = None,
    decor_color_id: int | None = None,
    wall_area_sqm: float | None = None,
) -> PaintEstimate | None:
    area = wall_area_sqm if wall_area_sqm is not None else project.wall_area_sqm
    if not area or area <= 0:
        return None

    mat_id = material_id or project.selected_material_id
    if not mat_id:
        return None

    material = await db.scalar(
        select(DecorativeMaterial)
        .where(
            DecorativeMaterial.id == mat_id,
            DecorativeMaterial.store_id == project.store_id,
            DecorativeMaterial.active.is_(True),
        )
        .options(selectinload(DecorativeMaterial.pack_sizes))
    )
    if not material:
        return None

    if decor_color_id or project.selected_decor_color_id:
        dc_id = decor_color_id or project.selected_decor_color_id
        dc = await db.get(DecorativeColor, dc_id)
        if not dc or dc.material_id != material.id:
            return None
    else:
        dc_id = None

    discounts = await load_store_discounts(db, project.store_id)
    discount_percent = resolve_decor_discount_percent(discounts, material.id, dc_id)

    pack_rows = [
        p
        for p in sorted(material.pack_sizes, key=_pack_sort_key)
        if p.active and p.price_uah > 0
    ]
    if not pack_rows:
        return None

    coats = material.recommended_coats or 1
    sizing_mode = material.pack_sizing_mode or "area"

    if sizing_mode == "volume":
        coverage = material.coverage_sqm_per_liter or 8.0
        options = []
        for p in pack_rows:
            if not p.volume_liters or p.volume_liters <= 0:
                continue
            price, _ = apply_discount_amount(p.price_uah, discount_percent)
            options.append(
                PackOption(
                    volume_liters=p.volume_liters,
                    price_uah=price if price is not None else p.price_uah,
                    label=pack_label(p.volume_liters, p.label),
                )
            )
        return build_decor_volume_estimate(float(area), coats, coverage, options, material.name)

    options = []
    for p in pack_rows:
        if not p.coverage_sqm or p.coverage_sqm <= 0:
            continue
        price, _ = apply_discount_amount(p.price_uah, discount_percent)
        options.append(
            PackOption(
                volume_liters=p.coverage_sqm,
                price_uah=price if price is not None else p.price_uah,
                label=_area_pack_label(p.coverage_sqm, p.label),
            )
        )
    return build_decor_area_estimate(float(area), coats, options, material.name)
