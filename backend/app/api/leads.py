from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Lead, LeadStatus, Project, Store, User
from app.schemas import LeadCreate, LeadCreateResponse
from app.services.lead_notify import notify_lead_created, send_manager_message
from app.services.decor_estimate_db import estimate_decor_for_project
from app.services.paint_estimate_db import estimate_paint_for_project
from app.services.pricing import calc_total_price
from app.services.selection import build_selection_summary, get_active_price_per_sqm

router = APIRouter(prefix="/leads", tags=["leads"])


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

    price = await get_active_price_per_sqm(db, project)
    summary = await build_selection_summary(db, project)

    paint_estimate = None
    if project.selected_color_id and project.wall_area_sqm:
        paint_estimate = await estimate_paint_for_project(
            db, project, project.selected_color_id, project.wall_area_sqm
        )
    elif project.selected_material_id and project.wall_area_sqm:
        paint_estimate = await estimate_decor_for_project(
            db,
            project,
            project.selected_material_id,
            project.selected_decor_color_id,
            project.wall_area_sqm,
        )

    if paint_estimate:
        total = paint_estimate.total_uah
        paint_plan = paint_estimate.summary_detail
    else:
        total = calc_total_price(price, project.wall_area_sqm)
        paint_plan = None

    lead = Lead(
        store_id=project.store_id,
        project_id=project.id,
        user_id=user.id,
        phone=body.phone.strip(),
        customer_name=body.customer_name,
        comment=body.comment,
        wall_area_sqm=project.wall_area_sqm,
        estimated_total_uah=total,
        selection_summary=summary,
        paint_plan_summary=paint_plan,
        status=LeadStatus.NEW,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    await db.refresh(store)

    notified = await notify_lead_created(store, lead, project)
    return LeadCreateResponse.model_validate(lead).model_copy(update={"telegram_notified": notified})
