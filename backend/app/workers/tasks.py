import asyncio
from pathlib import Path

import cv2
import numpy as np
import structlog
import torch
from PIL import Image

from app.config import settings
from app.database import SyncSessionLocal
from app.models import Project, ProjectStatus, User
from app.services.bot_tokens import bot_id_from_token, resolve_bot_token_for_project
from app.services.jwt import create_user_token
from app.services.webapp import build_webapp_url
from app.services.lead_notify import READY_CTA_TEXT
from app.services.notifications import notify_project_status
from app.services.storage import StorageService
from app.workers.celery_app import celery_app

logger = structlog.get_logger()

_segformer_model = None
_segformer_processor = None

ADE20K_WALL_CLASS = 0
ADE20K_EXCLUDE_CLASSES = {
    3, 5, 7, 8, 9, 11, 15, 19, 22, 23, 25, 30, 33, 35, 40, 57, 64, 82,
}


def _get_segformer():
    global _segformer_model, _segformer_processor
    if _segformer_model is not None:
        return _segformer_model, _segformer_processor

    torch.set_num_threads(settings.torch_num_threads)
    try:
        from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor

        model_id = settings.segformer_model_id
        _segformer_processor = SegformerImageProcessor.from_pretrained(model_id)
        _segformer_model = SegformerForSemanticSegmentation.from_pretrained(model_id)
        _segformer_model.eval()
        logger.info("segformer_loaded", model=model_id)
        return _segformer_model, _segformer_processor
    except Exception as exc:
        logger.warning("segformer_unavailable", error=str(exc))
        return None, None


def _resize_image(img: np.ndarray, max_size: int) -> np.ndarray:
    h, w = img.shape[:2]
    if max(h, w) <= max_size:
        return img
    scale = max_size / max(h, w)
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def _segformer_inference(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    from torch.nn import functional as F

    model, processor = _get_segformer()
    if model is None or processor is None:
        raise RuntimeError("SegFormer model is not available")

    h, w = img.shape[:2]
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    inputs = processor(images=pil, return_tensors="pt")

    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits.cpu()
    upsampled = F.interpolate(
        logits,
        size=(h, w),
        mode="bilinear",
        align_corners=False,
    )
    probabilities = F.softmax(upsampled, dim=1)
    wall_probs = probabilities[0, ADE20K_WALL_CLASS].numpy()
    pred = upsampled.argmax(dim=1)[0].cpu().numpy().astype(np.int32)
    return wall_probs, pred


def _generate_wall_mask(img: np.ndarray) -> np.ndarray:
    """Маска стін — як у робочому Flask-проєкті."""
    wall_probs, pred = _segformer_inference(img)
    threshold = settings.wall_confidence_threshold

    wall_mask = np.where(wall_probs > threshold, 255, 0).astype(np.uint8)

    for cls_id in ADE20K_EXCLUDE_CLASSES:
        wall_mask[pred == cls_id] = 0

    kernel_close = np.ones((5, 5), np.uint8)
    wall_mask = cv2.morphologyEx(wall_mask, cv2.MORPH_CLOSE, kernel_close)
    kernel_open = np.ones((3, 3), np.uint8)
    wall_mask = cv2.morphologyEx(wall_mask, cv2.MORPH_OPEN, kernel_open)
    return cv2.GaussianBlur(wall_mask, (5, 5), 0)


def _create_specular_map(img: np.ndarray, wall_mask: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    smooth_light = cv2.GaussianBlur(gray, (71, 71), 0)
    light_norm = cv2.normalize(smooth_light, None, 0, 255, cv2.NORM_MINMAX)
    specular = np.clip((light_norm / 255.0) ** 3.0 * 255.0, 0, 255).astype(np.uint8)
    _, wall_binary = cv2.threshold(wall_mask, 127, 255, cv2.THRESH_BINARY)
    return cv2.bitwise_and(specular, specular, mask=wall_binary)


def _save_grayscale_png(path: Path, gray: np.ndarray) -> None:
    cv2.imwrite(str(path), gray)


def _process_image(project_id: int) -> None:
    storage = StorageService()
    with SyncSessionLocal() as db:
        project = db.get(Project, project_id)
        if not project or not project.original_image:
            return

        project.status = ProjectStatus.PROCESSING
        db.commit()

        try:
            img_path = storage.absolute_path(project.original_image)
            img = cv2.imread(str(img_path))
            if img is None:
                raise ValueError("Cannot read image")

            img = _resize_image(img, settings.max_image_size)
            cv2.imwrite(str(img_path), img)

            logger.info(
                "wall_mask_start",
                threshold=settings.wall_confidence_threshold,
                model=settings.segformer_model_id,
            )

            mask = _generate_wall_mask(img)
            specular = _create_specular_map(img, mask)
            coverage = float((mask > 127).mean())
            logger.info("wall_mask_generated", coverage=coverage)

            proj_dir = storage.project_dir(project_id)
            mask_path = proj_dir / "mask.png"
            illum_path = proj_dir / "illumination.png"
            spec_path = proj_dir / "specular.png"
            _save_grayscale_png(mask_path, mask)
            _save_grayscale_png(spec_path, specular)
            illumination = np.full(mask.shape, 255, dtype=np.uint8)
            cv2.imwrite(str(illum_path), illumination)

            project.mask_image = str(mask_path.relative_to(storage.base))
            project.illumination_image = str(illum_path.relative_to(storage.base))
            project.specular_image = str(spec_path.relative_to(storage.base))
            project.status = ProjectStatus.READY
            project.error_message = None
            db.commit()

            if project.telegram_chat_id:
                user = db.get(User, project.user_id)
                bot_token = resolve_bot_token_for_project(db, project)
                logger.info(
                    "project_notify_ready",
                    project_id=project.id,
                    store_id=project.store_id,
                    telegram_bot_id=project.telegram_bot_id,
                    notify_bot_id=bot_id_from_token(bot_token),
                )
                token = create_user_token(user.id, user.telegram_id) if user else ""
                webapp_url = build_webapp_url(project.id, token)
                asyncio.run(notify_project_status(
                    project.telegram_chat_id,
                    project.telegram_message_id,
                    READY_CTA_TEXT,
                    webapp_url=webapp_url,
                    bot_token=bot_token,
                ))
        except Exception as exc:
            logger.exception("ai_processing_failed", project_id=project_id)
            project.status = ProjectStatus.ERROR
            project.error_message = str(exc)
            db.commit()
            if project.telegram_chat_id:
                bot_token = resolve_bot_token_for_project(db, project)
                asyncio.run(notify_project_status(
                    project.telegram_chat_id,
                    project.telegram_message_id,
                    f"❌ <b>Помилка обробки:</b> {exc}",
                    bot_token=bot_token,
                ))
            try:
                from app.models import Store
                from app.services.ops_notify import ops_alert_ai_failed

                store = db.get(Store, project.store_id)
                ops_alert_ai_failed(
                    project.id,
                    store.name if store else f"Store #{project.store_id}",
                    str(exc),
                )
            except Exception:
                logger.exception("ops_alert_failed")


@celery_app.task(name="process_wall_segmentation")
def process_wall_segmentation(project_id: int) -> None:
    _process_image(project_id)


@celery_app.task(name="send_store_broadcast")
def send_store_broadcast(broadcast_id: int) -> None:
    from app.services.broadcast import run_store_broadcast

    with SyncSessionLocal() as db:
        run_store_broadcast(db, broadcast_id)
