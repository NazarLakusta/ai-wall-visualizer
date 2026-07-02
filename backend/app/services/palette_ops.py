from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Brand, BrandPalette, Color, ColorPalette
from app.schemas import PaletteOut
from app.services.color_codes import code_system_label, normalize_code_system


def palette_out(palette: ColorPalette) -> PaletteOut:
    system = normalize_code_system(palette.code_system)
    return PaletteOut(
        id=palette.id,
        name=palette.name,
        code_system=system,
        code_system_label=code_system_label(system),
        active=palette.active,
    )


def colors_for_brand_clause(brand_id: int):
    palette_ids = select(BrandPalette.palette_id).where(BrandPalette.brand_id == brand_id)
    return or_(Color.palette_id.in_(palette_ids), Color.brand_id == brand_id)


async def palette_ids_for_brand(db: AsyncSession, brand_id: int) -> list[int]:
    rows = await db.scalars(select(BrandPalette.palette_id).where(BrandPalette.brand_id == brand_id))
    return list(rows.all())


async def sync_brand_palettes(db: AsyncSession, brand: Brand, palette_ids: list[int] | None) -> None:
    if palette_ids is None:
        return
    existing = {
        link.palette_id: link
        for link in await db.scalars(select(BrandPalette).where(BrandPalette.brand_id == brand.id))
    }
    wanted = set(palette_ids)
    for palette_id in wanted:
        if palette_id not in existing:
            db.add(BrandPalette(brand_id=brand.id, palette_id=palette_id))
    for palette_id, link in existing.items():
        if palette_id not in wanted:
            await db.delete(link)


async def load_palette(db: AsyncSession, palette_id: int) -> ColorPalette | None:
    return await db.get(ColorPalette, palette_id)


async def load_brand_with_palettes(db: AsyncSession, brand_id: int) -> Brand | None:
    return await db.scalar(
        select(Brand)
        .where(Brand.id == brand_id)
        .options(
            selectinload(Brand.pack_sizes),
            selectinload(Brand.palette_links).selectinload(BrandPalette.palette),
        )
    )


async def list_palettes_for_brand(db: AsyncSession, brand_id: int) -> list[ColorPalette]:
    rows = await db.scalars(
        select(ColorPalette)
        .join(BrandPalette, BrandPalette.palette_id == ColorPalette.id)
        .where(BrandPalette.brand_id == brand_id, ColorPalette.active.is_(True))
        .order_by(ColorPalette.name)
    )
    return list(rows.all())
