from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Brand, Color, DecorativeColor, DecorativeMaterial, Project
from app.services.brand_ops import paint_finish_label
from app.services.color_codes import format_display_code
from app.services.store_catalog import get_store_color
from app.services.store_discounts import (
    apply_discount_amount,
    load_store_discounts,
    resolve_decor_discount_percent,
    resolve_paint_discount_percent,
)


async def build_selection_summary(db: AsyncSession, project: Project) -> str | None:
    parts: list[str] = []
    if project.selected_material_id:
        mat = await db.get(DecorativeMaterial, project.selected_material_id)
        if mat:
            parts.append(mat.name)
    if project.selected_decor_color_id:
        dc = await db.get(DecorativeColor, project.selected_decor_color_id)
        if dc:
            code = f" — {dc.name}" if parts else dc.name
            parts.append(code.strip(" —"))
    elif project.selected_color_id:
        color = await db.get(Color, project.selected_color_id)
        if color:
            brand = await db.get(Brand, color.brand_id)
            code_system = brand.color_code_system if brand else "manufacturer"
            display = format_display_code(code_system, color.manufacturer_code)
            label = color.name
            if display:
                label = f"{display} · {color.name}"
            if brand:
                label = f"{brand.name} — {label}"
                parts.insert(0, paint_finish_label(brand.paint_finish))
            if color.tint_base:
                label += f" (база {color.tint_base.upper()})"
            parts.append(label)
    if project.selected_finish and not project.selected_decor_color_id and not project.selected_color_id:
        finish_map = {"matte": "матова", "silk_matte": "шовк.-матова", "gloss": "глянцева"}
        parts.append(finish_map.get(project.selected_finish, project.selected_finish))
    return " · ".join(parts) if parts else None


async def get_active_price_per_sqm(db: AsyncSession, project: Project) -> float | None:
    discounts = await load_store_discounts(db, project.store_id)
    if project.selected_decor_color_id:
        dc = await db.get(DecorativeColor, project.selected_decor_color_id)
        if not dc:
            return None
        disc = resolve_decor_discount_percent(discounts, dc.material_id, dc.id)
        price, _ = apply_discount_amount(dc.price_per_sqm, disc)
        return price
    if project.selected_color_id:
        pair = await get_store_color(db, project.store_id, project.selected_color_id)
        if not pair:
            return None
        color, listing = pair
        disc = resolve_paint_discount_percent(discounts, color.id, color.brand_id)
        price, _ = apply_discount_amount(listing.price_per_sqm, disc)
        return price
    return None
