"""store discounts for catalog pricing

Revision ID: 014_store_discounts
Revises: 013_store_brands_decor_packs
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014_store_discounts"
down_revision: str | None = "013_store_brands_decor_packs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_discounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("discount_percent", sa.Float(), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_store_discounts_store_active", "store_discounts", ["store_id", "active"])


def downgrade() -> None:
    op.drop_index("ix_store_discounts_store_active", table_name="store_discounts")
    op.drop_table("store_discounts")
