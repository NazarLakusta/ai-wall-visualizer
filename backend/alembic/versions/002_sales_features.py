"""Store contacts, pricing, leads, project tracking

Revision ID: 002_sales
Revises: 001_initial
Create Date: 2026-06-25
"""

from alembic import op
import sqlalchemy as sa

revision = "002_sales"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("stores", sa.Column("address", sa.String(500), nullable=True))
    op.add_column("stores", sa.Column("telegram_username", sa.String(100), nullable=True))
    op.add_column("stores", sa.Column("manager_telegram_chat_id", sa.BigInteger(), nullable=True))

    op.add_column("colors", sa.Column("price_per_sqm", sa.Float(), nullable=True))
    op.add_column("decorative_colors", sa.Column("price_per_sqm", sa.Float(), nullable=True))

    op.add_column("projects", sa.Column("wall_area_sqm", sa.Float(), nullable=True))
    op.add_column("projects", sa.Column("editor_opens", sa.Integer(), server_default="0", nullable=False))
    op.add_column("projects", sa.Column("selected_color_id", sa.Integer(), nullable=True))
    op.add_column("projects", sa.Column("selected_decor_color_id", sa.Integer(), nullable=True))
    op.add_column("projects", sa.Column("selected_material_id", sa.Integer(), nullable=True))
    op.add_column("projects", sa.Column("selected_finish", sa.String(20), nullable=True))
    op.add_column("projects", sa.Column("result_image", sa.String(500), nullable=True))

    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("wall_area_sqm", sa.Float(), nullable=True),
        sa.Column("estimated_total_uah", sa.Float(), nullable=True),
        sa.Column("selection_summary", sa.String(500), nullable=True),
        sa.Column(
            "status",
            sa.Enum("new", "contacted", "closed", name="leadstatus"),
            server_default="new",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_leads_store_status", "leads", ["store_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_leads_store_status", table_name="leads")
    op.drop_table("leads")
    op.drop_column("projects", "result_image")
    op.drop_column("projects", "selected_finish")
    op.drop_column("projects", "selected_material_id")
    op.drop_column("projects", "selected_decor_color_id")
    op.drop_column("projects", "selected_color_id")
    op.drop_column("projects", "editor_opens")
    op.drop_column("projects", "wall_area_sqm")
    op.drop_column("decorative_colors", "price_per_sqm")
    op.drop_column("colors", "price_per_sqm")
    op.drop_column("stores", "manager_telegram_chat_id")
    op.drop_column("stores", "telegram_username")
    op.drop_column("stores", "address")
    op.drop_column("stores", "phone")
    op.execute("DROP TYPE IF EXISTS leadstatus")
