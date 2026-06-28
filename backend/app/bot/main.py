import asyncio
import time

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import ErrorEvent, KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo
import httpx
import structlog

from app.bot.registry import StoreBotBinding, build_store_lookup, load_store_bot_bindings
from app.config import settings
from app.models import Store
from app.services.lead_notify import READY_CTA_TEXT
from app.services.queue_monitor import queue_busy_message, queue_position_message
from app.services.webapp import build_webapp_url

logger = structlog.get_logger()

API_UNAVAILABLE_MSG = (
    "❌ <b>Сервіс API тимчасово недоступний</b>\n\n"
    "Ймовірно, контейнер <code>api</code> ще запускається або зупинений.\n\n"
    "У терміналі перевірте:\n"
    "<code>docker compose ps api</code>\n\n"
    "Якщо api не працює:\n"
    "<code>docker compose up -d api bot</code>\n\n"
    "Зачекайте 10–20 сек і натисніть «Тестове фото» знову."
)

STATUS_MESSAGES = {
    "received": "📷 <b>Фото отримано</b>",
    "queued": "⏳ <b>Очікує в черзі</b>",
    "processing": "🔄 <b>Обробляється</b>",
    "ready": "✅ <b>Готово!</b>",
    "error": "❌ <b>Помилка</b>",
}

BINDINGS: list[StoreBotBinding] = []
STORE_BY_BOT_ID: dict[int, Store] = {}


def _api_url(path: str) -> str:
    return f"{settings.internal_api_url.rstrip('/')}{path}"


async def wait_for_api(timeout_sec: int = 120) -> bool:
    deadline = time.monotonic() + timeout_sec
    url = _api_url("/health")
    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    logger.info("api_ready", url=url)
                    return True
        except (httpx.ConnectError, httpx.ConnectTimeout):
            pass
        await asyncio.sleep(2)
    logger.error("api_not_ready", url=url)
    return False


async def api_post(client: httpx.AsyncClient, path: str, **kwargs) -> httpx.Response:
    url = _api_url(path)
    last_exc: Exception | None = None
    for attempt in range(5):
        try:
            return await client.post(url, **kwargs)
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            last_exc = exc
            if attempt < 4:
                await asyncio.sleep(1 + attempt)
    assert last_exc is not None
    raise last_exc


def _store_for_message(message: Message) -> Store:
    store = STORE_BY_BOT_ID.get(message.bot.id)
    if not store:
        logger.error("unknown_bot_id", bot_id=message.bot.id, known=list(STORE_BY_BOT_ID.keys()))
        raise RuntimeError("Bot not linked to any store. Restart bot service after saving token.")
    return store


def _main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📷 Завантажити фото")],
            [KeyboardButton(text="🖼 Тестове фото")],
        ],
        resize_keyboard=True,
    )


def _welcome_text(store: Store) -> str:
    return (
        f"🎨 <b>{store.name}</b>\n\n"
        "Підберіть колір або декор на фото вашої кімнати.\n\n"
        "🖼 <b>Тестове фото</b> — одразу без черги (рекомендуємо для першого разу)\n"
        "📷 <b>Завантажити фото</b> — ваше приміщення (AI ~1–3 хв)\n\n"
        "Оберіть дію на клавіатурі 👇"
    )


def _help_text(store: Store) -> str:
    return (
        f"ℹ️ <b>Довідка — {store.name}</b>\n\n"
        "<b>Як користуватись:</b>\n"
        "1️⃣ Натисніть «📷 Завантажити фото» і надішліть JPG/PNG кімнати (до 20 МБ)\n"
        "2️⃣ Зачекайте обробку — з’явиться кнопка «🎨 Відкрити редактор»\n"
        "3️⃣ У редакторі вкажіть площу стін, оберіть фарбу або декор\n"
        "4️⃣ Натисніть «Надіслати консультанту» — ми зв’яжемось з вами\n\n"
        "<b>Швидкий тест без фото:</b>\n"
        "«🖼 Тестове фото» — одразу відкриє редактор з демо-кімнатою.\n\n"
        "<b>Команди:</b>\n"
        "/start — головне меню\n"
        "/help — ця довідка"
    )


async def cmd_help(message: Message):
    store = _store_for_message(message)
    await message.answer(_help_text(store), parse_mode="HTML", reply_markup=_main_keyboard())


async def cmd_start(message: Message):
    store = _store_for_message(message)
    logger.info("cmd_start", store=store.slug, user_id=message.from_user.id)
    await message.answer(_welcome_text(store), reply_markup=_main_keyboard(), parse_mode="HTML")


async def ask_photo(message: Message):
    await message.answer("Надішліть фото кімнати у форматі JPG або PNG (до 20 МБ).")


async def test_photo(message: Message):
    store = _store_for_message(message)
    status_msg = await message.answer("🖼 <b>Відкриваємо тестовий проєкт...</b>", parse_mode="HTML")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await api_post(
                client,
                "/api/internal/projects/test",
                data={
                    "telegram_id": message.from_user.id,
                    "username": message.from_user.username or "",
                    "first_name": message.from_user.first_name or "",
                    "store_slug": store.slug,
                    "telegram_chat_id": message.chat.id,
                    "telegram_message_id": status_msg.message_id,
                    "telegram_bot_id": message.bot.id,
                    "key": settings.secret_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.ConnectError, httpx.ConnectTimeout):
        logger.exception("test_project_api_unreachable")
        await status_msg.edit_text(API_UNAVAILABLE_MSG, parse_mode="HTML")
        return
    except httpx.HTTPStatusError as exc:
        logger.exception("test_project_http_error", status=exc.response.status_code)
        detail = exc.response.text[:200] if exc.response.text else str(exc)
        await status_msg.edit_text(f"❌ Помилка API ({exc.response.status_code}): {detail}")
        return
    except Exception as exc:
        logger.exception("test_project_failed")
        await status_msg.edit_text(f"❌ Помилка створення проєкту: {exc}")
        return

    project_id = data["project_id"]
    access_token = data.get("access_token", "")
    webapp_url = build_webapp_url(project_id, access_token)

    if webapp_url.startswith("https://"):
        await message.answer(
            READY_CTA_TEXT,
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🎨 Відкрити редактор", web_app=WebAppInfo(url=webapp_url))]],
                resize_keyboard=True,
            ),
        )
    else:
        await message.answer(
            f"✅ <b>Тестовий проєкт готовий!</b> (ID: {project_id})\n\n"
            "⚠️ Telegram вимагає HTTPS для кнопки редактора.\n"
            "Локально відкрийте в браузері:\n"
            f"<code>{webapp_url}</code>\n\n"
            "Для тесту в Telegram використайте ngrok:\n"
            "<code>ngrok http 80</code> → вкажіть URL у .env як WEBAPP_URL",
            parse_mode="HTML",
            reply_markup=_main_keyboard(),
        )


async def handle_photo(message: Message):
    store = _store_for_message(message)
    bot = message.bot
    status_msg = await message.answer(STATUS_MESSAGES["received"], parse_mode="HTML")
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    content = file_bytes.read()

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await api_post(
                client,
                "/api/internal/projects/upload",
                data={
                    "telegram_id": message.from_user.id,
                    "username": message.from_user.username or "",
                    "first_name": message.from_user.first_name or "",
                    "store_slug": store.slug,
                    "telegram_chat_id": message.chat.id,
                    "telegram_message_id": status_msg.message_id,
                    "telegram_bot_id": message.bot.id,
                    "key": settings.secret_key,
                },
                files={"file": ("photo.jpg", content, "image/jpeg")},
            )
            if resp.status_code != 200:
                if resp.status_code == 503:
                    await status_msg.edit_text(resp.text or queue_busy_message(), parse_mode="HTML")
                else:
                    await status_msg.edit_text(f"❌ Помилка: {resp.text}")
                return
    except (httpx.ConnectError, httpx.ConnectTimeout):
        logger.exception("upload_api_unreachable")
        await status_msg.edit_text(API_UNAVAILABLE_MSG, parse_mode="HTML")
        return

    try:
        data = resp.json()
        position = int(data.get("queue_position") or 1)
        await status_msg.edit_text(queue_position_message(position), parse_mode="HTML")
    except Exception:
        await status_msg.edit_text(STATUS_MESSAGES["queued"], parse_mode="HTML")


async def on_error(event: ErrorEvent):
    logger.exception("bot_handler_error", error=str(event.exception))
    update = event.update
    message = update.message or (update.callback_query.message if update.callback_query else None)
    if message:
        try:
            await message.answer(
                "⚠️ <b>Помилка бота.</b>\n\n"
                "Спробуйте /start ще раз. Якщо не допомогло — адміністратору потрібно "
                "перезапустити сервіс <code>bot</code> після зміни токена в супер-адмінці.",
                parse_mode="HTML",
            )
        except Exception:
            pass


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.errors.register(on_error)
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(ask_photo, F.text == "📷 Завантажити фото")
    dp.message.register(test_photo, F.text == "🖼 Тестове фото")
    dp.message.register(handle_photo, F.photo)
    return dp


async def main():
    global BINDINGS, STORE_BY_BOT_ID
    BINDINGS = await load_store_bot_bindings()
    STORE_BY_BOT_ID = build_store_lookup(BINDINGS)

    if not BINDINGS:
        logger.error("no_store_bots_configured")
        return

    for binding in BINDINGS:
        logger.info(
            "bot_registered",
            store=binding.store.slug,
            store_name=binding.store.name,
            bot_username=binding.bot_username,
            bot_id=binding.bot_id,
        )

    logger.info("bot_starting", api_url=settings.internal_api_url, count=len(BINDINGS))
    if not await wait_for_api():
        logger.error("bot_start_aborted_api_down")
        return

    dp = build_dispatcher()
    bots = [binding.bot for binding in BINDINGS]
    await dp.start_polling(*bots)


if __name__ == "__main__":
    asyncio.run(main())
