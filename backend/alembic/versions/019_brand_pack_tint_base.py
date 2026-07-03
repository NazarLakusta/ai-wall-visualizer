"""pack size tint base for KROINZ Base A / Base C pricing

Revision ID: 019_brand_pack_tint_base
Revises: 018_color_palettes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "019_brand_pack_tint_base"
down_revision: str | None = "018_color_palettes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("brand_pack_sizes", sa.Column("tint_base", sa.String(1), nullable=True))


def downgrade() -> None:
    op.drop_column("brand_pack_sizes", "tint_base")
