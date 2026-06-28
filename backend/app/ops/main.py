"""Platform ops Telegram bot: /status + periodic heartbeat to owner chat."""

from __future__ import annotations

import asyncio

import structlog
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from app.config import settings
from app.services.ops_notify import (
    evaluate_ops_alerts,
    format_ops_status,
    send_ops_message,
    send_ops_status,
)
from app.services.ops_collector import collect_ops_snapshot

logger = structlog.get_logger()
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    chat_id = message.chat.id
    await message.answer(
        "🖥 <b>WallViz Ops</b>\n\n"
        "Я надсилаю стан сервера, чергу AI і помилки.\n\n"
        f"Ваш Chat ID: <code>{chat_id}</code>\n"
        "Додайте в <code>.env</code>:\n"
        f"<code>OPS_TELEGRAM_CHAT_ID={chat_id}</code>\n\n"
        "Команди:\n"
        "/status — стан зараз\n"
        "/help — довідка",
        parse_mode="HTML",
    )


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "📋 <b>Команди</b>\n\n"
        "/status — БД, Redis, черга AI, магазини, заявки\n\n"
        "Автоматично кожні "
        f"{settings.ops_heartbeat_interval_minutes} хв надсилаю зведення в чат з "
        "<code>OPS_TELEGRAM_CHAT_ID</code>.\n\n"
        "Миттєві алерти:\n"
        "• помилка AI на фото\n"
        "• висока черга\n"
        "• БД / Redis недоступні",
        parse_mode="HTML",
    )


@dp.message(Command("status"))
async def cmd_status(message: Message) -> None:
    snap = collect_ops_snapshot()
    await message.answer(format_ops_status(snap), parse_mode="HTML")


@dp.message(F.text)
async def unknown(message: Message) -> None:
    if message.text and message.text.startswith("/"):
        await message.answer("Невідома команда. Спробуйте /status або /help")


async def heartbeat_loop() -> None:
    interval = max(5, settings.ops_heartbeat_interval_minutes) * 60
    await asyncio.sleep(30)
    while True:
        try:
            snap = collect_ops_snapshot()
            evaluate_ops_alerts(snap)
            send_ops_status()
        except Exception:
            logger.exception("ops_heartbeat_failed")
        await asyncio.sleep(interval)


async def main() -> None:
    if not settings.ops_bot_enabled:
        logger.error(
            "ops_not_configured",
            hint="Set OPS_TELEGRAM_BOT_TOKEN in .env",
        )
        return

    token = settings.ops_telegram_bot_token.strip()
    bot = Bot(token=token)
    me = await bot.get_me()
    logger.info("ops_bot_starting", username=me.username, heartbeat_min=settings.ops_heartbeat_interval_minutes)

    if settings.ops_alerts_enabled:
        send_ops_message(
            f"🟢 <b>Ops monitor увімкнено</b>\n"
            f"Бот: @{me.username}\n"
            f"Звіт кожні {settings.ops_heartbeat_interval_minutes} хв.\n"
            "Команда /status — стан зараз."
        )
        asyncio.create_task(heartbeat_loop())
    else:
        logger.warning("ops_chat_id_missing", hint="Message /start to bot to get OPS_TELEGRAM_CHAT_ID")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
