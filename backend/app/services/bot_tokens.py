from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project, Store


def bot_id_from_token(token: str | None) -> str | None:
    if not token:
        return None
    token = token.strip()
    if ":" not in token:
        return None
    return token.split(":", 1)[0]


def resolve_bot_token_for_project(db: Session, project: Project) -> str | None:
    """Return the Telegram bot token that should notify the user for this project."""
    stores = list(db.scalars(select(Store).where(Store.active.is_(True))).all())

    if project.telegram_bot_id:
        target = str(project.telegram_bot_id)
        for store in stores:
            token = (store.telegram_bot_token or "").strip()
            if bot_id_from_token(token) == target:
                return token

    store = db.get(Store, project.store_id)
    if store:
        token = (store.telegram_bot_token or "").strip()
        if token:
            return token

    return None
