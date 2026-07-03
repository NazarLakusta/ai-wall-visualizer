"""decorative material volume-based pack sizing

Revision ID: 022_decor_volume_packs
Revises: 021_backfill_brand_descriptions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "022_decor_volume_packs"
down_revision: str | None = "021_backfill_brand_descriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "decorative_materials",
        sa.Column("pack_sizing_mode", sa.String(10), server_default="area", nullable=False),
    )
    op.add_column(
        "decorative_materials",
        sa.Column("coverage_sqm_per_liter", sa.Float(), nullable=True),
    )
    op.add_column(
        "decorative_material_pack_sizes",
        sa.Column("volume_liters", sa.Float(), nullable=True),
    )
    op.add_column(
        "decorative_material_pack_sizes",
        sa.Column("weight_kg", sa.Float(), nullable=True),
    )
    op.alter_column(
        "decorative_material_pack_sizes",
        "coverage_sqm",
        existing_type=sa.Float(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "decorative_material_pack_sizes",
        "coverage_sqm",
        existing_type=sa.Float(),
        nullable=False,
    )
    op.drop_column("decorative_material_pack_sizes", "weight_kg")
    op.drop_column("decorative_material_pack_sizes", "volume_liters")
    op.drop_column("decorative_materials", "coverage_sqm_per_liter")
    op.drop_column("decorative_materials", "pack_sizing_mode")
