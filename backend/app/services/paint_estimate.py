"""Paint volume and optimal can packaging calculator."""

from __future__ import annotations

import math
from dataclasses import dataclass


WASTE_PERCENT = 10.0

DEFAULT_BASE_SURCHARGE = {"A": 0.0, "B": 5.0, "C": 15.0}


@dataclass
class PackOption:
    volume_liters: float
    price_uah: float
    label: str


@dataclass
class PackLine:
    volume_liters: float
    price_uah: float
    label: str
    count: int

    @property
    def line_total(self) -> float:
        return round(self.price_uah * self.count, 2)


@dataclass
class PaintEstimate:
    area_sqm: float
    coats: int
    coverage_sqm_per_liter: float
    waste_percent: float
    liters_needed: float
    tint_base: str | None
    base_surcharge_percent: float
    packs: list[PackLine]
    packs_subtotal_uah: float
    base_surcharge_uah: float
    total_uah: float
    summary_short: str
    summary_detail: str


def pack_label(volume_liters: float, label: str | None = None) -> str:
    if label:
        return label
    if volume_liters == int(volume_liters):
        return f"{int(volume_liters)} л"
    return f"{volume_liters:g} л"


def calc_liters_needed(
    area_sqm: float,
    coats: int,
    coverage_sqm_per_liter: float,
    waste_percent: float = WASTE_PERCENT,
) -> float:
    if area_sqm <= 0 or coats <= 0 or coverage_sqm_per_liter <= 0:
        return 0.0
    raw = area_sqm * coats / coverage_sqm_per_liter
    return raw * (1 + waste_percent / 100.0)


def optimize_paint_packs(liters_needed: float, options: list[PackOption]) -> list[PackLine]:
    """Minimize cost while total volume >= liters_needed."""
    active = [o for o in options if o.volume_liters > 0 and o.price_uah > 0]
    if liters_needed <= 0 or not active:
        return []

    opts = sorted(active, key=lambda o: o.volume_liters)
    need_ml = max(1, int(math.ceil(liters_needed * 1000)))
    max_pack_ml = max(int(round(o.volume_liters * 1000)) for o in opts)
    cap = need_ml + max_pack_ml

    inf = 10**15
    dp = [inf] * (cap + 1)
    dp[0] = 0.0
    prev_ml: list[int | None] = [None] * (cap + 1)
    prev_pack: list[int | None] = [None] * (cap + 1)

    for ml in range(cap + 1):
        if dp[ml] >= inf:
            continue
        for i, opt in enumerate(opts):
            vol_ml = max(1, int(round(opt.volume_liters * 1000)))
            nml = min(cap, ml + vol_ml)
            cost = dp[ml] + opt.price_uah
            if cost < dp[nml]:
                dp[nml] = cost
                prev_ml[nml] = ml
                prev_pack[nml] = i

    best_ml = min(range(need_ml, cap + 1), key=lambda m: dp[m])
    if dp[best_ml] >= inf:
        return []

    counts: dict[int, int] = {}
    ml = best_ml
    while ml > 0 and prev_pack[ml] is not None:
        idx = prev_pack[ml]
        assert idx is not None
        counts[idx] = counts.get(idx, 0) + 1
        ml = prev_ml[ml] or 0

    lines: list[PackLine] = []
    for i in sorted(counts.keys(), key=lambda x: opts[x].volume_liters, reverse=True):
        opt = opts[i]
        lines.append(
            PackLine(
                volume_liters=opt.volume_liters,
                price_uah=opt.price_uah,
                label=pack_label(opt.volume_liters, opt.label),
                count=counts[i],
            )
        )
    return lines


def resolve_base_surcharge_percent(tint_base: str | None, explicit: float | None) -> float:
    if explicit is not None and explicit > 0:
        return float(explicit)
    if tint_base:
        return DEFAULT_BASE_SURCHARGE.get(tint_base.upper(), 0.0)
    return 0.0


def build_paint_estimate(
    area_sqm: float,
    coats: int,
    coverage_sqm_per_liter: float,
    pack_options: list[PackOption],
    tint_base: str | None = None,
    base_surcharge_percent: float | None = None,
    waste_percent: float = WASTE_PERCENT,
) -> PaintEstimate | None:
    liters = calc_liters_needed(area_sqm, coats, coverage_sqm_per_liter, waste_percent)
    if liters <= 0:
        return None

    packs = optimize_paint_packs(liters, pack_options)
    if not packs:
        return None

    surcharge_pct = resolve_base_surcharge_percent(tint_base, base_surcharge_percent)
    packs_subtotal = round(sum(p.line_total for p in packs), 2)
    surcharge_uah = round(packs_subtotal * surcharge_pct / 100.0, 2)
    total = round(packs_subtotal + surcharge_uah, 2)

    pack_text = ", ".join(f"{p.count}×{p.label} (₴{p.line_total:g})" for p in packs)
    base_text = f", база {tint_base.upper()}" if tint_base else ""
    surcharge_text = f", надбавка за базу {surcharge_pct:g}%" if surcharge_pct > 0 else ""

    summary_short = f"{pack_text} = ₴{total:g}"
    summary_detail = (
        f"Площа {area_sqm:g} м² × {coats} шари, "
        f"витрата {coverage_sqm_per_liter:g} м²/л{base_text}{surcharge_text}\n"
        f"Потрібно ~{liters:.1f} л (запас {waste_percent:g}%)\n"
        f"Фасування: {pack_text}\n"
        f"Банки: ₴{packs_subtotal:g}"
        + (f" + база: ₴{surcharge_uah:g}" if surcharge_uah else "")
        + f" = ₴{total:g}"
    )

    return PaintEstimate(
        area_sqm=area_sqm,
        coats=coats,
        coverage_sqm_per_liter=coverage_sqm_per_liter,
        waste_percent=waste_percent,
        liters_needed=round(liters, 2),
        tint_base=tint_base.upper() if tint_base else None,
        base_surcharge_percent=surcharge_pct,
        packs=packs,
        packs_subtotal_uah=packs_subtotal,
        base_surcharge_uah=surcharge_uah,
        total_uah=total,
        summary_short=summary_short,
        summary_detail=summary_detail,
    )
