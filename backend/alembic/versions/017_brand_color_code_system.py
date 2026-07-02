"""brand color code system (RAL / NCS / manufacturer)

Revision ID: 017_brand_color_code_system
Revises: 016_store_business_hours
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "017_brand_color_code_system"
down_revision: str | None = "016_store_business_hours"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "brands",
        sa.Column("color_code_system", sa.String(20), server_default="manufacturer", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("brands", "color_code_system")
