import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.database import SyncSessionLocal
from app.models import Project
from app.services.storage import StorageService


def run_cleanup_once() -> int:
    storage = StorageService()
    deleted = 0
    with SyncSessionLocal() as db:
        expired = db.scalars(
            select(Project).where(Project.expires_at < datetime.now(timezone.utc))
        ).all()
        for project in expired:
            storage.delete_project_files(project.id)
            db.delete(project)
            deleted += 1
        db.commit()
    return deleted


def main() -> None:
    import structlog
    logger = structlog.get_logger()
    interval = settings.cleanup_interval_minutes * 60
    logger.info("cleanup_service_started", interval_minutes=settings.cleanup_interval_minutes)
    while True:
        try:
            count = run_cleanup_once()
            if count:
                logger.info("cleanup_completed", deleted_projects=count)
        except Exception:
            logger.exception("cleanup_error")
        time.sleep(interval)


if __name__ == "__main__":
    main()
