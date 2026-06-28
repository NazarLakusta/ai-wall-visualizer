"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("telegram_bot_token", sa.String(255), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.String(255)),
        sa.Column("first_name", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "brands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("logo", sa.String(500)),
        sa.Column("country", sa.String(100)),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "store_admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("owner", "editor", name="adminrole"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("original_image", sa.String(500)),
        sa.Column("mask_image", sa.String(500)),
        sa.Column("illumination_image", sa.String(500)),
        sa.Column("specular_image", sa.String(500)),
        sa.Column("status", sa.Enum("received", "queued", "processing", "ready", "error", name="projectstatus"), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("telegram_chat_id", sa.BigInteger()),
        sa.Column("telegram_message_id", sa.BigInteger()),
        sa.Column("is_test", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_status_expires", "projects", ["status", "expires_at"])
    op.create_table(
        "colors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hex", sa.String(7), nullable=False),
        sa.Column("manufacturer_code", sa.String(100)),
        sa.Column("category", sa.Enum(
            "Білі", "Сірі", "Бежеві", "Коричневі", "Зелені", "Сині",
            "Жовті", "Червоні", "Темні", "Пастельні", name="colorcategory"
        ), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_colors_brand_category_active", "colors", ["brand_id", "category", "active"])
    op.create_table(
        "decorative_materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id")),
        sa.Column("category", sa.String(100)),
        sa.Column("texture_file", sa.String(500)),
        sa.Column("preview_image", sa.String(500)),
        sa.Column("texture_scale", sa.Float(), server_default="1.0"),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_decorative_materials_store_active", "decorative_materials", ["store_id", "active"])
    op.create_table(
        "decorative_colors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("decorative_materials.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hex", sa.String(7), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("decorative_colors")
    op.drop_table("decorative_materials")
    op.drop_table("colors")
    op.drop_table("projects")
    op.drop_table("store_admins")
    op.drop_table("brands")
    op.drop_table("users")
    op.drop_table("stores")
    op.execute("DROP TYPE IF EXISTS adminrole")
    op.execute("DROP TYPE IF EXISTS projectstatus")
    op.execute("DROP TYPE IF EXISTS colorcategory")
