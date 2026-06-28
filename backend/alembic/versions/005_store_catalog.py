"""Per-store paint catalog (store_colors) and bot tokens

Revision ID: 005_store_catalog
Revises: 004_in_stock
"""

from alembic import op
import sqlalchemy as sa

revision = "005_store_catalog"
down_revision = "004_in_stock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "store_colors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("color_id", sa.Integer(), sa.ForeignKey("colors.id"), nullable=False),
        sa.Column("price_per_sqm", sa.Float(), nullable=True),
        sa.Column("in_stock", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("store_id", "color_id", name="uq_store_colors_store_color"),
    )
    op.create_index("ix_store_colors_store_active", "store_colors", ["store_id", "active"])

    op.execute(
        """
        INSERT INTO store_colors (store_id, color_id, price_per_sqm, in_stock, active)
        SELECT s.id, c.id, c.price_per_sqm, c.in_stock, c.active
        FROM stores s
        CROSS JOIN colors c
        """
    )


def downgrade() -> None:
    op.drop_index("ix_store_colors_store_active", table_name="store_colors")
    op.drop_table("store_colors")
