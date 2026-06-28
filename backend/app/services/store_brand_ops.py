from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Brand, StoreBrand


async def get_store_brand(db: AsyncSession, store_id: int, brand_id: int) -> StoreBrand | None:
    return await db.scalar(
        select(StoreBrand).where(
            StoreBrand.store_id == store_id,
            StoreBrand.brand_id == brand_id,
            StoreBrand.active.is_(True),
        )
    )


async def link_brand_to_store(db: AsyncSession, store_id: int, brand_id: int) -> StoreBrand:
    existing = await db.scalar(
        select(StoreBrand).where(StoreBrand.store_id == store_id, StoreBrand.brand_id == brand_id)
    )
    if existing:
        existing.active = True
        return existing
    link = StoreBrand(store_id=store_id, brand_id=brand_id, active=True)
    db.add(link)
    return link


async def list_brands_for_store(db: AsyncSession, store_id: int) -> list[Brand]:
    brands = await db.scalars(
        select(Brand)
        .join(StoreBrand, StoreBrand.brand_id == Brand.id)
        .where(
            StoreBrand.store_id == store_id,
            StoreBrand.active.is_(True),
            Brand.active.is_(True),
        )
        .options(selectinload(Brand.pack_sizes))
        .order_by(Brand.name)
    )
    return list(brands.all())


async def brand_ids_for_store(db: AsyncSession, store_id: int) -> list[int]:
    rows = await db.scalars(
        select(StoreBrand.brand_id).where(
            StoreBrand.store_id == store_id,
            StoreBrand.active.is_(True),
        )
    )
    return list(rows.all())
