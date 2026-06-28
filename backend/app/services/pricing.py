def calc_total_price(price_per_sqm: float | None, area_sqm: float | None) -> float | None:
    if price_per_sqm is None or area_sqm is None or area_sqm <= 0:
        return None
    return round(price_per_sqm * area_sqm, 2)


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


def format_uah(amount: float | None) -> str:
    if amount is None:
        return ""
    return f"₴{amount:,.0f}".replace(",", " ")
