from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Brand, BrandPackSize
from app.models import PAINT_FINISH_LABELS
from app.schemas import BrandOut, BrandPackSizeIn, BrandPackSizeOut, PaletteOut
from app.services.color_codes import code_system_label, format_display_code, normalize_code_system
from app.services.paint_estimate import DEFAULT_BASE_SURCHARGE
from app.services.palette_ops import palette_out
from app.services.store_pack_prices import effective_pack_price


def normalize_paint_finish(value: str | None) -> str:
    if not value:
        return "matte"
    v = value.strip().lower()
    return v if v in PAINT_FINISH_LABELS else "matte"


def paint_finish_label(value: str | None) -> str:
    return PAINT_FINISH_LABELS.get(normalize_paint_finish(value), "Матова")


def brand_out(brand: Brand, pack_price_overrides: dict[int, float] | None = None) -> BrandOut:
    finish = normalize_paint_finish(brand.paint_finish)
    packs = sorted(
        [p for p in brand.pack_sizes if p.active],
        key=lambda p: (p.sort_order, p.volume_liters),
    )
    pack_rows = []
    for p in packs:
        row = BrandPackSizeOut.model_validate(p)
        if pack_price_overrides is not None:
            row = row.model_copy(update={"price_uah": effective_pack_price(p, pack_price_overrides)})
        pack_rows.append(row)
    palettes: list[PaletteOut] = []
    code_system = normalize_code_system(brand.color_code_system)
    if getattr(brand, "palette_links", None):
        for link in brand.palette_links:
            if link.palette and link.palette.active:
                palettes.append(palette_out(link.palette))
        if palettes:
            code_system = palettes[0].code_system
    return BrandOut(
        id=brand.id,
        name=brand.name,
        logo=brand.logo,
        country=brand.country,
        coverage_sqm_per_liter=brand.coverage_sqm_per_liter or 10.0,
        recommended_coats=brand.recommended_coats or 2,
        paint_finish=finish,
        paint_finish_label=paint_finish_label(finish),
        color_code_system=code_system,
        color_code_system_label=code_system_label(code_system),
        palettes=palettes,
        active=brand.active,
        pack_sizes=pack_rows,
    )


async def sync_brand_pack_sizes(
    db: AsyncSession,
    brand: Brand,
    packs: list[BrandPackSizeIn] | None,
) -> None:
    if packs is None:
        return

    existing = {
        p.id: p
        for p in await db.scalars(select(BrandPackSize).where(BrandPackSize.brand_id == brand.id))
    }
    seen_ids: set[int] = set()

    for i, item in enumerate(packs):
        if item.id and item.id in existing:
            row = existing[item.id]
            row.volume_liters = item.volume_liters
            row.label = item.label
            row.sort_order = item.sort_order if item.sort_order else i
            row.active = item.active
            seen_ids.add(item.id)
        else:
            db.add(
                BrandPackSize(
                    brand_id=brand.id,
                    volume_liters=item.volume_liters,
                    price_uah=item.price_uah,
                    label=item.label,
                    sort_order=item.sort_order if item.sort_order else i,
                    active=item.active,
                )
            )

    for pack_id, row in existing.items():
        if pack_id not in seen_ids and packs:
            row.active = False


def normalize_tint_base(value: str | None) -> str | None:
    if not value:
        return None
    base = value.strip().upper()
    return base if base in {"A", "B", "C"} else None


def default_surcharge_for_base(tint_base: str | None, explicit: float | None) -> float:
    if explicit is not None:
        return float(explicit)
    if tint_base:
        return DEFAULT_BASE_SURCHARGE.get(tint_base.upper(), 0.0)
    return 0.0


async def load_brand_with_packs(db: AsyncSession, brand_id: int) -> Brand | None:
    from app.services.palette_ops import load_brand_with_palettes

    return await load_brand_with_palettes(db, brand_id)
