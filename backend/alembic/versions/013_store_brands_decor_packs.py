"""store brands isolation and decorative material pack sizes

Revision ID: 013_store_brands_decor_packs
Revises: 012_store_crew_chat
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013_store_brands_decor_packs"
down_revision: str | None = "012_store_crew_chat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_brands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("store_id", "brand_id", name="uq_store_brands_store_brand"),
    )
    op.create_index("ix_store_brands_store_active", "store_brands", ["store_id", "active"])

    op.execute(
        """
        INSERT INTO store_brands (store_id, brand_id, active)
        SELECT DISTINCT sc.store_id, c.brand_id, true
        FROM store_colors sc
        JOIN colors c ON c.id = sc.color_id
        """
    )

    op.create_table(
        "decorative_material_pack_sizes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "material_id",
            sa.Integer(),
            sa.ForeignKey("decorative_materials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("coverage_sqm", sa.Float(), nullable=False),
        sa.Column("price_uah", sa.Float(), nullable=False),
        sa.Column("label", sa.String(50), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_decor_material_packs_material",
        "decorative_material_pack_sizes",
        ["material_id", "active"],
    )

    op.add_column(
        "decorative_materials",
        sa.Column("recommended_coats", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("decorative_materials", "recommended_coats")
    op.drop_index("ix_decor_material_packs_material", table_name="decorative_material_pack_sizes")
    op.drop_table("decorative_material_pack_sizes")
    op.drop_index("ix_store_brands_store_active", table_name="store_brands")
    op.drop_table("store_brands")
