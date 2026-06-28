def calc_total_price(price_per_sqm: float | None, area_sqm: float | None) -> float | None:
    if price_per_sqm is None or area_sqm is None or area_sqm <= 0:
        return None
    return round(price_per_sqm * area_sqm, 2)


def format_uah(amount: float | None) -> str:
    if amount is None:
        return ""
    return f"₴{amount:,.0f}".replace(",", " ")
