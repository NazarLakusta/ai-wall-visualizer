"""store business hours for customer lead acknowledgements

Revision ID: 016_store_business_hours
Revises: 015_store_brand_pack_prices
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "016_store_business_hours"
down_revision: str | None = "015_store_brand_pack_prices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("business_open_time", sa.String(5), server_default="09:00", nullable=False))
    op.add_column("stores", sa.Column("business_close_time", sa.String(5), server_default="19:00", nullable=False))
    op.add_column(
        "stores",
        sa.Column("business_timezone", sa.String(64), server_default="Europe/Kyiv", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("stores", "business_timezone")
    op.drop_column("stores", "business_close_time")
    op.drop_column("stores", "business_open_time")
