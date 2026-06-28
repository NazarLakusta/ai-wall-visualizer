from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Color,
    DecorativeColor,
    DecorativeMaterial,
    DecorativeMaterialPackSize,
    StoreColor,
)
from app.services.store_brand_ops import brand_ids_for_store
from app.services.store_pack_prices import bump_store_brand_pack_prices

BULK_SCOPES = frozenset({"all", "paint", "decor", "brand", "material"})
BULK_MODES = frozenset({"add_uah", "sub_uah", "add_percent", "sub_percent"})


def adjust_price(price: float, mode: str, value: float) -> float:
    if mode == "add_uah":
        return max(0.0, round(price + value, 2))
    if mode == "sub_uah":
        return max(0.0, round(price - value, 2))
    if mode == "add_percent":
        return max(0.0, round(price * (1 + value / 100), 2))
    if mode == "sub_percent":
        return max(0.0, round(price * (1 - value / 100), 2))
    raise ValueError(f"Unknown mode: {mode}")


async def bulk_adjust_prices(
    db: AsyncSession,
    store_id: int,
    scope: str,
    mode: str,
    value: float,
    target_id: int | None = None,
) -> dict[str, int]:
    if scope not in BULK_SCOPES:
        raise ValueError("Invalid scope")
    if mode not in BULK_MODES:
        raise ValueError("Invalid mode")
    if scope in {"brand", "material"} and not target_id:
        raise ValueError("target_id required")

    counts = {
        "store_colors": 0,
        "brand_packs": 0,
        "decor_colors": 0,
        "decor_packs": 0,
    }

    async def bump_store_color(listing: StoreColor) -> None:
        if listing.price_per_sqm is None:
            return
        listing.price_per_sqm = adjust_price(listing.price_per_sqm, mode, value)
        counts["store_colors"] += 1

    async def bump_brand_packs(brand_ids: set[int]) -> None:
        counts["brand_packs"] += await bump_store_brand_pack_prices(
            db, store_id, brand_ids, mode, value
        )

    async def bump_decor_for_materials(material_ids: set[int]) -> None:
        if not material_ids:
            return
        shades = await db.scalars(
            select(DecorativeColor).where(
                DecorativeColor.material_id.in_(material_ids),
                DecorativeColor.active.is_(True),
            )
        )
        for shade in shades.all():
            if shade.price_per_sqm is not None:
                shade.price_per_sqm = adjust_price(shade.price_per_sqm, mode, value)
                counts["decor_colors"] += 1
        packs = await db.scalars(
            select(DecorativeMaterialPackSize).where(
                DecorativeMaterialPackSize.material_id.in_(material_ids),
                DecorativeMaterialPackSize.active.is_(True),
            )
        )
        for pack in packs.all():
            pack.price_uah = adjust_price(pack.price_uah, mode, value)
            counts["decor_packs"] += 1

    store_brand_ids = set(await brand_ids_for_store(db, store_id))

    if scope == "all":
        listings = await db.scalars(select(StoreColor).where(StoreColor.store_id == store_id))
        for listing in listings.all():
            await bump_store_color(listing)
        await bump_brand_packs(store_brand_ids)
        materials = await db.scalars(
            select(DecorativeMaterial.id).where(DecorativeMaterial.store_id == store_id)
        )
        await bump_decor_for_materials(set(materials.all()))

    elif scope == "paint":
        listings = await db.scalars(
            select(StoreColor)
            .join(Color, Color.id == StoreColor.color_id)
            .where(StoreColor.store_id == store_id)
        )
        for listing in listings.all():
            await bump_store_color(listing)
        await bump_brand_packs(store_brand_ids)

    elif scope == "brand":
        assert target_id is not None
        if target_id not in store_brand_ids:
            raise ValueError("Brand not in store catalog")
        listings = await db.scalars(
            select(StoreColor)
            .join(Color, Color.id == StoreColor.color_id)
            .where(StoreColor.store_id == store_id, Color.brand_id == target_id)
        )
        for listing in listings.all():
            await bump_store_color(listing)
        await bump_brand_packs({target_id})

    elif scope == "decor":
        materials = await db.scalars(
            select(DecorativeMaterial.id).where(DecorativeMaterial.store_id == store_id)
        )
        await bump_decor_for_materials(set(materials.all()))

    elif scope == "material":
        assert target_id is not None
        material = await db.get(DecorativeMaterial, target_id)
        if not material or material.store_id != store_id:
            raise ValueError("Material not found")
        await bump_decor_for_materials({target_id})

    total = sum(counts.values())
    await db.commit()
    return {"updated_count": total, **counts}
