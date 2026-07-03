"""brand customer-facing description for mini-app hints

Revision ID: 020_brand_description
Revises: 019_brand_pack_tint_base
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "020_brand_description"
down_revision: str | None = "019_brand_pack_tint_base"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("brands", sa.Column("description", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("brands", "description")
