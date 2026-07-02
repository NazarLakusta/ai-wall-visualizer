from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Color, DecorativeColor, Project, StoreColor
from app.schemas import ColorOut, DecorativeColorOut
from app.services.color_codes import format_display_code, normalize_code_system
from app.services.store_discounts import apply_discount_amount


def color_out(
    color: Color,
    listing: StoreColor,
    discount_percent: float | None = None,
    *,
    code_system: str | None = None,
) -> ColorOut:
    display_price, original_price = apply_discount_amount(listing.price_per_sqm, discount_percent)
    system = normalize_code_system(code_system)
    if code_system is None:
        if color.palette is not None:
            system = normalize_code_system(color.palette.code_system)
        elif color.brand is not None:
            system = normalize_code_system(color.brand.color_code_system)
    display = format_display_code(system, color.manufacturer_code)
    palette_name = color.palette.name if color.palette else None
    return ColorOut(
        id=color.id,
        brand_id=color.brand_id,
        palette_id=color.palette_id,
        palette_name=palette_name,
        name=color.name,
        hex=color.hex,
        manufacturer_code=color.manufacturer_code,
        display_code=display,
        code_system=system,
        category=color.category.value if hasattr(color.category, "value") else str(color.category),
        tint_base=color.tint_base,
        base_surcharge_percent=color.base_surcharge_percent or 0.0,
        price_per_sqm=display_price,
        original_price_per_sqm=original_price,
        discount_percent=discount_percent if original_price is not None else None,
        in_stock=listing.in_stock,
        active=listing.active and color.active,
    )


def decor_color_out(
    shade: DecorativeColor,
    discount_percent: float | None = None,
) -> DecorativeColorOut:
    display_price, original_price = apply_discount_amount(shade.price_per_sqm, discount_percent)
    return DecorativeColorOut(
        id=shade.id,
        material_id=shade.material_id,
        name=shade.name,
        hex=shade.hex,
        price_per_sqm=display_price,
        original_price_per_sqm=original_price,
        discount_percent=discount_percent if original_price is not None else None,
        in_stock=shade.in_stock,
        active=shade.active,
    )


async def get_store_color(
    db: AsyncSession,
    store_id: int,
    color_id: int,
) -> tuple[Color, StoreColor] | None:
    row = await db.scalar(
        select(StoreColor)
        .where(
            StoreColor.store_id == store_id,
            StoreColor.color_id == color_id,
            StoreColor.active.is_(True),
        )
        .options(selectinload(StoreColor.color))
    )
    if not row or not row.color or not row.color.active:
        return None
    return row.color, row


async def get_paint_price_for_project(db: AsyncSession, project: Project) -> float | None:
    if not project.selected_color_id:
        return None
    pair = await get_store_color(db, project.store_id, project.selected_color_id)
    if not pair:
        return None
    _, listing = pair
    return listing.price_per_sqm
