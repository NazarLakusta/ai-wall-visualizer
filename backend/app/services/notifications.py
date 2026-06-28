import httpx
import structlog

from app.services.bot_tokens import bot_id_from_token

logger = structlog.get_logger()


def _webapp_keyboard(webapp_url: str | None) -> dict | None:
    if not webapp_url or not webapp_url.startswith("https://"):
        return None
    # Reply keyboard (як у «Тестове фото») — надійніше за inline web_app
    return {
        "keyboard": [[
            {"text": "🎨 Відкрити редактор", "web_app": {"url": webapp_url}}
        ]],
        "resize_keyboard": True,
    }


def _append_webapp_link(text: str, webapp_url: str | None) -> str:
    if not webapp_url:
        return text
    if webapp_url.startswith("https://"):
        return text
    return f"{text}\n\n🔗 Відкрийте редактор:\n<code>{webapp_url}</code>"


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
    message_text = _append_webapp_link(text, webapp_url)
    reply_markup = _webapp_keyboard(webapp_url)

    async with httpx.AsyncClient(timeout=30) as client:
        if message_id:
            edit_payload: dict = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": message_text,
                "parse_mode": "HTML",
            }
            if reply_markup:
                edit_payload["reply_markup"] = reply_markup
            resp = await client.post(f"{url}/editMessageText", json=edit_payload)
            if resp.status_code == 200:
                return message_id
            logger.warning(
                "edit_message_failed",
                status=resp.status_code,
                notify_bot_id=notify_bot_id,
                message_id=message_id,
                body=resp.text,
            )

        send_payload: dict = {
            "chat_id": chat_id,
            "text": message_text,
            "parse_mode": "HTML",
        }
        if reply_markup:
            send_payload["reply_markup"] = reply_markup

        resp = await client.post(f"{url}/sendMessage", json=send_payload)
        if resp.status_code == 200:
            return resp.json()["result"]["message_id"]

        logger.warning(
            "send_message_failed",
            status=resp.status_code,
            notify_bot_id=notify_bot_id,
            body=resp.text,
            had_webapp=bool(reply_markup),
        )

        if reply_markup:
            fallback_payload = {
                "chat_id": chat_id,
                "text": message_text,
                "parse_mode": "HTML",
            }
            resp = await client.post(f"{url}/sendMessage", json=fallback_payload)
            if resp.status_code == 200:
                return resp.json()["result"]["message_id"]
            logger.warning(
                "send_message_fallback_failed",
                status=resp.status_code,
                body=resp.text,
            )

    return message_id
