from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import asset_url, get_current_user
from app.database import get_db
from app.models import Brand, Color, ColorCategory, DecorativeColor, DecorativeMaterial, Project, Store, StoreColor, User
from app.schemas import (
    BrandOut,
    CatalogPromotionOut,
    ColorListResponse,
    ColorOut,
    DecorativeColorOut,
    DecorativeMaterialOut,
    PaintEstimateOut,
    StorePublicOut,
)
from app.services.brand_ops import brand_out
from app.services.color_codes import search_code_variants
from app.services.decor_estimate_db import estimate_decor_for_project
from app.services.paint_estimate_db import estimate_paint_for_project, estimate_to_dict
from app.services.store_brand_ops import brand_ids_for_store
from app.services.store_catalog import color_out, decor_color_out
from app.services.store_pack_prices import load_store_pack_price_overrides
from app.services.store_discounts import (
    load_store_discounts,
    promo_message,
    resolve_brand_discount_percent,
    resolve_decor_discount_percent,
    resolve_paint_discount_percent,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])


async def _project_for_user(db: AsyncSession, project_id: int, user: User) -> Project:
    project = await db.get(Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/store", response_model=StorePublicOut)
async def get_store_for_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _project_for_user(db, project_id, user)
    store = await db.get(Store, project.store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.get("/brands", response_model=list[BrandOut])
async def list_brands(
    project_id: int,
    finish: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _project_for_user(db, project_id, user)
    store_brand_ids = set(await brand_ids_for_store(db, project.store_id))
    brand_ids = await db.scalars(
        select(Color.brand_id)
        .join(StoreColor, StoreColor.color_id == Color.id)
        .where(
            StoreColor.store_id == project.store_id,
            StoreColor.active.is_(True),
            Color.active.is_(True),
        )
        .distinct()
    )
    ids = [bid for bid in brand_ids.all() if bid in store_brand_ids]
    if not ids:
        return []
    query = (
        select(Brand)
        .where(Brand.id.in_(ids), Brand.active.is_(True))
        .options(selectinload(Brand.pack_sizes))
    )
    if finish:
        from app.services.brand_ops import normalize_paint_finish

        query = query.where(Brand.paint_finish == normalize_paint_finish(finish))
    brands = await db.scalars(query.order_by(Brand.name))
    discounts = await load_store_discounts(db, project.store_id)
    pack_overrides = await load_store_pack_price_overrides(db, project.store_id)
    out: list[BrandOut] = []
    for b in brands.all():
        item = brand_out(b, pack_overrides)
        disc = resolve_brand_discount_percent(discounts, b.id)
        if disc:
            item = item.model_copy(update={"discount_percent": disc})
        out.append(item)
    return out


async def _promotion_target_label(
    db: AsyncSession,
    scope: str,
    target_id: int | None,
) -> str | None:
    if not target_id:
        return None
    if scope == "brand":
        brand = await db.get(Brand, target_id)
        return brand.name if brand else None
    if scope == "color":
        color = await db.get(Color, target_id)
        return color.name if color else None
    if scope == "material":
        material = await db.get(DecorativeMaterial, target_id)
        return material.name if material else None
    if scope == "decor_color":
        shade = await db.get(DecorativeColor, target_id)
        return shade.name if shade else None
    return None


@router.get("/promotions", response_model=list[CatalogPromotionOut])
async def list_catalog_promotions(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _project_for_user(db, project_id, user)
    discounts = await load_store_discounts(db, project.store_id)
    promotions: list[CatalogPromotionOut] = []
    for d in discounts:
        target_label = await _promotion_target_label(db, d.scope, d.target_id)
        promotions.append(
            CatalogPromotionOut(
                scope=d.scope,
                discount_percent=d.discount_percent,
                message=promo_message(d, target_label),
                target_label=target_label,
            )
        )
    return promotions


@router.get("/colors", response_model=ColorListResponse)
async def list_colors(
    project_id: int,
    brand_id: int | None = None,
    color_id: int | None = None,
    category: str | None = None,
    search: str | None = None,
    manufacturer_code: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _project_for_user(db, project_id, user)
    query = (
        select(StoreColor)
        .join(Color, Color.id == StoreColor.color_id)
        .where(
            StoreColor.store_id == project.store_id,
            StoreColor.active.is_(True),
            Color.active.is_(True),
        )
        .options(selectinload(StoreColor.color).selectinload(Color.brand))
    )
    if color_id:
        query = query.where(Color.id == color_id)
    if brand_id:
        query = query.where(Color.brand_id == brand_id)
    if category:
        try:
            cat = ColorCategory(category)
            query = query.where(Color.category == cat)
        except ValueError:
            pass
    if manufacturer_code:
        query = query.where(Color.manufacturer_code.ilike(f"%{manufacturer_code}%"))
    if search:
        terms = search_code_variants(search)
        clauses = []
        for term in terms:
            pattern = f"%{term}%"
            clauses.append(Color.name.ilike(pattern))
            clauses.append(Color.manufacturer_code.ilike(pattern))
        query = query.where(or_(*clauses))

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    listings = await db.scalars(
        query.order_by(Color.name).offset((page - 1) * page_size).limit(page_size)
    )
    discounts = await load_store_discounts(db, project.store_id)
    items = []
    for row in listings.all():
        if not row.color:
            continue
        disc = resolve_paint_discount_percent(discounts, row.color.id, row.color.brand_id)
        items.append(color_out(row.color, row, disc))
    return ColorListResponse(
        items=items,
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/categories")
async def list_categories(user: User = Depends(get_current_user)):
    return [c.value for c in ColorCategory]


@router.get("/materials", response_model=list[DecorativeMaterialOut])
async def list_materials(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _project_for_user(db, project_id, user)

    materials = await db.scalars(
        select(DecorativeMaterial)
        .where(DecorativeMaterial.store_id == project.store_id, DecorativeMaterial.active.is_(True))
        .order_by(DecorativeMaterial.name)
    )
    discounts = await load_store_discounts(db, project.store_id)
    return [
        DecorativeMaterialOut(
            id=m.id,
            store_id=m.store_id,
            name=m.name,
            brand_id=m.brand_id,
            category=m.category,
            texture_url=asset_url(m.texture_file),
            preview_url=asset_url(m.preview_image),
            texture_scale=m.texture_scale,
            in_stock=m.in_stock,
            active=m.active,
            discount_percent=resolve_decor_discount_percent(discounts, m.id),
        )
        for m in materials.all()
    ]


@router.get("/materials/{material_id}/colors", response_model=list[DecorativeColorOut])
async def list_material_colors(
    material_id: int,
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _project_for_user(db, project_id, user)
    material = await db.get(DecorativeMaterial, material_id)
    if not material or material.store_id != project.store_id:
        raise HTTPException(status_code=404, detail="Material not found")

    colors = await db.scalars(
        select(DecorativeColor)
        .where(DecorativeColor.material_id == material_id, DecorativeColor.active.is_(True))
        .order_by(DecorativeColor.name)
    )
    discounts = await load_store_discounts(db, project.store_id)
    return [
        decor_color_out(
            shade,
            resolve_decor_discount_percent(discounts, material_id, shade.id),
        )
        for shade in colors.all()
    ]


@router.get("/paint-estimate", response_model=PaintEstimateOut)
async def paint_estimate(
    project_id: int,
    color_id: int,
    wall_area_sqm: float = Query(..., gt=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _project_for_user(db, project_id, user)
    estimate = await estimate_paint_for_project(db, project, color_id, wall_area_sqm)
    if not estimate:
        raise HTTPException(
            status_code=400,
            detail="Не вдалося порахувати. Перевірте фасування бренду в адмінці.",
        )
    discounts = await load_store_discounts(db, project.store_id)
    color = await db.get(Color, color_id)
    disc = resolve_paint_discount_percent(discounts, color_id, color.brand_id) if color else None
    return PaintEstimateOut(**estimate_to_dict(estimate, disc))


@router.get("/decor-estimate", response_model=PaintEstimateOut)
async def decor_estimate(
    project_id: int,
    material_id: int,
    decor_color_id: int | None = None,
    wall_area_sqm: float = Query(..., gt=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _project_for_user(db, project_id, user)
    estimate = await estimate_decor_for_project(
        db, project, material_id, decor_color_id, wall_area_sqm
    )
    if not estimate:
        raise HTTPException(
            status_code=400,
            detail="Не вдалося порахувати. Додайте фасування матеріалу в адмінці.",
        )
    discounts = await load_store_discounts(db, project.store_id)
    disc = resolve_decor_discount_percent(discounts, material_id, decor_color_id)
    return PaintEstimateOut(**estimate_to_dict(estimate, disc))
