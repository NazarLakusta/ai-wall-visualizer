from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Lead, LeadStatus, Project, Store, User
from app.schemas import LeadCreate, LeadCreateResponse
from app.services.lead_notify import (
    customer_ack_plain_text,
    notify_lead_created,
    notify_lead_customer_ack,
)
from app.services.decor_estimate_db import estimate_decor_for_project
from app.services.paint_estimate_db import estimate_paint_for_project
from app.services.pricing import calc_total_price
from app.services.selection import build_selection_summary, get_active_price_per_sqm

router = APIRouter(prefix="/leads", tags=["leads"])


def _pick_snapshot_value(server_value, client_value):
    if server_value is not None and server_value != "":
        if isinstance(server_value, (int, float)) and server_value <= 0:
            pass
        else:
            return server_value
    return client_value


@router.post("", response_model=LeadCreateResponse)
async def create_lead(
    body: LeadCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, body.project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    store = await db.get(Store, project.store_id)
    if not store:
        raise HTTPException(status_code=400, detail="Store not found")

    area = body.wall_area_sqm if body.wall_area_sqm and body.wall_area_sqm > 0 else project.wall_area_sqm
    if body.wall_area_sqm and body.wall_area_sqm > 0:
        project.wall_area_sqm = float(body.wall_area_sqm)

    price = await get_active_price_per_sqm(db, project)
    summary = await build_selection_summary(db, project)

    paint_estimate = None
    if project.selected_color_id and area:
        paint_estimate = await estimate_paint_for_project(
            db, project, project.selected_color_id, area, brand_id=project.selected_brand_id
        )
    elif project.selected_material_id and area:
        paint_estimate = await estimate_decor_for_project(
            db,
            project,
            project.selected_material_id,
            project.selected_decor_color_id,
            area,
        )

    if paint_estimate:
        total = paint_estimate.total_uah
        paint_plan = paint_estimate.summary_detail
    else:
        total = calc_total_price(price, area)
        paint_plan = None

    wall_area_sqm = _pick_snapshot_value(area, body.wall_area_sqm)
    estimated_total_uah = _pick_snapshot_value(total, body.estimated_total_uah)
    selection_summary = _pick_snapshot_value(summary, body.selection_summary)
    paint_plan_summary = _pick_snapshot_value(paint_plan, body.paint_plan_summary)

    lead = Lead(
        store_id=project.store_id,
        project_id=project.id,
        user_id=user.id,
        phone=body.phone.strip(),
        customer_name=body.customer_name,
        comment=body.comment,
        wall_area_sqm=wall_area_sqm,
        estimated_total_uah=estimated_total_uah,
        selection_summary=selection_summary,
        paint_plan_summary=paint_plan_summary,
        status=LeadStatus.NEW,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    await db.refresh(store)

    manager_notified = await notify_lead_created(store, lead, project, user)
    customer_notified = await notify_lead_customer_ack(store, lead, project, user)
    ack_text = customer_ack_plain_text(store)
    return LeadCreateResponse.model_validate(lead).model_copy(
        update={
            "telegram_notified": manager_notified,
            "customer_notified": customer_notified,
            "customer_ack_text": ack_text,
            "telegram_username": user.username,
        }
    )
