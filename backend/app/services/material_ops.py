from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import DecorativeMaterial, DecorativeMaterialPackSize
from app.schemas import DecorativeMaterialPackSizeIn, DecorativeMaterialPackSizeOut


def material_pack_out(pack: DecorativeMaterialPackSize) -> DecorativeMaterialPackSizeOut:
    return DecorativeMaterialPackSizeOut.model_validate(pack)


async def load_material_with_packs(db: AsyncSession, material_id: int) -> DecorativeMaterial | None:
    return await db.scalar(
        select(DecorativeMaterial)
        .where(DecorativeMaterial.id == material_id)
        .options(selectinload(DecorativeMaterial.pack_sizes))
    )


def _pack_sort_key(pack: DecorativeMaterialPackSize) -> tuple:
    primary = pack.volume_liters if pack.volume_liters and pack.volume_liters > 0 else (pack.coverage_sqm or 0)
    return (pack.sort_order, primary)


async def sync_material_pack_sizes(
    db: AsyncSession,
    material: DecorativeMaterial,
    packs: list[DecorativeMaterialPackSizeIn] | None,
) -> None:
    if packs is None:
        return
    existing = {
        p.id: p
        for p in await db.scalars(
            select(DecorativeMaterialPackSize).where(
                DecorativeMaterialPackSize.material_id == material.id
            )
        )
    }
    seen: set[int] = set()
    for i, item in enumerate(packs):
        if item.id and item.id in existing:
            pack = existing[item.id]
            seen.add(item.id)
        else:
            pack = DecorativeMaterialPackSize(material_id=material.id)
            db.add(pack)
        pack.coverage_sqm = item.coverage_sqm
        pack.volume_liters = item.volume_liters
        pack.weight_kg = item.weight_kg
        pack.price_uah = item.price_uah
        pack.label = item.label
        pack.sort_order = item.sort_order if item.sort_order is not None else i
        pack.active = True
    for pid, pack in existing.items():
        if pid not in seen:
            pack.active = False
