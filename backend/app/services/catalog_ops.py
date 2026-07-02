from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Brand, Color, ColorCategory, StoreColor
from app.services.palette_ops import colors_for_brand_clause
from app.schemas import ColorCreate, ColorOut, ColorUpdate, StockUpdate
from app.services.store_catalog import color_out


async def get_store_color_row(
    db: AsyncSession,
    store_id: int,
    color_id: int,
) -> tuple[Color, StoreColor] | None:
    listing = await db.scalar(
        select(StoreColor)
        .where(StoreColor.store_id == store_id, StoreColor.color_id == color_id)
        .options(selectinload(StoreColor.color))
    )
    if not listing or not listing.color:
        return None
    return listing.color, listing


async def list_store_colors(
    db: AsyncSession,
    store_id: int,
    brand_id: int | None = None,
) -> list[ColorOut]:
    query = (
        select(StoreColor)
        .join(Color, Color.id == StoreColor.color_id)
        .where(
            StoreColor.store_id == store_id,
            StoreColor.active.is_(True),
            Color.active.is_(True),
        )
        .options(
            selectinload(StoreColor.color).selectinload(Color.brand),
            selectinload(StoreColor.color).selectinload(Color.palette),
        )
    )
    if brand_id:
        query = query.where(colors_for_brand_clause(brand_id))
    listings = await db.scalars(query.order_by(Color.palette_id, Color.name))
    return [color_out(row.color, row) for row in listings.all() if row.color]


async def list_brands(db: AsyncSession) -> list[Brand]:
    brands = await db.scalars(select(Brand).where(Brand.active.is_(True)).order_by(Brand.name))
    return list(brands.all())


async def ensure_brand(db: AsyncSession, name: str, country: str = "UA") -> Brand:
    brand = await db.scalar(select(Brand).where(Brand.name == name))
    if brand:
        if not brand.active:
            brand.active = True
        return brand
    brand = Brand(name=name, country=country, active=True)
    db.add(brand)
    await db.flush()
    return brand


async def add_color_to_store(db: AsyncSession, store_id: int, body: ColorCreate) -> ColorOut:
    try:
        category = ColorCategory(body.category)
    except ValueError as exc:
        raise ValueError("Invalid category") from exc

    existing = await db.scalar(
        select(Color).where(
            Color.palette_id == body.palette_id,
            Color.name == body.name,
            Color.hex == body.hex,
        )
    )
    if existing:
        color = existing
    else:
        color = Color(
            palette_id=body.palette_id,
            name=body.name,
            hex=body.hex,
            manufacturer_code=body.manufacturer_code,
            category=category,
            active=True,
        )
        db.add(color)
        await db.flush()

    listing = await db.scalar(
        select(StoreColor).where(StoreColor.store_id == store_id, StoreColor.color_id == color.id)
    )
    if listing:
        listing.active = True
        if body.price_per_sqm is not None:
            listing.price_per_sqm = body.price_per_sqm
    else:
        listing = StoreColor(
            store_id=store_id,
            color_id=color.id,
            price_per_sqm=body.price_per_sqm,
            in_stock=True,
            active=True,
        )
        db.add(listing)

    await db.commit()
    await db.refresh(listing)
    await db.refresh(color)
    return color_out(color, listing)


async def update_store_color(
    db: AsyncSession,
    store_id: int,
    color_id: int,
    body: ColorUpdate,
) -> ColorOut:
    pair = await get_store_color_row(db, store_id, color_id)
    if not pair:
        raise LookupError("Color not in store catalog")
    color, listing = pair

    data = body.model_dump(exclude_unset=True)
    store_fields = {"price_per_sqm", "in_stock", "active"}
    for key in list(data.keys()):
        if key in store_fields:
            setattr(listing, key, data.pop(key))
    if "category" in data and data["category"]:
        data["category"] = ColorCategory(data["category"])
    for key, value in data.items():
        setattr(color, key, value)

    await db.commit()
    await db.refresh(color)
    await db.refresh(listing)
    return color_out(color, listing)


async def set_store_color_stock(
    db: AsyncSession,
    store_id: int,
    color_id: int,
    body: StockUpdate,
) -> ColorOut:
    pair = await get_store_color_row(db, store_id, color_id)
    if not pair:
        raise LookupError("Color not in store catalog")
    color, listing = pair
    listing.in_stock = body.in_stock
    await db.commit()
    await db.refresh(listing)
    return color_out(color, listing)


async def remove_color_from_store(db: AsyncSession, store_id: int, color_id: int) -> None:
    pair = await get_store_color_row(db, store_id, color_id)
    if not pair:
        raise LookupError("Color not in store catalog")
    _, listing = pair
    listing.active = False
    await db.commit()


async def upsert_store_color(
    db: AsyncSession,
    store_id: int,
    palette_id: int,
    name: str,
    hex_val: str,
    manufacturer_code: str | None,
    category: ColorCategory,
    price_per_sqm: float,
    in_stock: bool = True,
) -> None:
    color = await db.scalar(
        select(Color).where(Color.palette_id == palette_id, Color.manufacturer_code == manufacturer_code)
    )
    if not color:
        color = await db.scalar(
            select(Color).where(Color.palette_id == palette_id, Color.name == name, Color.hex == hex_val)
        )
    if not color:
        color = Color(
            palette_id=palette_id,
            name=name,
            hex=hex_val,
            manufacturer_code=manufacturer_code,
            category=category,
            active=True,
        )
        db.add(color)
        await db.flush()

    listing = await db.scalar(
        select(StoreColor).where(StoreColor.store_id == store_id, StoreColor.color_id == color.id)
    )
    if listing:
        listing.active = True
        listing.price_per_sqm = price_per_sqm
        listing.in_stock = in_stock
    else:
        db.add(
            StoreColor(
                store_id=store_id,
                color_id=color.id,
                price_per_sqm=price_per_sqm,
                in_stock=in_stock,
                active=True,
            )
        )
