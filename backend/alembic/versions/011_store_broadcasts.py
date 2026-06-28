"""Add store_broadcasts table

Revision ID: 011_store_broadcasts
Revises: 010_project_editor_mode
"""

from alembic import op
import sqlalchemy as sa

revision = "011_store_broadcasts"
down_revision = "010_project_editor_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "store_broadcasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("created_by_admin_id", sa.Integer(), sa.ForeignKey("store_admins.id"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("image_path", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), server_default="queued", nullable=False),
        sa.Column("total_recipients", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sent_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_store_broadcasts_store_created", "store_broadcasts", ["store_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_store_broadcasts_store_created", table_name="store_broadcasts")
    op.drop_table("store_broadcasts")
