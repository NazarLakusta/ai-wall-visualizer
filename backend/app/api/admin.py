import csv
import io
import re
from datetime import datetime, time, timezone, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import asset_url, get_current_admin, require_store_owner
from app.config import settings
from app.database import get_db
from app.models import AdminRole, Brand, BrandPackSize, Color, ColorCategory, DecorativeColor, DecorativeMaterial, Lead, LeadStatus, Project, Store, StoreAdmin, StoreBroadcast, StoreColor, StoreDiscount, User
from app.services.store_brand_ops import get_store_brand, link_brand_to_store, list_brands_for_store
from app.services.material_ops import load_material_with_packs, material_pack_out, sync_material_pack_sizes
from app.schemas import (
    AdminProjectOut,
    AdminStatsOut,
    BrandCreate,
    BrandOut,
    BrandUpdate,
    BroadcastAudienceOut,
    BroadcastOut,
    ColorCreate,
    ColorOut,
    ColorUpdate,
    DecorativeColorCreate,
    DecorativeColorOut,
    DecorativeColorUpdate,
    DecorativeMaterialOut,
    ImportConfirmRequest,
    ImportPreviewResponse,
    ImportPreviewRow,
    LeadCustomerMessage,
    LeadOut,
    LeadStatusUpdate,
    MaterialCreate,
    MaterialUpdate,
    StockUpdate,
    StoreSettingsOut,
    StoreSettingsUpdate,
    StoreDiscountOut,
    StoreDiscountCreate,
    BulkPriceAdjustIn,
    BulkPriceAdjustOut,
)
from app.services.pricing import calc_total_price
from app.services.selection import build_selection_summary, get_active_price_per_sqm
from app.services.file_validation import validate_image_upload, validate_texture_upload
from app.services.lead_notify import (
    notify_lead_customer_contacted,
    notify_lead_customer_text,
    notify_lead_to_crew,
    send_lead_quote_to_customer,
    send_test_notifications,
)
from app.services.storage import StorageService
from app.services.brand_ops import brand_out, default_surcharge_for_base, load_brand_with_packs, normalize_paint_finish, normalize_tint_base, paint_finish_label, sync_brand_pack_sizes
from app.services.store_catalog import color_out
from app.services.store_pack_prices import load_store_pack_price_overrides, sync_store_brand_pack_prices
from app.services.store_discounts import (
    VALID_DISCOUNT_SCOPES,
    load_store_discounts,
    resolve_paint_discount_percent,
    scope_requires_target,
)
from app.services.pricing_bulk import bulk_adjust_prices
from app.services.date_filter import parse_filter_date_end_exclusive, parse_filter_date_start
from app.services.quote_pdf import build_lead_quote_pdf
from app.services.queue_monitor import queue_snapshot
from app.workers.tasks import send_store_broadcast

router = APIRouter(prefix="/admin", tags=["admin"])

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _funnel_rate(part: int, whole: int) -> float | None:
    if whole <= 0:
        return None
    return round(100.0 * part / whole, 1)


def _in_period(created_at: datetime | None, cutoff: datetime | None) -> bool:
    if cutoff is None or created_at is None:
        return True
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at >= cutoff


def _store_settings_out(store: Store) -> StoreSettingsOut:
    token = (store.telegram_bot_token or "").strip()
    hint = f"…{token[-6:]}" if len(token) > 6 else None
    return StoreSettingsOut(
        id=store.id,
        name=store.name,
        slug=store.slug,
        phone=store.phone,
        address=store.address,
        telegram_username=store.telegram_username,
        manager_telegram_chat_id=store.manager_telegram_chat_id,
        leads_group_chat_id=store.leads_group_chat_id,
        crew_telegram_chat_id=store.crew_telegram_chat_id,
        business_open_time=store.business_open_time or "09:00",
        business_close_time=store.business_close_time or "19:00",
        business_timezone=store.business_timezone or "Europe/Kyiv",
        has_bot_token=bool(token),
        bot_token_hint=hint,
    )


async def _get_store_color_row(
    db: AsyncSession,
    store_id: int,
    color_id: int,
) -> tuple[Color, StoreColor] | None:
    listing = await db.scalar(
        select(StoreColor)
        .where(StoreColor.store_id == store_id, StoreColor.color_id == color_id)
        .options(selectinload(StoreColor.color))
    )
    if not listing or not listing.color:
        return None
    return listing.color, listing


def _parse_import_file(content: bytes, filename: str) -> pd.DataFrame:
    if filename.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(content))
    if filename.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(content))
    raise HTTPException(status_code=400, detail="Unsupported file format")


def _material_out(material: DecorativeMaterial) -> DecorativeMaterialOut:
    packs = sorted(material.pack_sizes, key=lambda p: (p.sort_order, p.coverage_sqm))
    return DecorativeMaterialOut(
        id=material.id,
        store_id=material.store_id,
        name=material.name,
        brand_id=material.brand_id,
        category=material.category,
        texture_url=asset_url(material.texture_file),
        preview_url=asset_url(material.preview_image),
        texture_scale=material.texture_scale,
        recommended_coats=material.recommended_coats or 1,
        in_stock=material.in_stock,
        active=material.active,
        pack_sizes=[material_pack_out(p) for p in packs if p.active],
    )


@router.get("/brands", response_model=list[BrandOut])
async def admin_list_brands(
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    brands = await list_brands_for_store(db, admin.store_id)
    pack_overrides = await load_store_pack_price_overrides(db, admin.store_id)
    return [brand_out(b, pack_overrides) for b in brands]


@router.post("/brands", response_model=BrandOut)
async def admin_create_brand(
    body: BrandCreate,
    admin: StoreAdmin = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    data = body.model_dump(exclude={"pack_sizes"})
    if "paint_finish" in data:
        data["paint_finish"] = normalize_paint_finish(data["paint_finish"])
    brand = Brand(**data)
    db.add(brand)
    await db.flush()
    await link_brand_to_store(db, admin.store_id, brand.id)
    await sync_brand_pack_sizes(db, brand, body.pack_sizes)
    await sync_store_brand_pack_prices(db, admin.store_id, brand, body.pack_sizes)
    await db.commit()
    brand = await load_brand_with_packs(db, brand.id)
    pack_overrides = await load_store_pack_price_overrides(db, admin.store_id)
    return brand_out(brand, pack_overrides)


@router.put("/brands/{brand_id}", response_model=BrandOut)
async def admin_update_brand(
    brand_id: int,
    body: BrandUpdate,
    admin: StoreAdmin = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    brand = await load_brand_with_packs(db, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    if not await get_store_brand(db, admin.store_id, brand_id):
        raise HTTPException(status_code=404, detail="Brand not found")
    data = body.model_dump(exclude_unset=True, exclude={"pack_sizes"})
    if "paint_finish" in data and data["paint_finish"] is not None:
        data["paint_finish"] = normalize_paint_finish(data["paint_finish"])
    for k, v in data.items():
        setattr(brand, k, v)
    if body.pack_sizes is not None:
        await sync_brand_pack_sizes(db, brand, body.pack_sizes)
        await sync_store_brand_pack_prices(db, admin.store_id, brand, body.pack_sizes)
    await db.commit()
    brand = await load_brand_with_packs(db, brand_id)
    pack_overrides = await load_store_pack_price_overrides(db, admin.store_id)
    return brand_out(brand, pack_overrides)


@router.delete("/brands/{brand_id}")
async def admin_delete_brand(
    brand_id: int,
    admin: StoreAdmin = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    link = await get_store_brand(db, admin.store_id, brand_id)
    if not link:
        raise HTTPException(status_code=404, detail="Brand not found")
    link.active = False
    await db.commit()
    return {"ok": True}


@router.get("/colors", response_model=list[ColorOut])
async def admin_list_colors(
    brand_id: int | None = None,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(StoreColor)
        .join(Color, Color.id == StoreColor.color_id)
        .where(
            StoreColor.store_id == admin.store_id,
            StoreColor.active.is_(True),
            Color.active.is_(True),
        )
        .options(selectinload(StoreColor.color))
    )
    if brand_id:
        query = query.where(Color.brand_id == brand_id)
    listings = await db.scalars(query.order_by(Color.name))
    discounts = await load_store_discounts(db, admin.store_id)
    return [
        color_out(
            row.color,
            row,
            resolve_paint_discount_percent(discounts, row.color.id, row.color.brand_id),
        )
        for row in listings.all()
        if row.color
    ]


@router.patch("/colors/{color_id}/stock", response_model=ColorOut)
async def admin_set_color_stock(
    color_id: int,
    body: StockUpdate,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    pair = await _get_store_color_row(db, admin.store_id, color_id)
    if not pair:
        raise HTTPException(status_code=404, detail="Color not in store catalog")
    color, listing = pair
    listing.in_stock = body.in_stock
    await db.commit()
    await db.refresh(listing)
    return color_out(color, listing)


@router.post("/colors", response_model=ColorOut)
async def admin_create_color(
    body: ColorCreate,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        category = ColorCategory(body.category)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid category") from exc

    if not await get_store_brand(db, admin.store_id, body.brand_id):
        raise HTTPException(status_code=404, detail="Brand not in store catalog")

    existing = await db.scalar(
        select(Color).where(
            Color.brand_id == body.brand_id,
            Color.name == body.name,
            Color.hex == body.hex,
        )
    )
    if existing:
        color = existing
    else:
        color = Color(
            brand_id=body.brand_id,
            name=body.name,
            hex=body.hex,
            manufacturer_code=body.manufacturer_code,
            category=category,
            tint_base=normalize_tint_base(body.tint_base),
            base_surcharge_percent=default_surcharge_for_base(
                normalize_tint_base(body.tint_base), body.base_surcharge_percent
            ),
            active=True,
        )
        db.add(color)
        await db.flush()

    listing = await db.scalar(
        select(StoreColor).where(
            StoreColor.store_id == admin.store_id,
            StoreColor.color_id == color.id,
        )
    )
    if listing:
        listing.active = True
        if body.price_per_sqm is not None:
            listing.price_per_sqm = body.price_per_sqm
    else:
        listing = StoreColor(
            store_id=admin.store_id,
            color_id=color.id,
            price_per_sqm=body.price_per_sqm,
            in_stock=True,
            active=True,
        )
        db.add(listing)

    await db.commit()
    await db.refresh(listing)
    await db.refresh(color)
    return color_out(color, listing)


@router.put("/colors/{color_id}", response_model=ColorOut)
async def admin_update_color(
    color_id: int,
    body: ColorUpdate,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    pair = await _get_store_color_row(db, admin.store_id, color_id)
    if not pair:
        raise HTTPException(status_code=404, detail="Color not in store catalog")
    color, listing = pair

    data = body.model_dump(exclude_unset=True)
    store_fields = {"price_per_sqm", "in_stock", "active"}
    for key in list(data.keys()):
        if key in store_fields:
            setattr(listing, key, data.pop(key))
    if "category" in data and data["category"]:
        data["category"] = ColorCategory(data["category"])
    for k, v in data.items():
        setattr(color, k, v)

    await db.commit()
    await db.refresh(color)
    await db.refresh(listing)
    return color_out(color, listing)


@router.delete("/colors/{color_id}")
async def admin_delete_color(
    color_id: int,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    pair = await _get_store_color_row(db, admin.store_id, color_id)
    if not pair:
        raise HTTPException(status_code=404, detail="Color not in store catalog")
    _, listing = pair
    listing.active = False
    await db.commit()
    return {"ok": True}


@router.post("/import/colors/preview", response_model=ImportPreviewResponse)
async def import_colors_preview(
    file: UploadFile = File(...),
    admin: StoreAdmin = Depends(get_current_admin),
):
    content = await file.read()
    df = _parse_import_file(content, file.filename or "import.csv")
    required = {"name", "hex", "category", "brand_name"}
    if not required.issubset(set(c.lower() for c in df.columns)):
        raise HTTPException(status_code=400, detail=f"Required columns: {required}")

    col_map = {c.lower(): c for c in df.columns}
    rows: list[ImportPreviewRow] = []
    for _, row in df.iterrows():
        name = str(row[col_map["name"]]).strip()
        hex_val = str(row[col_map["hex"]]).strip()
        if not hex_val.startswith("#"):
            hex_val = f"#{hex_val}"
        category = str(row[col_map["category"]]).strip()
        brand_name = str(row[col_map["brand_name"]]).strip()
        mfg = str(row[col_map.get("manufacturer_code", "manufacturer_code")]).strip() if "manufacturer_code" in col_map else None
        if mfg == "nan":
            mfg = None
        error = None
        valid = True
        if not HEX_RE.match(hex_val):
            valid = False
            error = "Invalid HEX"
        try:
            ColorCategory(category)
        except ValueError:
            valid = False
            error = (error + "; " if error else "") + "Invalid category"
        rows.append(ImportPreviewRow(
            name=name, hex=hex_val, manufacturer_code=mfg,
            category=category, brand_name=brand_name, valid=valid, error=error,
        ))
    valid_count = sum(1 for r in rows if r.valid)
    return ImportPreviewResponse(rows=rows, valid_count=valid_count, invalid_count=len(rows) - valid_count)


@router.post("/import/colors/confirm")
async def import_colors_confirm(
    body: ImportConfirmRequest,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    brand = await db.get(Brand, body.brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    if not await get_store_brand(db, admin.store_id, body.brand_id):
        raise HTTPException(status_code=404, detail="Brand not in store catalog")
    created = 0
    for row in body.rows:
        if not row.valid:
            continue
        existing = await db.scalar(
            select(Color).where(
                Color.brand_id == body.brand_id,
                Color.name == row.name,
                Color.hex == row.hex,
            )
        )
        if existing:
            color = existing
        else:
            color = Color(
                brand_id=body.brand_id,
                name=row.name,
                hex=row.hex,
                manufacturer_code=row.manufacturer_code,
                category=ColorCategory(row.category),
                active=True,
            )
            db.add(color)
            await db.flush()

        listing = await db.scalar(
            select(StoreColor).where(
                StoreColor.store_id == admin.store_id,
                StoreColor.color_id == color.id,
            )
        )
        if listing:
            listing.active = True
        else:
            db.add(StoreColor(store_id=admin.store_id, color_id=color.id, active=True))
        created += 1
    await db.commit()
    return {"created": created}


@router.get("/materials", response_model=list[DecorativeMaterialOut])
async def admin_list_materials(
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.orm import selectinload

    materials = await db.scalars(
        select(DecorativeMaterial)
        .where(DecorativeMaterial.store_id == admin.store_id)
        .options(selectinload(DecorativeMaterial.pack_sizes))
        .order_by(DecorativeMaterial.name)
    )
    return [_material_out(m) for m in materials.all()]


@router.post("/materials", response_model=DecorativeMaterialOut)
async def admin_create_material(
    body: MaterialCreate,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    data = body.model_dump(exclude={"pack_sizes"})
    material = DecorativeMaterial(store_id=admin.store_id, **data)
    db.add(material)
    await db.flush()
    await sync_material_pack_sizes(db, material, body.pack_sizes)
    await db.commit()
    material = await load_material_with_packs(db, material.id)
    return _material_out(material)


@router.put("/materials/{material_id}", response_model=DecorativeMaterialOut)
async def admin_update_material(
    material_id: int,
    body: MaterialUpdate,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    material = await load_material_with_packs(db, material_id)
    if not material or material.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Material not found")
    data = body.model_dump(exclude_unset=True, exclude={"pack_sizes"})
    for k, v in data.items():
        setattr(material, k, v)
    if body.pack_sizes is not None:
        await sync_material_pack_sizes(db, material, body.pack_sizes)
    await db.commit()
    material = await load_material_with_packs(db, material_id)
    return _material_out(material)


@router.delete("/materials/{material_id}")
async def admin_delete_material(
    material_id: int,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(DecorativeMaterial, material_id)
    if not material or material.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Material not found")
    material.active = False
    await db.commit()
    return {"ok": True}


@router.patch("/materials/{material_id}/stock", response_model=DecorativeMaterialOut)
async def admin_set_material_stock(
    material_id: int,
    body: StockUpdate,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(DecorativeMaterial, material_id)
    if not material or material.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Material not found")
    material.in_stock = body.in_stock
    await db.commit()
    material = await load_material_with_packs(db, material_id)
    return _material_out(material)


@router.post("/materials/{material_id}/texture")
async def upload_texture(
    material_id: int,
    file: UploadFile = File(...),
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(DecorativeMaterial, material_id)
    if not material or material.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Material not found")
    data = await file.read()
    try:
        validate_texture_upload(data, settings.max_upload_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    storage = StorageService()
    fname = storage.unique_filename(file.filename or "texture.jpg")
    path = storage.texture_dir(admin.store_id) / fname
    path.write_bytes(data)
    material.texture_file = str(path.relative_to(storage.base))
    await db.commit()
    return {"texture_url": asset_url(material.texture_file)}


@router.get("/materials/{material_id}/colors", response_model=list[DecorativeColorOut])
async def admin_list_material_colors(
    material_id: int,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(DecorativeMaterial, material_id)
    if not material or material.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Material not found")
    colors = await db.scalars(select(DecorativeColor).where(DecorativeColor.material_id == material_id))
    return list(colors.all())


@router.post("/materials/{material_id}/colors", response_model=DecorativeColorOut)
async def admin_create_material_color(
    material_id: int,
    body: DecorativeColorCreate,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(DecorativeMaterial, material_id)
    if not material or material.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Material not found")
    color = DecorativeColor(material_id=material_id, **body.model_dump())
    db.add(color)
    await db.commit()
    await db.refresh(color)
    return color


@router.put("/materials/{material_id}/colors/{color_id}", response_model=DecorativeColorOut)
async def admin_update_material_color(
    material_id: int,
    color_id: int,
    body: DecorativeColorUpdate,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(DecorativeMaterial, material_id)
    if not material or material.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Material not found")
    color = await db.get(DecorativeColor, color_id)
    if not color or color.material_id != material_id:
        raise HTTPException(status_code=404, detail="Color not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(color, key, value)
    await db.commit()
    await db.refresh(color)
    return DecorativeColorOut.model_validate(color)


@router.delete("/materials/{material_id}/colors/{color_id}")
async def admin_delete_material_color(
    material_id: int,
    color_id: int,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(DecorativeMaterial, material_id)
    if not material or material.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Material not found")
    color = await db.get(DecorativeColor, color_id)
    if not color or color.material_id != material_id:
        raise HTTPException(status_code=404, detail="Color not found")
    color.active = False
    await db.commit()
    return {"ok": True}


@router.patch("/materials/{material_id}/colors/{color_id}/stock", response_model=DecorativeColorOut)
async def admin_set_decor_color_stock(
    material_id: int,
    color_id: int,
    body: StockUpdate,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(DecorativeMaterial, material_id)
    if not material or material.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Material not found")
    color = await db.get(DecorativeColor, color_id)
    if not color or color.material_id != material_id:
        raise HTTPException(status_code=404, detail="Color not found")
    color.in_stock = body.in_stock
    await db.commit()
    await db.refresh(color)
    return DecorativeColorOut.model_validate(color)


@router.get("/store", response_model=StoreSettingsOut)
async def get_store_settings(
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    store = await db.get(Store, admin.store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return _store_settings_out(store)


@router.put("/store", response_model=StoreSettingsOut)
async def update_store_settings(
    body: StoreSettingsUpdate,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    store = await db.get(Store, admin.store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    data = body.model_dump(exclude_unset=True)
    if admin.role != AdminRole.OWNER and "telegram_bot_token" in data:
        raise HTTPException(status_code=403, detail="Only owner can change bot token")
    for key, value in data.items():
        if key == "telegram_bot_token":
            if value and str(value).strip():
                store.telegram_bot_token = str(value).strip()
            continue
        setattr(store, key, value)
    await db.commit()
    await db.refresh(store)
    return _store_settings_out(store)


@router.post("/store/test-notification")
async def test_store_notification(
    admin: StoreAdmin = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    store = await db.get(Store, admin.store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    ok, err = await send_test_notifications(store)
    if not ok:
        raise HTTPException(status_code=502, detail=err)
    return {"ok": True}


@router.get("/ops/queue")
async def admin_queue_status(
    admin: StoreAdmin = Depends(require_store_owner),
):
    snap = queue_snapshot()
    return {"ok": True, **snap}


@router.get("/stats", response_model=AdminStatsOut)
async def get_stats(
    days: int = Query(default=30, ge=0, le=365),
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    store_id = admin.store_id
    cutoff: datetime | None = None
    period_days: int | None = days if days > 0 else None
    if days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    projects = await db.scalars(select(Project).where(Project.store_id == store_id))
    project_list = [p for p in projects.all() if _in_period(p.created_at, cutoff)]
    leads = await db.scalars(select(Lead).where(Lead.store_id == store_id))
    lead_list = [lead for lead in leads.all() if _in_period(lead.created_at, cutoff)]

    real_projects = [p for p in project_list if not p.is_test]
    funnel_uploads = len(real_projects)
    funnel_editor = sum(1 for p in real_projects if (p.editor_opens or 0) >= 1)
    funnel_leads = len(lead_list)
    funnel_contacted = sum(
        1 for lead in lead_list if lead.status in (LeadStatus.CONTACTED, LeadStatus.CLOSED)
    )
    funnel_closed = sum(1 for lead in lead_list if lead.status == LeadStatus.CLOSED)

    return AdminStatsOut(
        period_days=period_days,
        projects_total=len(project_list),
        projects_real=len(real_projects),
        projects_test=sum(1 for p in project_list if p.is_test),
        editor_opens=sum(p.editor_opens or 0 for p in project_list),
        leads_total=funnel_leads,
        leads_new=sum(1 for lead in lead_list if lead.status == LeadStatus.NEW),
        downloads_estimate=sum(1 for p in project_list if p.result_image),
        funnel_uploads=funnel_uploads,
        funnel_editor=funnel_editor,
        funnel_leads=funnel_leads,
        funnel_contacted=funnel_contacted,
        funnel_closed=funnel_closed,
        funnel_rate_upload_to_editor=_funnel_rate(funnel_editor, funnel_uploads),
        funnel_rate_editor_to_lead=_funnel_rate(funnel_leads, funnel_editor),
        funnel_rate_lead_to_contacted=_funnel_rate(funnel_contacted, funnel_leads),
        funnel_rate_contacted_to_closed=_funnel_rate(funnel_closed, funnel_contacted),
    )


@router.get("/projects", response_model=list[AdminProjectOut])
async def list_store_projects(
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    projects = await db.scalars(
        select(Project)
        .where(Project.store_id == admin.store_id)
        .order_by(Project.created_at.desc())
        .limit(100)
    )
    out: list[AdminProjectOut] = []
    for project in projects.all():
        user = await db.get(User, project.user_id)
        summary = await build_selection_summary(db, project)
        price = await get_active_price_per_sqm(db, project)
        total = calc_total_price(price, project.wall_area_sqm)
        out.append(
            AdminProjectOut(
                id=project.id,
                status=project.status.value,
                is_test=project.is_test,
                wall_area_sqm=project.wall_area_sqm,
                selection_summary=summary,
                estimated_total_uah=total,
                editor_opens=project.editor_opens or 0,
                user_name=user.first_name if user else None,
                user_phone_hint=f"@{user.username}" if user and user.username else None,
                original_url=asset_url(project.original_image),
                result_url=asset_url(project.result_image),
                created_at=project.created_at,
            )
        )
    return out


def _lead_out(lead: Lead, project: Project | None = None, user: User | None = None) -> LeadOut:
    if user is None and hasattr(lead, "user") and lead.user is not None:
        user = lead.user
    return LeadOut(
        id=lead.id,
        project_id=lead.project_id,
        phone=lead.phone,
        customer_name=lead.customer_name,
        telegram_username=user.username if user else None,
        comment=lead.comment,
        wall_area_sqm=lead.wall_area_sqm,
        estimated_total_uah=lead.estimated_total_uah,
        selection_summary=lead.selection_summary,
        paint_plan_summary=lead.paint_plan_summary,
        original_url=asset_url(project.original_image) if project else None,
        result_url=asset_url(project.result_image) if project else None,
        is_test=bool(project.is_test) if project else False,
        status=lead.status.value if hasattr(lead.status, "value") else str(lead.status),
        created_at=lead.created_at,
    )


@router.get("/leads", response_model=list[LeadOut])
async def list_leads(
    status: str | None = None,
    sort: str = Query(default="date_desc"),
    date_from: str | None = None,
    date_to: str | None = None,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(Lead).where(Lead.store_id == admin.store_id).options(selectinload(Lead.user))
    if status:
        try:
            query = query.where(Lead.status == LeadStatus(status))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid status") from exc
    if date_from:
        try:
            query = query.where(Lead.created_at >= parse_filter_date_start(date_from))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid date_from") from exc
    if date_to:
        try:
            query = query.where(Lead.created_at < parse_filter_date_end_exclusive(date_to))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid date_to") from exc

    if sort == "date_asc":
        query = query.order_by(Lead.created_at.asc())
    elif sort == "amount_desc":
        query = query.order_by(Lead.estimated_total_uah.desc().nulls_last(), Lead.created_at.desc())
    elif sort == "amount_asc":
        query = query.order_by(Lead.estimated_total_uah.asc().nulls_last(), Lead.created_at.desc())
    else:
        query = query.order_by(Lead.created_at.desc())

    leads = await db.scalars(query.limit(200))
    lead_rows = list(leads.all())
    if not lead_rows:
        return []

    project_ids = {lead.project_id for lead in lead_rows}
    projects = await db.scalars(select(Project).where(Project.id.in_(project_ids)))
    projects_by_id = {p.id: p for p in projects.all()}

    out: list[LeadOut] = []
    for lead in lead_rows:
        project = projects_by_id.get(lead.project_id)
        out.append(_lead_out(lead, project, lead.user))
    return out


@router.patch("/leads/{lead_id}", response_model=LeadOut)
async def update_lead_status(
    lead_id: int,
    body: LeadStatusUpdate,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    lead = await db.get(Lead, lead_id)
    if not lead or lead.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Lead not found")
    prev_status = lead.status
    try:
        lead.status = LeadStatus(body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid status") from exc
    await db.commit()
    await db.refresh(lead)
    project = await db.get(Project, lead.project_id)
    user = await db.get(User, lead.user_id)
    store = await db.get(Store, admin.store_id)

    if (
        store
        and project
        and lead.status == LeadStatus.CONTACTED
        and prev_status != LeadStatus.CONTACTED
    ):
        await notify_lead_customer_contacted(store, lead, project, user)

    return _lead_out(lead, project, user)


@router.get("/leads/{lead_id}/quote")
async def download_lead_quote(
    lead_id: int,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    lead = await db.get(Lead, lead_id)
    if not lead or lead.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Lead not found")
    store = await db.get(Store, admin.store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    user = await db.get(User, lead.user_id)
    try:
        pdf_bytes = build_lead_quote_pdf(store, lead, user.username if user else None)
    except (FileNotFoundError, ImportError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    filename = f"koshtorys-lead-{lead_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/leads/{lead_id}/forward-crew")
async def forward_lead_to_crew(
    lead_id: int,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    lead = await db.get(Lead, lead_id)
    if not lead or lead.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Lead not found")
    store = await db.get(Store, admin.store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    project = await db.get(Project, lead.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    ok, err = await notify_lead_to_crew(store, lead, project)
    if not ok:
        raise HTTPException(status_code=502, detail=err or "Не вдалося надіслати бригаді")
    return {"ok": True, "message": "Заявку надіслано бригаді в Telegram"}


@router.post("/leads/{lead_id}/notify-customer")
async def notify_customer_about_lead(
    lead_id: int,
    body: LeadCustomerMessage,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    lead = await db.get(Lead, lead_id)
    if not lead or lead.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Lead not found")
    store = await db.get(Store, admin.store_id)
    project = await db.get(Project, lead.project_id)
    user = await db.get(User, lead.user_id)
    if not store or not project:
        raise HTTPException(status_code=404, detail="Store or project not found")
    ok = await notify_lead_customer_text(store, lead, project, user, body.message)
    if not ok:
        raise HTTPException(
            status_code=502,
            detail="Не вдалося надіслати клієнту. Переконайтесь, що він писав боту /start.",
        )
    return {"ok": True}


@router.post("/leads/{lead_id}/send-quote-customer")
async def send_quote_pdf_to_customer(
    lead_id: int,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    lead = await db.get(Lead, lead_id)
    if not lead or lead.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Lead not found")
    store = await db.get(Store, admin.store_id)
    project = await db.get(Project, lead.project_id)
    user = await db.get(User, lead.user_id)
    if not store or not project:
        raise HTTPException(status_code=404, detail="Store or project not found")
    try:
        pdf_bytes = build_lead_quote_pdf(store, lead, user.username if user else None)
    except (FileNotFoundError, ImportError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    ok = await send_lead_quote_to_customer(store, lead, project, user, pdf_bytes)
    if not ok:
        raise HTTPException(
            status_code=502,
            detail="Не вдалося надіслати PDF клієнту в Telegram.",
        )
    return {"ok": True, "message": "PDF надіслано клієнту в Telegram"}


@router.post("/leads/{lead_id}/notify-contacted")
async def notify_customer_contacted(
    lead_id: int,
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    lead = await db.get(Lead, lead_id)
    if not lead or lead.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Lead not found")
    store = await db.get(Store, admin.store_id)
    project = await db.get(Project, lead.project_id)
    user = await db.get(User, lead.user_id)
    if not store or not project:
        raise HTTPException(status_code=404, detail="Store not found")
    ok = await notify_lead_customer_contacted(store, lead, project, user)
    if not ok:
        raise HTTPException(status_code=502, detail="Не вдалося надіслати повідомлення клієнту")
    if lead.status == LeadStatus.NEW:
        lead.status = LeadStatus.CONTACTED
        await db.commit()
    return {"ok": True}


def _resolve_export_dates(
    date_from: str | None,
    date_to: str | None,
    legacy_from: str | None,
    legacy_to: str | None,
) -> tuple[str | None, str | None]:
    return date_from or legacy_from, date_to or legacy_to


@router.get("/leads/export")
async def export_leads_csv(
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    date_from, date_to = _resolve_export_dates(date_from, date_to, from_date, to_date)
    query = select(Lead).where(Lead.store_id == admin.store_id)
    if status:
        try:
            query = query.where(Lead.status == LeadStatus(status))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid status") from exc
    if date_from:
        try:
            query = query.where(Lead.created_at >= parse_filter_date_start(date_from))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid date_from") from exc
    if date_to:
        try:
            query = query.where(Lead.created_at < parse_filter_date_end_exclusive(date_to))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid date_to") from exc

    query = query.order_by(Lead.created_at.desc())
    leads = await db.scalars(query.limit(5000))
    lead_rows = list(leads.all())

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([
        "id",
        "created_at",
        "status",
        "customer_name",
        "phone",
        "project_id",
        "wall_area_sqm",
        "estimated_total_uah",
        "selection_summary",
        "paint_plan_summary",
        "comment",
    ])
    for lead in lead_rows:
        writer.writerow([
            lead.id,
            lead.created_at.isoformat() if lead.created_at else "",
            lead.status.value if hasattr(lead.status, "value") else lead.status,
            lead.customer_name or "",
            lead.phone,
            lead.project_id,
            lead.wall_area_sqm if lead.wall_area_sqm is not None else "",
            lead.estimated_total_uah if lead.estimated_total_uah is not None else "",
            lead.selection_summary or "",
            (lead.paint_plan_summary or "").replace("\n", " | "),
            lead.comment or "",
        ])

    filename = f"leads-store-{admin.store_id}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _broadcast_out(broadcast: StoreBroadcast) -> BroadcastOut:
    return BroadcastOut(
        id=broadcast.id,
        title=broadcast.title,
        body=broadcast.body,
        image_url=asset_url(broadcast.image_path),
        status=broadcast.status,
        total_recipients=broadcast.total_recipients,
        sent_count=broadcast.sent_count,
        failed_count=broadcast.failed_count,
        error_message=broadcast.error_message,
        created_at=broadcast.created_at,
        started_at=broadcast.started_at,
        finished_at=broadcast.finished_at,
    )


@router.get("/broadcasts/audience", response_model=BroadcastAudienceOut)
async def get_broadcast_audience(
    admin: StoreAdmin = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    project_user_ids = await db.scalars(
        select(Project.user_id).where(Project.store_id == admin.store_id).distinct()
    )
    lead_user_ids = await db.scalars(
        select(Lead.user_id).where(Lead.store_id == admin.store_id).distinct()
    )
    user_ids = set(project_user_ids.all()) | set(lead_user_ids.all())
    if not user_ids:
        return BroadcastAudienceOut(count=0)
    telegram_ids = await db.scalars(
        select(User.telegram_id).where(User.id.in_(user_ids)).distinct()
    )
    count = sum(1 for tg_id in telegram_ids.all() if tg_id)
    return BroadcastAudienceOut(count=count)


@router.get("/broadcasts", response_model=list[BroadcastOut])
async def list_broadcasts(
    admin: StoreAdmin = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(StoreBroadcast)
        .where(StoreBroadcast.store_id == admin.store_id)
        .order_by(StoreBroadcast.created_at.desc())
        .limit(50)
    )
    return [_broadcast_out(row) for row in rows.all()]


@router.post("/broadcasts", response_model=BroadcastOut)
async def create_broadcast(
    title: str = Form(..., min_length=1, max_length=255),
    body: str = Form(..., min_length=1),
    image: UploadFile | None = File(default=None),
    admin: StoreAdmin = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    store = await db.get(Store, admin.store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    if not (store.telegram_bot_token or "").strip():
        raise HTTPException(status_code=400, detail="Спочатку вкажіть токен Telegram-бота магазину")

    broadcast = StoreBroadcast(
        store_id=admin.store_id,
        created_by_admin_id=admin.id,
        title=title.strip(),
        body=body.strip(),
    )
    db.add(broadcast)
    await db.flush()

    if image and image.filename:
        data = await image.read()
        try:
            validate_image_upload(data, settings.max_upload_bytes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        storage = StorageService()
        broadcast.image_path = storage.save_broadcast_image(
            admin.store_id,
            broadcast.id,
            image.filename or "broadcast.jpg",
            data,
        )

    await db.commit()
    await db.refresh(broadcast)
    send_store_broadcast.delay(broadcast.id)
    return _broadcast_out(broadcast)


async def _discount_target_label(
    db: AsyncSession,
    scope: str,
    target_id: int | None,
) -> str | None:
    if not target_id:
        return None
    if scope == "brand":
        brand = await db.get(Brand, target_id)
        return brand.name if brand else f"#{target_id}"
    if scope == "color":
        color = await db.get(Color, target_id)
        return color.name if color else f"#{target_id}"
    if scope == "material":
        material = await db.get(DecorativeMaterial, target_id)
        return material.name if material else f"#{target_id}"
    if scope == "decor_color":
        shade = await db.get(DecorativeColor, target_id)
        return shade.name if shade else f"#{target_id}"
    return f"#{target_id}"


def _discount_out(discount: StoreDiscount, target_label: str | None) -> StoreDiscountOut:
    return StoreDiscountOut(
        id=discount.id,
        scope=discount.scope,
        target_id=discount.target_id,
        target_label=target_label,
        discount_percent=discount.discount_percent,
        label=discount.label,
        active=discount.active,
        created_at=discount.created_at,
    )


SCOPE_LABELS = {
    "all": "Весь каталог",
    "paint": "Уся фарба",
    "decor": "Уся декоративка",
    "brand": "Бренд",
    "color": "Колір фарби",
    "material": "Декор-матеріал",
    "decor_color": "Відтінок декору",
}


@router.get("/discounts", response_model=list[StoreDiscountOut])
async def list_discounts(
    admin: StoreAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(StoreDiscount)
        .where(StoreDiscount.store_id == admin.store_id)
        .order_by(StoreDiscount.created_at.desc())
    )
    out: list[StoreDiscountOut] = []
    for row in rows.all():
        label = await _discount_target_label(db, row.scope, row.target_id)
        out.append(_discount_out(row, label))
    return out


@router.post("/discounts", response_model=StoreDiscountOut)
async def create_discount(
    body: StoreDiscountCreate,
    admin: StoreAdmin = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    scope = body.scope.strip().lower()
    if scope not in VALID_DISCOUNT_SCOPES:
        raise HTTPException(status_code=400, detail="Invalid scope")
    if scope_requires_target(scope) and not body.target_id:
        raise HTTPException(status_code=400, detail="target_id required for this scope")
    if not scope_requires_target(scope) and body.target_id:
        raise HTTPException(status_code=400, detail="target_id must be empty for this scope")

    if scope == "brand":
        if not await get_store_brand(db, admin.store_id, body.target_id):
            raise HTTPException(status_code=404, detail="Brand not in store catalog")
    elif scope == "color":
        pair = await _get_store_color_row(db, admin.store_id, body.target_id)
        if not pair:
            raise HTTPException(status_code=404, detail="Color not in store catalog")
    elif scope == "material":
        material = await db.get(DecorativeMaterial, body.target_id)
        if not material or material.store_id != admin.store_id:
            raise HTTPException(status_code=404, detail="Material not found")
    elif scope == "decor_color":
        shade = await db.get(DecorativeColor, body.target_id)
        if not shade:
            raise HTTPException(status_code=404, detail="Decor color not found")
        material = await db.get(DecorativeMaterial, shade.material_id)
        if not material or material.store_id != admin.store_id:
            raise HTTPException(status_code=404, detail="Decor color not in store")

    discount = StoreDiscount(
        store_id=admin.store_id,
        scope=scope,
        target_id=body.target_id,
        discount_percent=body.discount_percent,
        label=body.label,
        active=True,
    )
    db.add(discount)
    await db.commit()
    await db.refresh(discount)
    target_label = await _discount_target_label(db, discount.scope, discount.target_id)
    return _discount_out(discount, target_label)


@router.delete("/discounts/{discount_id}")
async def delete_discount(
    discount_id: int,
    admin: StoreAdmin = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    discount = await db.get(StoreDiscount, discount_id)
    if not discount or discount.store_id != admin.store_id:
        raise HTTPException(status_code=404, detail="Discount not found")
    discount.active = False
    await db.commit()
    return {"ok": True}


@router.post("/pricing/bulk-adjust", response_model=BulkPriceAdjustOut)
async def bulk_adjust_catalog_prices(
    body: BulkPriceAdjustIn,
    admin: StoreAdmin = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await bulk_adjust_prices(
            db,
            admin.store_id,
            body.scope.strip().lower(),
            body.mode.strip().lower(),
            body.value,
            body.target_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    scope_label = SCOPE_LABELS.get(body.scope, body.scope)
    return BulkPriceAdjustOut(
        updated_count=result["updated_count"],
        store_colors=result.get("store_colors", 0),
        brand_packs=result.get("brand_packs", 0),
        decor_colors=result.get("decor_colors", 0),
        decor_packs=result.get("decor_packs", 0),
        message=f"Оновлено {result['updated_count']} позицій ({scope_label})",
    )
