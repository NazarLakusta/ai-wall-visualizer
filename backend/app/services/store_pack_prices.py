from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Brand, BrandPackSize, StoreBrandPackPrice
from app.schemas import BrandPackSizeIn
from app.services.pricing_bulk import adjust_price


def effective_pack_price(pack: BrandPackSize, overrides: dict[int, float]) -> float:
    return overrides.get(pack.id, pack.price_uah)


async def load_store_pack_price_overrides(
    db: AsyncSession,
    store_id: int,
    *,
    brand_ids: set[int] | None = None,
) -> dict[int, float]:
    """Map brand_pack_size_id → store-specific price_uah (only rows that exist)."""
    query = (
        select(StoreBrandPackPrice)
        .join(BrandPackSize, BrandPackSize.id == StoreBrandPackPrice.brand_pack_size_id)
        .where(StoreBrandPackPrice.store_id == store_id)
    )
    if brand_ids:
        query = query.where(BrandPackSize.brand_id.in_(brand_ids))
    rows = await db.scalars(query)
    return {row.brand_pack_size_id: row.price_uah for row in rows.all()}


async def sync_store_brand_pack_prices(
    db: AsyncSession,
    store_id: int,
    brand: Brand,
    packs: list[BrandPackSizeIn] | None,
) -> None:
    """Persist pack prices for one store without changing other tenants."""
    if not packs:
        return

    active_packs = {
        p.id: p
        for p in await db.scalars(
            select(BrandPackSize).where(BrandPackSize.brand_id == brand.id, BrandPackSize.active.is_(True))
        )
    }
    if not active_packs:
        return

    existing = {
        row.brand_pack_size_id: row
        for row in await db.scalars(
            select(StoreBrandPackPrice).where(
                StoreBrandPackPrice.store_id == store_id,
                StoreBrandPackPrice.brand_pack_size_id.in_(active_packs.keys()),
            )
        )
    }
    by_volume = {p.volume_liters: p for p in active_packs.values()}

    for item in packs:
        pack = active_packs.get(item.id) if item.id else by_volume.get(item.volume_liters)
        if not pack:
            continue
        row = existing.get(pack.id)
        if row:
            row.price_uah = item.price_uah
        else:
            db.add(
                StoreBrandPackPrice(
                    store_id=store_id,
                    brand_pack_size_id=pack.id,
                    price_uah=item.price_uah,
                )
            )


async def bump_store_brand_pack_prices(
    db: AsyncSession,
    store_id: int,
    brand_ids: set[int],
    mode: str,
    value: float,
) -> int:
    if not brand_ids:
        return 0

    packs = await db.scalars(
        select(BrandPackSize).where(
            BrandPackSize.brand_id.in_(brand_ids),
            BrandPackSize.active.is_(True),
        )
    )
    pack_list = packs.all()
    if not pack_list:
        return 0

    pack_ids = {p.id for p in pack_list}
    overrides = {
        row.brand_pack_size_id: row
        for row in await db.scalars(
            select(StoreBrandPackPrice).where(
                StoreBrandPackPrice.store_id == store_id,
                StoreBrandPackPrice.brand_pack_size_id.in_(pack_ids),
            )
        )
    }

    count = 0
    for pack in pack_list:
        current = overrides[pack.id].price_uah if pack.id in overrides else pack.price_uah
        new_price = adjust_price(current, mode, value)
        row = overrides.get(pack.id)
        if row:
            row.price_uah = new_price
        else:
            db.add(
                StoreBrandPackPrice(
                    store_id=store_id,
                    brand_pack_size_id=pack.id,
                    price_uah=new_price,
                )
            )
        count += 1
    return count
