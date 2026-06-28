import httpx
import structlog

from app.services.bot_tokens import bot_id_from_token

logger = structlog.get_logger()


async def notify_project_status(
    chat_id: int,
    message_id: int | None,
    text: str,
    webapp_url: str | None = None,
    bot_token: str | None = None,
) -> int | None:
    if not bot_token:
        logger.warning("telegram_notify_skipped", reason="no token")
        return message_id

    notify_bot_id = bot_id_from_token(bot_token)
    url = f"https://api.telegram.org/bot{bot_token}"
    reply_markup = None
    if webapp_url:
        reply_markup = {
            "inline_keyboard": [[
                {"text": "🎨 Відкрити редактор", "web_app": {"url": webapp_url}}
            ]]
        }

    async with httpx.AsyncClient(timeout=30) as client:
        if message_id:
            payload: dict = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML",
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            resp = await client.post(f"{url}/editMessageText", json=payload)
            if resp.status_code == 200:
                return message_id
            logger.warning(
                "edit_message_failed",
                status=resp.status_code,
                notify_bot_id=notify_bot_id,
                message_id=message_id,
                body=resp.text,
            )

        resp = await client.post(
            f"{url}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": reply_markup,
            },
        )
        resp.raise_for_status()
        return resp.json()["result"]["message_id"]
