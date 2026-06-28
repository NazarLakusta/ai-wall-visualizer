"""Add paint_finish to brands (product line finish)

Revision ID: 009_brand_paint_finish
Revises: 008_brand_packaging
"""

from alembic import op
import sqlalchemy as sa

revision = "009_brand_paint_finish"
down_revision = "008_brand_packaging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "brands",
        sa.Column("paint_finish", sa.String(20), server_default="matte", nullable=False),
    )
    op.execute("UPDATE brands SET paint_finish = 'matte' WHERE name IN ('Latex Matt', 'Innen Latex', 'Koala', 'Demo Brand')")
    op.execute("UPDATE brands SET paint_finish = 'silk_matte' WHERE name = 'Innen Wunder'")


def downgrade() -> None:
    op.drop_column("brands", "paint_finish")
