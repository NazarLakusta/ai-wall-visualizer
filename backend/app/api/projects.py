from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import asset_url, get_current_user
from app.config import settings
from app.database import get_db
from app.models import Project, ProjectStatus, Store, User
from app.schemas import ProjectOut, ProjectStateUpdate
from app.services.file_validation import validate_image_upload
from app.services.rate_limit import upload_limiter
from app.services.storage import StorageService
from app.workers.tasks import process_wall_segmentation

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_out(project: Project) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        status=project.status.value,
        store_id=project.store_id,
        is_test=project.is_test,
        original_url=asset_url(project.original_image),
        mask_url=asset_url(project.mask_image),
        illumination_url=asset_url(project.illumination_image),
        specular_url=asset_url(project.specular_image),
        result_url=asset_url(project.result_image),
        wall_area_sqm=project.wall_area_sqm,
        selected_color_id=project.selected_color_id,
        selected_decor_color_id=project.selected_decor_color_id,
        selected_material_id=project.selected_material_id,
        selected_finish=project.selected_finish,
        editor_mode=project.editor_mode or "paint",
        error_message=project.error_message,
        created_at=project.created_at,
        expires_at=project.expires_at,
    )


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_out(project)


@router.post("/upload", response_model=ProjectOut)
async def upload_project(
    file: UploadFile = File(...),
    store_slug: str = Form(default="demo"),
    telegram_chat_id: int | None = Form(default=None),
    telegram_message_id: int | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not upload_limiter.is_allowed(str(user.telegram_id)):
        raise HTTPException(status_code=429, detail="Upload limit exceeded")

    store = await db.scalar(select(Store).where(Store.slug == store_slug, Store.active.is_(True)))
    if not store:
        raise HTTPException(status_code=400, detail="Store not found")

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
    return _project_out(project)


@router.post("/test", response_model=ProjectOut)
async def create_test_project(
    store_slug: str = Form(default="demo"),
    telegram_chat_id: int | None = Form(default=None),
    telegram_message_id: int | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    store = await db.scalar(select(Store).where(Store.slug == store_slug, Store.active.is_(True)))
    if not store:
        raise HTTPException(status_code=400, detail="Store not found")

    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.retention_hours)
    project = Project(
        user_id=user.id,
        store_id=store.id,
        status=ProjectStatus.READY,
        is_test=True,
        telegram_chat_id=telegram_chat_id,
        telegram_message_id=telegram_message_id,
        expires_at=expires_at,
    )
    db.add(project)
    await db.flush()

    storage = StorageService()
    files = storage.copy_test_project(project.id)
    project.original_image = files.get("original_image")
    project.mask_image = files.get("mask_image")
    project.illumination_image = files.get("illumination_image")
    project.specular_image = files.get("specular_image")
    await db.commit()
    await db.refresh(project)
    return _project_out(project)


@router.post("/{project_id}/open")
async def track_editor_open(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    project.editor_opens = (project.editor_opens or 0) + 1
    await db.commit()
    return {"editor_opens": project.editor_opens}


@router.patch("/{project_id}/state")
async def update_project_state(
    project_id: int,
    body: ProjectStateUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    data = body.model_dump(exclude_unset=True)
    mode = data.pop("mode", None)
    if mode is not None:
        project.editor_mode = mode
    for key, value in data.items():
        setattr(project, key, value)
    await db.commit()
    return {"ok": True}


@router.post("/{project_id}/result")
async def save_result_image(
    project_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    data = await file.read()
    try:
        validate_image_upload(data, settings.max_upload_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ext = ".jpg"
    if file.filename and file.filename.lower().endswith(".png"):
        ext = ".png"
    elif file.content_type == "image/png":
        ext = ".png"

    storage = StorageService()
    rel = storage.save_upload(project_id, f"result{ext}", data)
    project.result_image = rel
    await db.commit()
    filename = f"wall-visualizer-{project_id}{ext}"
    return {"download_url": asset_url(rel), "filename": filename}
