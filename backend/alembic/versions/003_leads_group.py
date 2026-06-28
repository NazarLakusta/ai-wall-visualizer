"""Add leads group chat for consultant notifications

Revision ID: 003_leads_group
Revises: 002_sales
"""

from alembic import op
import sqlalchemy as sa

revision = "003_leads_group"
down_revision = "002_sales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("leads_group_chat_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("stores", "leads_group_chat_id")
