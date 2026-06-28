import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_platform_admin
from app.database import get_db
from app.models import AdminRole, Lead, LeadStatus, PlatformAdmin, Project, Store, StoreAdmin
from app.schemas import (
    BrandOut,
    ColorCreate,
    ColorOut,
    ColorUpdate,
    PlatformStatsOut,
    PlatformStoreAdminCreate,
    PlatformStoreAdminOut,
    PlatformStoreAdminUpdate,
    PlatformStoreCreate,
    PlatformStoreOut,
    PlatformStoreUpdate,
    StockUpdate,
)
from app.services.catalog_ops import (
    add_color_to_store,
    list_brands,
    list_store_colors,
    remove_color_from_store,
    set_store_color_stock,
    update_store_color,
)
from app.services.jwt import hash_password

router = APIRouter(prefix="/platform", tags=["platform"])

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _store_out(
    store: Store,
    *,
    admins_count: int = 0,
    projects_count: int = 0,
    leads_count: int = 0,
) -> PlatformStoreOut:
    token = (store.telegram_bot_token or "").strip()
    hint = f"…{token[-6:]}" if len(token) > 6 else None
    return PlatformStoreOut(
        id=store.id,
        name=store.name,
        slug=store.slug,
        phone=store.phone,
        address=store.address,
        telegram_username=store.telegram_username,
        manager_telegram_chat_id=store.manager_telegram_chat_id,
        leads_group_chat_id=store.leads_group_chat_id,
        active=store.active,
        has_bot_token=bool(token),
        bot_token_hint=hint,
        admins_count=admins_count,
        projects_count=projects_count,
        leads_count=leads_count,
        created_at=store.created_at,
    )


async def _store_counts(db: AsyncSession, store_id: int) -> tuple[int, int, int]:
    admins = await db.scalar(
        select(func.count()).select_from(StoreAdmin).where(StoreAdmin.store_id == store_id)
    )
    projects = await db.scalar(
        select(func.count()).select_from(Project).where(Project.store_id == store_id)
    )
    leads = await db.scalar(
        select(func.count()).select_from(Lead).where(Lead.store_id == store_id)
    )
    return int(admins or 0), int(projects or 0), int(leads or 0)


@router.get("/stats", response_model=PlatformStatsOut)
async def platform_stats(
    _: PlatformAdmin = Depends(get_current_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    stores = await db.scalars(select(Store))
    store_list = list(stores.all())
    projects = await db.scalar(select(func.count()).select_from(Project))
    leads = await db.scalar(select(func.count()).select_from(Lead))
    leads_new = await db.scalar(
        select(func.count()).select_from(Lead).where(Lead.status == LeadStatus.NEW)
    )
    return PlatformStatsOut(
        stores_total=len(store_list),
        stores_active=sum(1 for s in store_list if s.active),
        projects_total=int(projects or 0),
        leads_total=int(leads or 0),
        leads_new=int(leads_new or 0),
    )


@router.get("/stores", response_model=list[PlatformStoreOut])
async def list_stores(
    _: PlatformAdmin = Depends(get_current_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    stores = await db.scalars(select(Store).order_by(Store.name))
    out: list[PlatformStoreOut] = []
    for store in stores.all():
        ac, pc, lc = await _store_counts(db, store.id)
        out.append(_store_out(store, admins_count=ac, projects_count=pc, leads_count=lc))
    return out


@router.post("/stores", response_model=PlatformStoreOut)
async def create_store(
    body: PlatformStoreCreate,
    _: PlatformAdmin = Depends(get_current_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    slug = body.slug.strip().lower()
    if not SLUG_RE.match(slug):
        raise HTTPException(status_code=400, detail="Invalid slug format")

    exists = await db.scalar(select(Store).where(Store.slug == slug))
    if exists:
        raise HTTPException(status_code=400, detail="Store slug already exists")

    store = Store(
        name=body.name.strip(),
        slug=slug,
        phone=body.phone,
        address=body.address,
        telegram_username=body.telegram_username,
        telegram_bot_token=(body.telegram_bot_token or "").strip() or None,
        active=True,
    )
    db.add(store)
    await db.flush()

    admins_count = 0
    if body.admin_email and body.admin_password:
        email_taken = await db.scalar(select(StoreAdmin).where(StoreAdmin.email == body.admin_email))
        if email_taken:
            raise HTTPException(status_code=400, detail="Admin email already in use")
        db.add(
            StoreAdmin(
                store_id=store.id,
                email=body.admin_email.lower(),
                password_hash=hash_password(body.admin_password),
                role=AdminRole.OWNER,
                active=True,
            )
        )
        admins_count = 1

    await db.commit()
    await db.refresh(store)
    return _store_out(store, admins_count=admins_count)


@router.get("/stores/{store_id}", response_model=PlatformStoreOut)
async def get_store(
    store_id: int,
    _: PlatformAdmin = Depends(get_current_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    ac, pc, lc = await _store_counts(db, store.id)
    return _store_out(store, admins_count=ac, projects_count=pc, leads_count=lc)


@router.put("/stores/{store_id}", response_model=PlatformStoreOut)
async def update_store(
    store_id: int,
    body: PlatformStoreUpdate,
    _: PlatformAdmin = Depends(get_current_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    data = body.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"]:
        slug = data["slug"].strip().lower()
        if not SLUG_RE.match(slug):
            raise HTTPException(status_code=400, detail="Invalid slug format")
        other = await db.scalar(select(Store).where(Store.slug == slug, Store.id != store_id))
        if other:
            raise HTTPException(status_code=400, detail="Store slug already exists")
        data["slug"] = slug

    if "telegram_bot_token" in data:
        token = (data.pop("telegram_bot_token") or "").strip()
        if token:
            store.telegram_bot_token = token

    for key, value in data.items():
        setattr(store, key, value)

    await db.commit()
    await db.refresh(store)
    ac, pc, lc = await _store_counts(db, store.id)
    return _store_out(store, admins_count=ac, projects_count=pc, leads_count=lc)


@router.get("/stores/{store_id}/admins", response_model=list[PlatformStoreAdminOut])
async def list_store_admins(
    store_id: int,
    _: PlatformAdmin = Depends(get_current_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    admins = await db.scalars(
        select(StoreAdmin).where(StoreAdmin.store_id == store_id).order_by(StoreAdmin.email)
    )
    return list(admins.all())


@router.post("/stores/{store_id}/admins", response_model=PlatformStoreAdminOut)
async def create_store_admin(
    store_id: int,
    body: PlatformStoreAdminCreate,
    _: PlatformAdmin = Depends(get_current_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    email = body.email.lower()
    exists = await db.scalar(select(StoreAdmin).where(StoreAdmin.email == email))
    if exists:
        raise HTTPException(status_code=400, detail="Email already in use")

    try:
        role = AdminRole(body.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid role") from exc

    admin = StoreAdmin(
        store_id=store_id,
        email=email,
        password_hash=hash_password(body.password),
        role=role,
        active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


@router.put("/admins/{admin_id}", response_model=PlatformStoreAdminOut)
async def update_store_admin(
    admin_id: int,
    body: PlatformStoreAdminUpdate,
    _: PlatformAdmin = Depends(get_current_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    admin = await db.get(StoreAdmin, admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    data = body.model_dump(exclude_unset=True)
    if "email" in data and data["email"]:
        email = data["email"].lower()
        other = await db.scalar(
            select(StoreAdmin).where(StoreAdmin.email == email, StoreAdmin.id != admin_id)
        )
        if other:
            raise HTTPException(status_code=400, detail="Email already in use")
        admin.email = email
        data.pop("email", None)

    if "password" in data and data["password"]:
        admin.password_hash = hash_password(data.pop("password"))

    if "role" in data and data["role"]:
        try:
            admin.role = AdminRole(data["role"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid role") from exc
        data.pop("role", None)

    for key, value in data.items():
        setattr(admin, key, value)

    await db.commit()
    await db.refresh(admin)
    return admin


@router.delete("/admins/{admin_id}")
async def deactivate_store_admin(
    admin_id: int,
    _: PlatformAdmin = Depends(get_current_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    admin = await db.get(StoreAdmin, admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    admin.active = False
    await db.commit()
    return {"ok": True}


@router.get("/brands", response_model=list[BrandOut])
async def platform_list_brands(
    _: PlatformAdmin = Depends(get_current_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return await list_brands(db)


@router.get("/stores/{store_id}/colors", response_model=list[ColorOut])
async def platform_list_store_colors(
    store_id: int,
    brand_id: int | None = None,
    _: PlatformAdmin = Depends(get_current_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return await list_store_colors(db, store_id, brand_id)


@router.post("/stores/{store_id}/colors", response_model=ColorOut)
async def platform_add_store_color(
    store_id: int,
    body: ColorCreate,
    _: PlatformAdmin = Depends(get_current_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    try:
        return await add_color_to_store(db, store_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/stores/{store_id}/colors/{color_id}", response_model=ColorOut)
async def platform_update_store_color(
    store_id: int,
    color_id: int,
    body: ColorUpdate,
    _: PlatformAdmin = Depends(get_current_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    try:
        return await update_store_color(db, store_id, color_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/stores/{store_id}/colors/{color_id}/stock", response_model=ColorOut)
async def platform_set_color_stock(
    store_id: int,
    color_id: int,
    body: StockUpdate,
    _: PlatformAdmin = Depends(get_current_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    try:
        return await set_store_color_stock(db, store_id, color_id, body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/stores/{store_id}/colors/{color_id}")
async def platform_remove_store_color(
    store_id: int,
    color_id: int,
    _: PlatformAdmin = Depends(get_current_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    try:
        await remove_color_from_store(db, store_id, color_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}
