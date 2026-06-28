"""Create or reset PlatformAdmin from current container .env (run after changing .env + recreate api)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, "/app")

from sqlalchemy import select

from app.config import settings
from app.database import SyncSessionLocal
from app.models import PlatformAdmin
from app.services.jwt import hash_password, verify_password


def main() -> None:
    email = settings.platform_admin_email
    password = settings.platform_admin_password

    with SyncSessionLocal() as db:
        admins = list(db.scalars(select(PlatformAdmin)).all())
        print(f"Platform admins in DB: {len(admins)}")
        for row in admins:
            print(f"  - {row.email!r} active={row.active}")

        admin = db.scalar(select(PlatformAdmin).where(PlatformAdmin.email == email))
        if admin:
            admin.password_hash = hash_password(password)
            admin.active = True
            if not admin.name:
                admin.name = "Platform Admin"
            print(f"Reset password for: {email}")
        else:
            admin = PlatformAdmin(
                email=email,
                password_hash=hash_password(password),
                name="Platform Admin",
                active=True,
            )
            db.add(admin)
            print(f"Created platform admin: {email}")

        db.commit()
        db.refresh(admin)
        ok = verify_password(password, admin.password_hash)
        print(f"Verify password from .env: {'OK' if ok else 'FAILED'}")
        print(f"Login with email={email!r} and PLATFORM_ADMIN_PASSWORD from .env")


if __name__ == "__main__":
    main()
