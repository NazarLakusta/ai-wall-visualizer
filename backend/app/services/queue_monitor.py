"""Celery / AI queue visibility and load-shedding helpers."""

from __future__ import annotations

import redis

from app.config import settings


def _redis_client() -> redis.Redis:
    return redis.from_url(settings.celery_broker_url, decode_responses=True)


def celery_queue_length() -> int:
    """Approximate number of pending segmentation tasks in Redis."""
    try:
        client = _redis_client()
        return int(client.llen("celery") or 0)
    except redis.RedisError:
        return 0


def queue_snapshot() -> dict:
    pending = celery_queue_length()
    workers = max(1, settings.ai_worker_count)
    avg = max(15, settings.avg_processing_seconds)
    eta_per_job = avg / workers
    return {
        "pending_tasks": pending,
        "worker_count": workers,
        "avg_processing_seconds": avg,
        "max_queue_size": settings.max_ai_queue,
        "estimated_wait_seconds": int(pending * eta_per_job),
        "accepting_uploads": pending < settings.max_ai_queue,
    }


def queue_busy_message(snapshot: dict | None = None) -> str:
    snap = snapshot or queue_snapshot()
    wait_min = max(1, round(snap["estimated_wait_seconds"] / 60))
    return (
        f"⏳ Зараз високе навантаження ({snap['pending_tasks']} фото в черзі).\n"
        f"Орієнтовне очікування для нових завантажень: ~{wait_min} хв.\n\n"
        "Спробуйте «🖼 Тестове фото» — воно відкривається одразу, без черги."
    )


def queue_position_message(position: int, snapshot: dict | None = None) -> str:
    snap = snapshot or queue_snapshot()
    workers = snap["worker_count"]
    avg = snap["avg_processing_seconds"]
    eta_sec = max(30, int(((max(1, position) - 1) / workers) * avg + avg * 0.5))
    eta_min = max(1, round(eta_sec / 60))
    if position <= 1:
        return "⏳ <b>Очікує в черзі</b>\n\nВаше фото скоро піде в обробку (~1 хв)."
    return (
        f"⏳ <b>Очікує в черзі</b>\n\n"
        f"Позиція: <b>~{position}</b> · орієнтовно <b>~{eta_min} хв</b>\n"
        "Ми повідомимо, коли буде готово."
    )
