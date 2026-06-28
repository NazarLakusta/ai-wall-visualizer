"""Sync StoreAdmin / PlatformAdmin password hashes from current .env settings."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, "/app")

from sqlalchemy import select

from app.config import settings
from app.database import SyncSessionLocal
from app.models import PlatformAdmin, StoreAdmin
from app.services.jwt import hash_password


def main() -> None:
    with SyncSessionLocal() as db:
        store_admin = db.scalar(select(StoreAdmin).where(StoreAdmin.email == settings.admin_email))
        if store_admin:
            store_admin.password_hash = hash_password(settings.admin_password)
            print(f"Updated store admin password: {settings.admin_email}")
        else:
            print(f"No store admin for {settings.admin_email} — run seed first")

        platform_admin = db.scalar(
            select(PlatformAdmin).where(PlatformAdmin.email == settings.platform_admin_email)
        )
        if platform_admin:
            platform_admin.password_hash = hash_password(settings.platform_admin_password)
            platform_admin.active = True
            print(f"Updated platform admin password: {settings.platform_admin_email}")
        else:
            db.add(
                PlatformAdmin(
                    email=settings.platform_admin_email,
                    password_hash=hash_password(settings.platform_admin_password),
                    name="Platform Admin",
                    active=True,
                )
            )
            print(f"Created platform admin: {settings.platform_admin_email}")

        db.commit()
    print("Done.")


if __name__ == "__main__":
    main()
