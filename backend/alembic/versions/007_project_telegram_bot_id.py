"""Add telegram_bot_id to projects for multi-bot notifications

Revision ID: 007_project_telegram_bot_id
Revises: 006_platform_admin
"""

from alembic import op
import sqlalchemy as sa

revision = "007_project_telegram_bot_id"
down_revision = "006_platform_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("telegram_bot_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "telegram_bot_id")
