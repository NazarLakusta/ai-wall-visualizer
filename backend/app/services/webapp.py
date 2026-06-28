from urllib.parse import quote

from app.config import settings


def build_webapp_url(project_id: int, access_token: str = "") -> str:
    base = settings.webapp_url.rstrip("/")
    url = f"{base}/?project_id={project_id}"
    if access_token:
        url += f"&access_token={quote(access_token, safe='')}"
    return url
