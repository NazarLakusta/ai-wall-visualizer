from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_platform_admin, get_current_user
from app.config import settings
from app.database import get_db
from app.models import PlatformAdmin, Project, Store, StoreAdmin, User
from app.schemas import AdminLoginRequest, TelegramAuthRequest, TokenResponse
from app.services.jwt import create_access_token, verify_password
from app.services.telegram_auth import validate_telegram_init_data

router = APIRouter(prefix="/auth", tags=["auth"])


async def _bot_token_for_project(db: AsyncSession, project_id: int | None) -> str:
    if project_id:
        project = await db.get(Project, project_id)
        if project:
            store = await db.get(Store, project.store_id)
            if store and store.telegram_bot_token:
                return store.telegram_bot_token
    if settings.telegram_bot_token:
        return settings.telegram_bot_token
    raise HTTPException(status_code=400, detail="Telegram bot not configured for this store")


@router.post("/telegram", response_model=TokenResponse)
async def auth_telegram(body: TelegramAuthRequest, db: AsyncSession = Depends(get_db)):
    bot_token = await _bot_token_for_project(db, body.project_id)
    try:
        tg_user = validate_telegram_init_data(body.init_data, bot_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    telegram_id = tg_user["id"]
    user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=tg_user.get("username"),
            first_name=tg_user.get("first_name"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(
        {"sub": str(user.id), "type": "user", "telegram_id": telegram_id},
        expires_delta=timedelta(hours=1),
    )
    return TokenResponse(access_token=token)


@router.post("/admin/login", response_model=TokenResponse)
async def admin_login(body: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    admin = await db.scalar(select(StoreAdmin).where(StoreAdmin.email == body.email))
    if not admin or not admin.active or not verify_password(body.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(
        {
            "sub": str(admin.id),
            "type": "admin",
            "store_id": admin.store_id,
            "role": admin.role.value,
        },
        expires_delta=timedelta(hours=8),
    )
    return TokenResponse(access_token=token)


@router.get("/me")
async def me_user(user: User = Depends(get_current_user)):
    return {"id": user.id, "telegram_id": user.telegram_id, "username": user.username}


@router.get("/admin/me")
async def me_admin(admin: StoreAdmin = Depends(get_current_admin)):
    return {"id": admin.id, "email": admin.email, "store_id": admin.store_id, "role": admin.role.value}


@router.post("/platform/login", response_model=TokenResponse)
async def platform_login(body: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    admin = await db.scalar(select(PlatformAdmin).where(PlatformAdmin.email == body.email))
    if not admin or not admin.active or not verify_password(body.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(
        {"sub": str(admin.id), "type": "platform"},
        expires_delta=timedelta(hours=12),
    )
    return TokenResponse(access_token=token)


@router.get("/platform/me")
async def me_platform(admin: PlatformAdmin = Depends(get_current_platform_admin)):
    return {"id": admin.id, "email": admin.email, "name": admin.name}
