from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StoreDiscount

SCOPE_PRIORITY: dict[str, int] = {
    "color": 100,
    "decor_color": 100,
    "brand": 80,
    "material": 80,
    "paint": 60,
    "decor": 60,
    "all": 40,
}

VALID_DISCOUNT_SCOPES = frozenset(SCOPE_PRIORITY.keys())


async def load_store_discounts(db: AsyncSession, store_id: int) -> list[StoreDiscount]:
    rows = await db.scalars(
        select(StoreDiscount).where(
            StoreDiscount.store_id == store_id,
            StoreDiscount.active.is_(True),
        )
    )
    return list(rows.all())


def apply_discount_amount(price: float | None, discount_percent: float | None) -> tuple[float | None, float | None]:
    if price is None or discount_percent is None or discount_percent <= 0:
        return price, None
    discounted = max(0.0, round(price * (1 - discount_percent / 100), 2))
    return discounted, price


def resolve_paint_discount_percent(
    discounts: list[StoreDiscount],
    color_id: int,
    brand_id: int,
) -> float | None:
    matches: list[StoreDiscount] = []
    for d in discounts:
        if d.scope == "color" and d.target_id == color_id:
            matches.append(d)
        elif d.scope == "brand" and d.target_id == brand_id:
            matches.append(d)
        elif d.scope == "paint":
            matches.append(d)
        elif d.scope == "all":
            matches.append(d)
    if not matches:
        return None
    best = max(matches, key=lambda d: SCOPE_PRIORITY.get(d.scope, 0))
    return best.discount_percent


def resolve_decor_discount_percent(
    discounts: list[StoreDiscount],
    material_id: int,
    decor_color_id: int | None = None,
) -> float | None:
    matches: list[StoreDiscount] = []
    for d in discounts:
        if decor_color_id and d.scope == "decor_color" and d.target_id == decor_color_id:
            matches.append(d)
        elif d.scope == "material" and d.target_id == material_id:
            matches.append(d)
        elif d.scope == "decor":
            matches.append(d)
        elif d.scope == "all":
            matches.append(d)
    if not matches:
        return None
    best = max(matches, key=lambda d: SCOPE_PRIORITY.get(d.scope, 0))
    return best.discount_percent


def resolve_brand_discount_percent(
    discounts: list[StoreDiscount],
    brand_id: int,
) -> float | None:
    matches: list[StoreDiscount] = []
    for d in discounts:
        if d.scope == "brand" and d.target_id == brand_id:
            matches.append(d)
        elif d.scope == "paint":
            matches.append(d)
        elif d.scope == "all":
            matches.append(d)
    if not matches:
        return None
    best = max(matches, key=lambda d: SCOPE_PRIORITY.get(d.scope, 0))
    return best.discount_percent


def promo_message(discount: StoreDiscount, target_label: str | None = None) -> str:
    if discount.label:
        return discount.label
    pct = f"−{discount.discount_percent:g}%"
    if discount.scope == "all":
        return f"{pct} на весь каталог"
    if discount.scope == "paint":
        return f"{pct} на всю фарбу"
    if discount.scope == "decor":
        return f"{pct} на всю декоративку"
    if discount.scope == "brand" and target_label:
        return f"{pct} на {target_label}"
    if discount.scope == "color" and target_label:
        return f"{pct} на колір {target_label}"
    if discount.scope == "material" and target_label:
        return f"{pct} на {target_label}"
    if discount.scope == "decor_color" and target_label:
        return f"{pct} на відтінок {target_label}"
    return pct


def scope_requires_target(scope: str) -> bool:
    return scope in {"brand", "color", "material", "decor_color"}
