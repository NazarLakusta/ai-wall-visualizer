"""Telegram alerts for platform owner (ops bot)."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import redis
import structlog

from app.config import settings
from app.services.ops_collector import collect_ops_snapshot

logger = structlog.get_logger()


def _redis() -> redis.Redis:
    return redis.from_url(settings.celery_broker_url, decode_responses=True)


def _chat_id() -> int | None:
    raw = (settings.ops_telegram_chat_id or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def can_send_alert(kind: str, cooldown_seconds: int = 1800) -> bool:
    """Rate-limit repeated alerts of the same kind."""
    try:
        client = _redis()
        key = f"ops:cooldown:{kind}"
        return bool(client.set(key, "1", nx=True, ex=cooldown_seconds))
    except redis.RedisError:
        return True


def send_ops_message(text: str) -> bool:
    if not settings.ops_alerts_enabled:
        return False
    token = settings.ops_telegram_bot_token.strip()
    chat_id = _chat_id()
    if not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                url,
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
        if resp.status_code == 200:
            return True
        logger.warning("ops_telegram_failed", status=resp.status_code, body=resp.text[:300])
    except httpx.HTTPError as exc:
        logger.warning("ops_telegram_error", error=str(exc))
    return False


def _status_icon(ok: bool) -> str:
    return "✅" if ok else "❌"


def format_ops_status(snap: dict | None = None) -> str:
    snap = snap or collect_ops_snapshot()
    queue = snap["queue"]
    pending = queue["pending_tasks"]
    wait_min = max(0, round(queue["estimated_wait_seconds"] / 60))
    workers = queue["worker_count"]
    accepting = "так" if queue["accepting_uploads"] else "ні (черга повна)"

    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    lines = [
        f"🖥 <b>WallViz Ops</b> · {now}",
        "",
        f"{_status_icon(snap['db_ok'])} База даних",
        f"{_status_icon(snap['redis_ok'])} Redis / черга",
        "",
        f"🤖 <b>AI-черга:</b> {pending} фото · ~{wait_min} хв очікування",
        f"⚙️ Воркерів: {workers} · приймаємо фото: <b>{accepting}</b>",
        f"🔄 В обробці зараз: {snap['projects_processing']}",
        "",
        f"🏪 Магазинів: {snap['stores_with_bot']}/{snap['stores_total']} (з ботом)",
        f"📸 Фото за годину: {snap['projects_hour']}",
        f"❌ Помилок AI за годину: {snap['projects_hour_errors']}",
        f"📬 Заявки за 24 год: {snap['leads_24h']} (нових: {snap['leads_new_24h']})",
    ]

    if pending >= settings.ops_queue_critical_threshold:
        lines.insert(2, f"🚨 <b>КРИТИЧНА ЧЕРГА</b> — {pending} фото!")
    elif pending >= settings.ops_queue_warn_threshold:
        lines.insert(2, f"⚠️ <b>Високе навантаження</b> — {pending} фото в черзі")

    errors = snap.get("recent_errors") or []
    if errors:
        lines.append("")
        lines.append("<b>Останні помилки:</b>")
        for err in errors[:3]:
            lines.append(
                f"• #{err['project_id']} {err['store']}: "
                f"<code>{err['error']}</code>"
            )

    return "\n".join(lines)


def send_ops_status() -> bool:
    return send_ops_message(format_ops_status())


def ops_alert(text: str, *, kind: str | None = None, cooldown_seconds: int = 1800) -> bool:
    if kind and not can_send_alert(kind, cooldown_seconds):
        return False
    return send_ops_message(text)


def ops_alert_ai_failed(project_id: int, store_name: str, error: str) -> None:
    if not settings.ops_alerts_enabled:
        return
    msg = (
        f"❌ <b>AI не обробив фото</b>\n"
        f"🏪 {store_name}\n"
        f"Проєкт <b>#{project_id}</b>\n"
        f"<code>{error[:300]}</code>"
    )
    ops_alert(msg, kind=f"ai_fail:{project_id}", cooldown_seconds=3600)


def ops_alert_queue_high(snap: dict | None = None) -> None:
    snap = snap or collect_ops_snapshot()
    pending = snap["queue"]["pending_tasks"]
    if pending < settings.ops_queue_warn_threshold:
        return
    level = "🚨 КРИТИЧНО" if pending >= settings.ops_queue_critical_threshold else "⚠️ Увага"
    wait_min = max(1, round(snap["queue"]["estimated_wait_seconds"] / 60))
    msg = (
        f"{level} <b>Черга AI</b>\n"
        f"У черзі: <b>{pending}</b> фото\n"
        f"Очікування: ~<b>{wait_min}</b> хв\n"
        f"Воркерів: {snap['queue']['worker_count']}"
    )
    kind = "queue_critical" if pending >= settings.ops_queue_critical_threshold else "queue_warn"
    cooldown = 3600 if pending >= settings.ops_queue_critical_threshold else 1800
    ops_alert(msg, kind=kind, cooldown_seconds=cooldown)


def evaluate_ops_alerts(snap: dict | None = None) -> None:
    """Send threshold-based alerts (heartbeat sends full status separately)."""
    snap = snap or collect_ops_snapshot()
    if not snap["db_ok"]:
        ops_alert("❌ <b>База даних недоступна</b>", kind="db_down", cooldown_seconds=600)
    if not snap["redis_ok"]:
        ops_alert("❌ <b>Redis недоступний</b> (черга Celery)", kind="redis_down", cooldown_seconds=600)
    ops_alert_queue_high(snap)
