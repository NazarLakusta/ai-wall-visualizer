from pathlib import Path

import httpx
import structlog

from app.models import Lead, Project, Store, User
from app.services.store_hours import customer_lead_ack_message, customer_lead_contacted_message
from app.services.storage import StorageService

logger = structlog.get_logger()

READY_CTA_TEXT = (
    "✅ <b>Готово!</b>\n\n"
    "1️⃣ Відкрийте редактор\n"
    "2️⃣ Вкажіть <b>площу стін (м²)</b>\n"
    "3️⃣ Оберіть фарбу — одразу побачите <b>вартість</b>\n"
    "4️⃣ Натисніть <b>«Надіслати консультанту»</b>\n\n"
    "Або зателефонуйте в магазин прямо з редактора 📞"
)


def _format_uah(amount: float | None) -> str:
    if amount is None:
        return "—"
    return f"₴{amount:,.0f}".replace(",", " ")


def _lead_details_block(lead: Lead) -> str:
    lines: list[str] = []
    if lead.wall_area_sqm and lead.wall_area_sqm > 0:
        lines.append(f"📐 Площа: <b>{lead.wall_area_sqm:g} м²</b>")
    if lead.selection_summary:
        lines.append(f"🎨 {lead.selection_summary}")
    if lead.estimated_total_uah is not None and lead.estimated_total_uah > 0:
        lines.append(f"💰 Разом: <b>{_format_uah(lead.estimated_total_uah)}</b>")
    if lead.paint_plan_summary:
        for line in lead.paint_plan_summary.split("\n"):
            if line.strip():
                lines.append(f"🪣 {line.strip()}")
    return "\n".join(lines)


def _lead_notification_text(store: Store, lead: Lead, project: Project, user: User | None = None) -> str:
    user_line = lead.customer_name or "Клієнт"
    text = (
        f"📬 <b>Заявка для консультанта</b>\n"
        f"🏪 {store.name}\n\n"
        f"👤 {user_line}\n"
        f"📞 <code>{lead.phone}</code>\n"
    )
    if user and user.username:
        text += f"💬 Telegram: @{user.username.lstrip('@')}\n"
    details = _lead_details_block(lead)
    if details:
        text += f"\n{details}\n"
    if lead.comment:
        text += f"💬 {lead.comment}\n"
    text += f"\n🆔 Проєкт #{project.id}"
    return text


def _notification_targets(store: Store) -> list[int]:
    targets: list[int] = []
    for chat_id in (store.leads_group_chat_id, store.manager_telegram_chat_id):
        if chat_id and int(chat_id) not in targets:
            targets.append(int(chat_id))
    return targets


def _store_bot_token(store: Store) -> str | None:
    token = (store.telegram_bot_token or "").strip()
    return token or None


def _result_image_path(project: Project) -> Path | None:
    rel = (project.result_image or "").strip()
    if not rel:
        return None
    path = StorageService().absolute_path(rel)
    if not path.is_file():
        logger.info("lead_photo_skipped", project_id=project.id, reason="file missing")
        return None
    return path


def _original_image_path(project: Project) -> Path | None:
    rel = (project.original_image or "").strip()
    if not rel:
        return None
    path = StorageService().absolute_path(rel)
    if not path.is_file():
        logger.info("lead_photo_skipped", project_id=project.id, reason="original missing")
        return None
    return path


def _customer_chat_id(project: Project, user: User | None) -> int | None:
    if project.telegram_chat_id:
        return int(project.telegram_chat_id)
    if user and user.telegram_id:
        return int(user.telegram_id)
    return None


async def notify_lead_created(store: Store, lead: Lead, project: Project, user: User | None = None) -> bool:
    bot_token = _store_bot_token(store)
    if not bot_token:
        logger.info("lead_notify_skipped", store_id=store.id, reason="no token")
        return False

    targets = _notification_targets(store)
    if not targets:
        logger.info("lead_notify_skipped", store_id=store.id, reason="no chat ids")
        return False

    text = _lead_notification_text(store, lead, project, user)
    photo_path = _result_image_path(project)
    photo_caption = f"🖼 Результат візуалізації · проєкт #{project.id}"

    ok_any = False
    for chat_id in targets:
        if await send_manager_message(chat_id, text, bot_token):
            ok_any = True
        if photo_path:
            if await send_manager_photo(chat_id, photo_path, photo_caption, bot_token):
                ok_any = True
    return ok_any


async def notify_lead_customer_ack(
    store: Store,
    lead: Lead,
    project: Project,
    user: User | None = None,
) -> bool:
    bot_token = _store_bot_token(store)
    chat_id = _customer_chat_id(project, user)
    if not bot_token or not chat_id:
        logger.info("lead_customer_ack_skipped", lead_id=lead.id, reason="no token or chat")
        return False
    text = customer_lead_ack_message(store, lead.created_at)
    return await send_manager_message(chat_id, text, bot_token)


async def notify_lead_customer_contacted(
    store: Store,
    lead: Lead,
    project: Project,
    user: User | None = None,
) -> bool:
    bot_token = _store_bot_token(store)
    chat_id = _customer_chat_id(project, user)
    if not bot_token or not chat_id:
        return False
    text = customer_lead_contacted_message(store)
    return await send_manager_message(chat_id, text, bot_token)


async def notify_lead_customer_text(
    store: Store,
    lead: Lead,
    project: Project,
    user: User | None,
    message: str,
) -> bool:
    bot_token = _store_bot_token(store)
    chat_id = _customer_chat_id(project, user)
    if not bot_token or not chat_id:
        return False
    return await send_manager_message(chat_id, message.strip(), bot_token)


async def send_customer_document(
    chat_id: int,
    file_bytes: bytes,
    filename: str,
    caption: str,
    bot_token: str,
) -> bool:
    if not bot_token or not file_bytes:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url,
            data={"chat_id": str(int(chat_id)), "caption": caption[:1024], "parse_mode": "HTML"},
            files={"document": (filename, file_bytes, "application/pdf")},
        )
        if resp.status_code == 200:
            return True
        logger.warning(
            "telegram_document_failed",
            chat_id=chat_id,
            status=resp.status_code,
            body=resp.text[:300],
        )
        return False


async def send_lead_quote_to_customer(
    store: Store,
    lead: Lead,
    project: Project,
    user: User | None,
    pdf_bytes: bytes,
) -> bool:
    bot_token = _store_bot_token(store)
    chat_id = _customer_chat_id(project, user)
    if not bot_token or not chat_id:
        return False
    caption = f"📄 Кошторис від <b>{store.name}</b>"
    filename = f"koshtorys-{lead.id}.pdf"
    return await send_customer_document(chat_id, pdf_bytes, filename, caption, bot_token)


def customer_ack_plain_text(store: Store) -> str:
    """Plain text for mini-app alert (no HTML)."""
    from app.services.store_hours import business_hours_label, is_store_open, next_contact_phrase

    if is_store_open(store):
        return (
            f"Дякуємо за заявку! {store.name} отримав ваш запит. "
            "Консультант зателефонує протягом 15 хвилин."
        )
    when = next_contact_phrase(store).replace("<b>", "").replace("</b>", "")
    hours = business_hours_label(store)
    return (
        f"Дякуємо за заявку! Зараз магазин не працює. "
        f"Ми зв'яжемось з вами {when}. Графік: {hours}."
    )


def _crew_lead_text(store: Store, lead: Lead, project: Project) -> str:
    user_line = lead.customer_name or "Клієнт"
    test_mark = " (тестове фото)" if project.is_test else ""
    text = (
        f"🔧 <b>Заявка для монтажної бригади</b>{test_mark}\n"
        f"🏪 {store.name}\n\n"
        f"👤 {user_line}\n"
        f"📞 <code>{lead.phone}</code>\n"
    )
    if lead.wall_area_sqm and lead.wall_area_sqm > 0:
        text += f"📐 Площа: <b>{lead.wall_area_sqm:g} м²</b>\n"
    if lead.selection_summary:
        text += f"🎨 {lead.selection_summary}\n"
    if lead.estimated_total_uah is not None and lead.estimated_total_uah > 0:
        text += f"💰 Орієнтовно: <b>{_format_uah(lead.estimated_total_uah)}</b>\n"
    if lead.paint_plan_summary:
        for line in lead.paint_plan_summary.split("\n"):
            if line.strip():
                text += f"🪣 {line.strip()}\n"
    if lead.comment:
        text += f"💬 {lead.comment}\n"
    if store.phone:
        text += f"\n📞 Магазин: {store.phone}"
    text += f"\n🆔 Проєкт #{project.id} · заявка #{lead.id}"
    return text


async def notify_lead_to_crew(store: Store, lead: Lead, project: Project) -> tuple[bool, str]:
    bot_token = _store_bot_token(store)
    if not bot_token:
        return False, "Вкажіть токен Telegram-бота магазину в налаштуваннях"

    chat_id = store.crew_telegram_chat_id
    if not chat_id:
        return False, "Вкажіть Chat ID монтажної бригади в налаштуваннях магазину"

    text = _crew_lead_text(store, lead, project)
    ok_any = False
    if await send_manager_message(int(chat_id), text, bot_token):
        ok_any = True

    original_path = _original_image_path(project)
    if original_path:
        label = "📷 Тестове фото кімнати" if project.is_test else "📷 Фото кімнати клієнта"
        if await send_manager_photo(int(chat_id), original_path, label, bot_token):
            ok_any = True

    result_path = _result_image_path(project)
    if result_path:
        caption = f"🖼 Результат візуалізації · проєкт #{project.id}"
        if await send_manager_photo(int(chat_id), result_path, caption, bot_token):
            ok_any = True

    if ok_any:
        return True, ""
    return False, (
        "Telegram не прийняв повідомлення. Додайте бота в чат бригади і натисніть /start, "
        "або перевірте Chat ID."
    )


async def send_manager_message(chat_id: int, text: str, bot_token: str) -> bool:
    if not bot_token:
        logger.warning("telegram_send_skipped", reason="no token")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            json={"chat_id": int(chat_id), "text": text, "parse_mode": "HTML"},
        )
        if resp.status_code == 200:
            return True
        body = resp.text
        logger.warning("telegram_send_failed", chat_id=chat_id, status=resp.status_code, body=body)
        return False


async def send_manager_photo(
    chat_id: int,
    photo_path: Path,
    caption: str,
    bot_token: str,
) -> bool:
    if not bot_token:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    suffix = photo_path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    filename = photo_path.name or f"result{suffix or '.jpg'}"

    try:
        data_bytes = photo_path.read_bytes()
    except OSError as exc:
        logger.warning("lead_photo_read_failed", path=str(photo_path), error=str(exc))
        return False

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url,
            data={"chat_id": str(int(chat_id)), "caption": caption, "parse_mode": "HTML"},
            files={"photo": (filename, data_bytes, mime)},
        )
        if resp.status_code == 200:
            return True
        logger.warning(
            "telegram_photo_failed",
            chat_id=chat_id,
            status=resp.status_code,
            body=resp.text[:300],
        )
        return False


async def send_test_notifications(store: Store) -> tuple[bool, str]:
    bot_token = _store_bot_token(store)
    if not bot_token:
        return False, "Вкажіть токен Telegram-бота магазину в налаштуваннях"

    targets = _notification_targets(store)
    if not targets:
        return False, "Вкажіть Chat ID менеджера або групи заявок"

    text = (
        f"✅ <b>Тестове сповіщення</b> — {store.name}\n\n"
        "Якщо ви бачите це в окремому чаті/групі — заявки клієнтів будуть приходити сюди."
    )
    ok_any = False
    errors: list[str] = []
    for chat_id in targets:
        if await send_manager_message(chat_id, text, bot_token):
            ok_any = True
        else:
            errors.append(str(chat_id))
    if ok_any:
        return True, ""
    return False, (
        "Telegram не прийняв повідомлення. "
        "Для особистого чату — натисніть /start у боті магазину. "
        "Для групи — додайте бота в групу і вкажіть її Chat ID."
        + (f" Помилка для: {', '.join(errors)}" if errors else "")
    )
