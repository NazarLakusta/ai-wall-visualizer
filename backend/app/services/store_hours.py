"""Business hours helpers for store-facing customer messages."""

from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from app.models import Store

DEFAULT_OPEN = "09:00"
DEFAULT_CLOSE = "19:00"
DEFAULT_TZ = "Europe/Kyiv"


def _parse_hhmm(value: str | None, fallback: str) -> time:
    raw = (value or fallback).strip()
    parts = raw.split(":")
    if len(parts) != 2:
        return _parse_hhmm(fallback, fallback)
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("out of range")
        return time(hour=hour, minute=minute)
    except ValueError:
        return _parse_hhmm(fallback, fallback)


def format_hhmm(value: str | None, fallback: str) -> str:
    t = _parse_hhmm(value, fallback)
    return f"{t.hour:02d}:{t.minute:02d}"


def store_timezone(store: Store) -> ZoneInfo:
    name = (store.business_timezone or DEFAULT_TZ).strip() or DEFAULT_TZ
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def store_local_now(store: Store, at: datetime | None = None) -> datetime:
    base = at or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base.astimezone(store_timezone(store))


def is_store_open(store: Store, at: datetime | None = None) -> bool:
    local = store_local_now(store, at)
    open_t = _parse_hhmm(store.business_open_time, DEFAULT_OPEN)
    close_t = _parse_hhmm(store.business_close_time, DEFAULT_CLOSE)
    now_t = local.time()
    if open_t == close_t:
        return True
    if open_t < close_t:
        return open_t <= now_t < close_t
    # Overnight window (e.g. 22:00–06:00)
    return now_t >= open_t or now_t < close_t


def next_contact_phrase(store: Store, at: datetime | None = None) -> str:
    local = store_local_now(store, at)
    open_t = _parse_hhmm(store.business_open_time, DEFAULT_OPEN)
    open_label = format_hhmm(store.business_open_time, DEFAULT_OPEN)
    if local.time() < open_t:
        return f"сьогодні о <b>{open_label}</b>"
    return f"завтра о <b>{open_label}</b>"


def business_hours_label(store: Store) -> str:
    open_label = format_hhmm(store.business_open_time, DEFAULT_OPEN)
    close_label = format_hhmm(store.business_close_time, DEFAULT_CLOSE)
    return f"{open_label} – {close_label}"


def customer_lead_ack_message(store: Store, at: datetime | None = None) -> str:
    if is_store_open(store, at):
        return (
            f"✨ <b>Дякуємо, що обрали {store.name}!</b>\n\n"
            f"Ваш запит уже у консультанта.\n"
            f"Зателефонуємо протягом <b>15 хвилин</b> — допоможемо з кольором і розрахунком."
        )
    when = next_contact_phrase(store, at)
    hours = business_hours_label(store)
    return (
        f"✨ <b>Дякуємо за ваш запит!</b>\n\n"
        f"Зараз <b>{store.name}</b> поза графіком — але заявку ми зберегли.\n"
        f"Передзвонимо вам {when} і все детально розповімо.\n\n"
        f"🕐 Працюємо: <b>{hours}</b>"
    )


def customer_lead_contacted_message(store: Store) -> str:
    phone_line = f"\n\n📞 Якщо зручніше — {store.phone}" if store.phone else ""
    return (
        f"👋 <b>Вітаємо від {store.name}!</b>\n\n"
        f"Вашу заявку вже взяв консультант — підбираємо рішення під ваш інтер’єр."
        f"{phone_line}"
    )
