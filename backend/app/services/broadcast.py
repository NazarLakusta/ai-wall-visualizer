from __future__ import annotations

import html
import time
from pathlib import Path

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BroadcastStatus, Lead, Project, Store, StoreBroadcast, User

logger = structlog.get_logger()

TELEGRAM_CAPTION_LIMIT = 1024
SEND_DELAY_SEC = 0.04


def escape_telegram_html(text: str) -> str:
    return html.escape(text or "", quote=False)


def format_broadcast_message(title: str, body: str) -> str:
    safe_title = escape_telegram_html(title.strip())
    safe_body = escape_telegram_html(body.strip())
    message = f"<b>{safe_title}</b>\n\n{safe_body}"
    if len(message) > TELEGRAM_CAPTION_LIMIT:
        return message[: TELEGRAM_CAPTION_LIMIT - 1] + "…"
    return message


def get_store_audience_telegram_ids(db: Session, store_id: int) -> list[int]:
    project_user_ids = db.scalars(
        select(Project.user_id).where(Project.store_id == store_id).distinct()
    ).all()
    lead_user_ids = db.scalars(
        select(Lead.user_id).where(Lead.store_id == store_id).distinct()
    ).all()
    user_ids = set(project_user_ids) | set(lead_user_ids)
    if not user_ids:
        return []
    rows = db.scalars(
        select(User.telegram_id).where(User.id.in_(user_ids)).distinct()
    ).all()
    return [int(tg_id) for tg_id in rows if tg_id]


def audience_count(db: Session, store_id: int) -> int:
    return len(get_store_audience_telegram_ids(db, store_id))


def _send_text(chat_id: int, text: str, bot_token: str) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                url,
                json={"chat_id": int(chat_id), "text": text, "parse_mode": "HTML"},
            )
            if resp.status_code == 200:
                return True
            logger.warning(
                "broadcast_send_failed",
                chat_id=chat_id,
                status=resp.status_code,
                body=resp.text[:200],
            )
            return False
    except httpx.HTTPError as exc:
        logger.warning("broadcast_send_error", chat_id=chat_id, error=str(exc))
        return False


def _send_photo(chat_id: int, photo_path: Path, caption: str, bot_token: str) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    suffix = photo_path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    try:
        data_bytes = photo_path.read_bytes()
    except OSError as exc:
        logger.warning("broadcast_photo_read_failed", path=str(photo_path), error=str(exc))
        return False

    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                url,
                data={"chat_id": str(int(chat_id)), "caption": caption, "parse_mode": "HTML"},
                files={"photo": (photo_path.name, data_bytes, mime)},
            )
            if resp.status_code == 200:
                return True
            logger.warning(
                "broadcast_photo_failed",
                chat_id=chat_id,
                status=resp.status_code,
                body=resp.text[:200],
            )
            return False
    except httpx.HTTPError as exc:
        logger.warning("broadcast_photo_error", chat_id=chat_id, error=str(exc))
        return False


def send_broadcast_to_chat(
    chat_id: int,
    message: str,
    bot_token: str,
    photo_path: Path | None = None,
) -> bool:
    if photo_path and photo_path.is_file():
        return _send_photo(chat_id, photo_path, message, bot_token)
    return _send_text(chat_id, message, bot_token)


def run_store_broadcast(db: Session, broadcast_id: int) -> None:
    from datetime import datetime, timezone

    from app.services.storage import StorageService

    broadcast = db.get(StoreBroadcast, broadcast_id)
    if not broadcast:
        logger.warning("broadcast_not_found", broadcast_id=broadcast_id)
        return

    store = db.get(Store, broadcast.store_id)
    if not store:
        broadcast.status = BroadcastStatus.FAILED.value
        broadcast.error_message = "Store not found"
        db.commit()
        return

    bot_token = (store.telegram_bot_token or "").strip()
    if not bot_token:
        broadcast.status = BroadcastStatus.FAILED.value
        broadcast.error_message = "Bot token not configured"
        db.commit()
        return

    audience = get_store_audience_telegram_ids(db, broadcast.store_id)
    broadcast.status = BroadcastStatus.SENDING.value
    broadcast.total_recipients = len(audience)
    broadcast.started_at = datetime.now(timezone.utc)
    broadcast.sent_count = 0
    broadcast.failed_count = 0
    broadcast.error_message = None
    db.commit()

    if not audience:
        broadcast.status = BroadcastStatus.FAILED.value
        broadcast.error_message = "No recipients"
        broadcast.finished_at = datetime.now(timezone.utc)
        db.commit()
        return

    message = format_broadcast_message(broadcast.title, broadcast.body)
    photo_path = None
    if broadcast.image_path:
        photo_path = StorageService().absolute_path(broadcast.image_path)

    sent = 0
    failed = 0
    for chat_id in audience:
        if send_broadcast_to_chat(chat_id, message, bot_token, photo_path):
            sent += 1
        else:
            failed += 1
        time.sleep(SEND_DELAY_SEC)

    broadcast.sent_count = sent
    broadcast.failed_count = failed
    broadcast.finished_at = datetime.now(timezone.utc)

    if sent == 0:
        broadcast.status = BroadcastStatus.FAILED.value
        broadcast.error_message = "Telegram rejected all messages"
    elif failed == 0:
        broadcast.status = BroadcastStatus.SENT.value
    else:
        broadcast.status = BroadcastStatus.PARTIAL.value
        broadcast.error_message = f"{failed} recipients failed"

    db.commit()
    logger.info(
        "broadcast_finished",
        broadcast_id=broadcast.id,
        store_id=broadcast.store_id,
        sent=sent,
        failed=failed,
        total=len(audience),
    )
