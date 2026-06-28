"""Brand packaging, tint base, paint plan on leads

Revision ID: 008_brand_packaging
Revises: 007_project_telegram_bot_id
"""

from alembic import op
import sqlalchemy as sa

revision = "008_brand_packaging"
down_revision = "007_project_telegram_bot_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("brands", sa.Column("coverage_sqm_per_liter", sa.Float(), server_default="10", nullable=False))
    op.add_column("brands", sa.Column("recommended_coats", sa.Integer(), server_default="2", nullable=False))

    op.add_column("colors", sa.Column("tint_base", sa.String(1), nullable=True))
    op.add_column("colors", sa.Column("base_surcharge_percent", sa.Float(), server_default="0", nullable=False))

    op.add_column("leads", sa.Column("paint_plan_summary", sa.Text(), nullable=True))

    op.create_table(
        "brand_pack_sizes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("volume_liters", sa.Float(), nullable=False),
        sa.Column("price_uah", sa.Float(), nullable=False),
        sa.Column("label", sa.String(50), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_brand_pack_sizes_brand", "brand_pack_sizes", ["brand_id", "active"])


def downgrade() -> None:
    op.drop_index("ix_brand_pack_sizes_brand", table_name="brand_pack_sizes")
    op.drop_table("brand_pack_sizes")
    op.drop_column("leads", "paint_plan_summary")
    op.drop_column("colors", "base_surcharge_percent")
    op.drop_column("colors", "tint_base")
    op.drop_column("brands", "recommended_coats")
    op.drop_column("brands", "coverage_sqm_per_liter")
