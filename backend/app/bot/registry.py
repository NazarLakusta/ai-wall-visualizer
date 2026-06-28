from dataclasses import dataclass

import structlog

from aiogram import Bot
from sqlalchemy import select

from app.config import settings
from app.database import SyncSessionLocal
from app.models import Store

logger = structlog.get_logger()


@dataclass
class StoreBotBinding:
    store: Store
    bot: Bot
    bot_id: int
    bot_username: str | None = None


async def load_store_bot_bindings() -> list[StoreBotBinding]:
    bindings: list[StoreBotBinding] = []
    with SyncSessionLocal() as db:
        stores = list(
            db.scalars(
                select(Store).where(Store.active.is_(True), Store.telegram_bot_token.isnot(None))
            ).all()
        )

        if not stores and settings.telegram_bot_token:
            store = db.scalar(select(Store).where(Store.slug == settings.default_store_slug))
            if store:
                stores = [store]

    seen_tokens: set[str] = set()
    for store in stores:
        token = (store.telegram_bot_token or "").strip()
        if not token:
            if store.slug == settings.default_store_slug and settings.telegram_bot_token:
                token = settings.telegram_bot_token.strip()
            else:
                continue
        if token in seen_tokens:
            continue
        seen_tokens.add(token)

        bot = Bot(token=token)
        try:
            me = await bot.get_me()
        except Exception as exc:
            logger.error("invalid_bot_token", store=store.slug, error=str(exc))
            await bot.session.close()
            continue

        bindings.append(
            StoreBotBinding(
                store=store,
                bot=bot,
                bot_id=me.id,
                bot_username=me.username,
            )
        )

    return bindings


def build_store_lookup(bindings: list[StoreBotBinding]) -> dict[int, Store]:
    return {binding.bot_id: binding.store for binding in bindings}
