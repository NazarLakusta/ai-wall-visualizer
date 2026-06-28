"""Collect platform health metrics for ops Telegram alerts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import redis
from sqlalchemy import func, select

from app.config import settings
from app.database import SyncSessionLocal
from app.models import Lead, LeadStatus, Project, ProjectStatus, Store
from app.services.queue_monitor import queue_snapshot


def _ping_redis() -> bool:
    try:
        client = redis.from_url(settings.celery_broker_url, decode_responses=True)
        return bool(client.ping())
    except redis.RedisError:
        return False


def _ping_db() -> bool:
    try:
        with SyncSessionLocal() as db:
            db.execute(select(1))
        return True
    except Exception:
        return False


def collect_ops_snapshot() -> dict:
    now = datetime.now(timezone.utc)
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(hours=24)

    queue = queue_snapshot()
    snap: dict = {
        "at": now.isoformat(),
        "db_ok": _ping_db(),
        "redis_ok": _ping_redis(),
        "queue": queue,
        "stores_total": 0,
        "stores_with_bot": 0,
        "projects_hour": 0,
        "projects_hour_errors": 0,
        "projects_processing": 0,
        "leads_24h": 0,
        "leads_new_24h": 0,
        "recent_errors": [],
    }

    with SyncSessionLocal() as db:
        snap["stores_total"] = int(
            db.scalar(select(func.count()).select_from(Store).where(Store.active.is_(True))) or 0
        )
        snap["stores_with_bot"] = int(
            db.scalar(
                select(func.count()).select_from(Store).where(
                    Store.active.is_(True),
                    Store.telegram_bot_token.isnot(None),
                    Store.telegram_bot_token != "",
                )
            )
            or 0
        )
        snap["projects_hour"] = int(
            db.scalar(
                select(func.count()).select_from(Project).where(Project.created_at >= hour_ago)
            )
            or 0
        )
        snap["projects_hour_errors"] = int(
            db.scalar(
                select(func.count()).select_from(Project).where(
                    Project.status == ProjectStatus.ERROR,
                    Project.created_at >= hour_ago,
                )
            )
            or 0
        )
        snap["projects_processing"] = int(
            db.scalar(
                select(func.count()).select_from(Project).where(
                    Project.status.in_([ProjectStatus.QUEUED, ProjectStatus.PROCESSING])
                )
            )
            or 0
        )
        snap["leads_24h"] = int(
            db.scalar(select(func.count()).select_from(Lead).where(Lead.created_at >= day_ago))
            or 0
        )
        snap["leads_new_24h"] = int(
            db.scalar(
                select(func.count()).select_from(Lead).where(
                    Lead.created_at >= day_ago,
                    Lead.status == LeadStatus.NEW,
                )
            )
            or 0
        )

        error_rows = db.scalars(
            select(Project)
            .where(Project.status == ProjectStatus.ERROR, Project.created_at >= hour_ago)
            .order_by(Project.created_at.desc())
            .limit(5)
        )
        for project in error_rows.all():
            store = db.get(Store, project.store_id)
            snap["recent_errors"].append(
                {
                    "project_id": project.id,
                    "store": store.name if store else f"#{project.store_id}",
                    "error": (project.error_message or "unknown")[:120],
                }
            )

    return snap
