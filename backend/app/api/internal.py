from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Project, ProjectStatus, Store, User
from app.services.jwt import create_user_token
from app.services.file_validation import validate_image_upload
from app.services.storage import StorageService
from app.services.queue_monitor import queue_busy_message, queue_position_message, queue_snapshot
from app.workers.tasks import process_wall_segmentation

router = APIRouter(prefix="/internal", tags=["internal"])

INTERNAL_KEY = settings.secret_key


def verify_internal(key: str = Form(...)):
    if key != INTERNAL_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


async def _get_or_create_user(db: AsyncSession, telegram_id: int, username: str | None, first_name: str | None) -> User:
    user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        user = User(telegram_id=telegram_id, username=username, first_name=first_name)
        db.add(user)
        await db.flush()
    return user


@router.post("/projects/upload")
async def internal_upload(
    file: UploadFile = File(...),
    telegram_id: int = Form(...),
    username: str | None = Form(default=None),
    first_name: str | None = Form(default=None),
    store_slug: str = Form(default="demo"),
    telegram_chat_id: int | None = Form(default=None),
    telegram_message_id: int | None = Form(default=None),
    telegram_bot_id: int | None = Form(default=None),
    key: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    verify_internal(key)
    snap = queue_snapshot()
    if not snap["accepting_uploads"]:
        raise HTTPException(status_code=503, detail=queue_busy_message(snap))

    store = await db.scalar(select(Store).where(Store.slug == store_slug, Store.active.is_(True)))
    if not store:
        raise HTTPException(status_code=400, detail="Store not found")

    user = await _get_or_create_user(db, telegram_id, username, first_name)
    data = await file.read()
    try:
        validate_image_upload(data, settings.max_upload_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.retention_hours)
    project = Project(
        user_id=user.id,
        store_id=store.id,
        status=ProjectStatus.RECEIVED,
        telegram_chat_id=telegram_chat_id,
        telegram_message_id=telegram_message_id,
        telegram_bot_id=telegram_bot_id,
        expires_at=expires_at,
    )
    db.add(project)
    await db.flush()

    storage = StorageService()
    ext = ".jpg" if file.filename and file.filename.lower().endswith((".jpg", ".jpeg")) else ".png"
    rel = storage.save_upload(project.id, f"original{ext}", data)
    project.original_image = rel
    project.status = ProjectStatus.QUEUED
    await db.commit()
    await db.refresh(project)

    process_wall_segmentation.delay(project.id)
    snap = queue_snapshot()
    return {
        "project_id": project.id,
        "status": project.status.value,
        "queue_position": snap["pending_tasks"],
        "estimated_wait_seconds": snap["estimated_wait_seconds"],
    }


@router.post("/projects/test")
async def internal_test_project(
    telegram_id: int = Form(...),
    username: str | None = Form(default=None),
    first_name: str | None = Form(default=None),
    store_slug: str = Form(default="demo"),
    telegram_chat_id: int | None = Form(default=None),
    telegram_message_id: int | None = Form(default=None),
    telegram_bot_id: int | None = Form(default=None),
    key: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    verify_internal(key)
    store = await db.scalar(select(Store).where(Store.slug == store_slug, Store.active.is_(True)))
    if not store:
        raise HTTPException(status_code=400, detail="Store not found")

    user = await _get_or_create_user(db, telegram_id, username, first_name)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.retention_hours)
    project = Project(
        user_id=user.id,
        store_id=store.id,
        status=ProjectStatus.READY,
        is_test=True,
        telegram_chat_id=telegram_chat_id,
        telegram_message_id=telegram_message_id,
        telegram_bot_id=telegram_bot_id,
        expires_at=expires_at,
    )
    db.add(project)
    await db.flush()

    storage = StorageService()
    files = storage.copy_test_project(project.id)
    if not files.get("original_image"):
        raise HTTPException(
            status_code=500,
            detail="Test files missing. Put original.png, mask.png, specular.png into storage/test/",
        )
    project.original_image = files.get("original_image")
    project.mask_image = files.get("mask_image")
    project.illumination_image = files.get("illumination_image")
    project.specular_image = files.get("specular_image")
    await db.commit()
    await db.refresh(project)
    access_token = create_user_token(user.id, user.telegram_id)
    return {"project_id": project.id, "status": project.status.value, "access_token": access_token}
