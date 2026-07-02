"""Color code systems per brand (RAL, NCS, manufacturer palette, etc.)."""

from __future__ import annotations

import re

DEFAULT_CODE_SYSTEM = "manufacturer"

CODE_SYSTEM_LABELS: dict[str, str] = {
    "ral": "RAL",
    "ncs": "NCS",
    "manufacturer": "Палітра виробника",
    "none": "Без коду",
    "other": "Інше",
}

VALID_CODE_SYSTEMS = frozenset(CODE_SYSTEM_LABELS)


def normalize_code_system(value: str | None) -> str:
    if not value:
        return DEFAULT_CODE_SYSTEM
    key = value.strip().lower()
    return key if key in VALID_CODE_SYSTEMS else DEFAULT_CODE_SYSTEM


def code_system_label(value: str | None) -> str:
    return CODE_SYSTEM_LABELS.get(normalize_code_system(value), CODE_SYSTEM_LABELS["manufacturer"])


def _normalize_ral(raw: str) -> str:
    cleaned = re.sub(r"^ral\s*", "", raw.strip(), flags=re.IGNORECASE)
    return f"RAL {cleaned}".strip()


def _normalize_ncs(raw: str) -> str:
    cleaned = re.sub(r"^ncs\s*", "", raw.strip(), flags=re.IGNORECASE)
    return f"NCS {cleaned}".strip()


def format_display_code(code_system: str | None, raw_code: str | None) -> str | None:
    if not raw_code or not str(raw_code).strip():
        return None
    raw = str(raw_code).strip()
    system = normalize_code_system(code_system)
    if system == "none":
        return None
    if system == "ral":
        return _normalize_ral(raw)
    if system == "ncs":
        return _normalize_ncs(raw)
    return raw


def search_code_variants(search: str) -> list[str]:
    """Extra search terms: strip RAL/NCS prefix so 'RAL 7016' matches code '7016'."""
    q = search.strip()
    if not q:
        return []
    variants = [q]
    stripped = re.sub(r"^(ral|ncs)\s+", "", q, flags=re.IGNORECASE).strip()
    if stripped and stripped.lower() != q.lower():
        variants.append(stripped)
    return variants
