"""store crew telegram chat

Revision ID: 012_store_crew_chat
Revises: 011_store_broadcasts
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012_store_crew_chat"
down_revision: str | None = "011_store_broadcasts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("crew_telegram_chat_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("stores", "crew_telegram_chat_id")
