import hashlib
import hmac
import json
from urllib.parse import parse_qsl, unquote


def validate_telegram_init_data(init_data: str, bot_token: str) -> dict:
    """Validate Telegram WebApp initData per official docs."""
    if not init_data:
        raise ValueError("Missing init data")
    if not bot_token:
        raise ValueError("Bot token not configured")

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise ValueError("Missing hash")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Invalid init data signature")

    user_raw = parsed.get("user")
    if not user_raw:
        raise ValueError("Missing user in init data")

    user = json.loads(unquote(user_raw))
    return user
