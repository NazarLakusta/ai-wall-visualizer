"""Add editor_mode to projects

Revision ID: 010_project_editor_mode
Revises: 009_brand_paint_finish
"""

from alembic import op
import sqlalchemy as sa

revision = "010_project_editor_mode"
down_revision = "009_brand_paint_finish"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("editor_mode", sa.String(10), server_default="paint", nullable=True),
    )
    op.execute(
        """
        UPDATE projects
        SET editor_mode = 'decor'
        WHERE selected_material_id IS NOT NULL OR selected_decor_color_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("projects", "editor_mode")
