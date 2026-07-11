"""store decor catalog toggle

Revision ID: 023_store_decor_enabled
Revises: 022_decor_volume_packs
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "023_store_decor_enabled"
down_revision: str | None = "022_decor_volume_packs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stores",
        sa.Column("decor_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("stores", "decor_enabled")
