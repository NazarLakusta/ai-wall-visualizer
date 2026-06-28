"""Add in_stock flags for colors and decorative items

Revision ID: 004_in_stock
Revises: 003_leads_group
"""

from alembic import op
import sqlalchemy as sa

revision = "004_in_stock"
down_revision = "003_leads_group"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "colors",
        sa.Column("in_stock", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "decorative_materials",
        sa.Column("in_stock", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "decorative_colors",
        sa.Column("in_stock", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("decorative_colors", "in_stock")
    op.drop_column("decorative_materials", "in_stock")
    op.drop_column("colors", "in_stock")
