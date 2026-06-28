"""per-store brand pack prices (tenant isolation)

Revision ID: 015_store_brand_pack_prices
Revises: 014_store_discounts
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015_store_brand_pack_prices"
down_revision: str | None = "014_store_discounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_brand_pack_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "brand_pack_size_id",
            sa.Integer(),
            sa.ForeignKey("brand_pack_sizes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price_uah", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("store_id", "brand_pack_size_id", name="uq_store_brand_pack_price"),
    )
    op.create_index(
        "ix_store_brand_pack_prices_store",
        "store_brand_pack_prices",
        ["store_id"],
    )
    # Seed per-store overrides from current global pack prices (one-time, safe for multi-tenant).
    op.execute(
        """
        INSERT INTO store_brand_pack_prices (store_id, brand_pack_size_id, price_uah)
        SELECT sb.store_id, bps.id, bps.price_uah
        FROM store_brands sb
        JOIN brand_pack_sizes bps ON bps.brand_id = sb.brand_id AND bps.active = true
        WHERE sb.active = true
        ON CONFLICT (store_id, brand_pack_size_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_store_brand_pack_prices_store", table_name="store_brand_pack_prices")
    op.drop_table("store_brand_pack_prices")
