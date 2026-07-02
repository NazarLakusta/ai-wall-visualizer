"""color palettes separate from paint products

Revision ID: 018_color_palettes
Revises: 017_brand_color_code_system
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "018_color_palettes"
down_revision: str | None = "017_brand_color_code_system"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "color_palettes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("code_system", sa.String(20), server_default="manufacturer", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "brand_palettes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("palette_id", sa.Integer(), sa.ForeignKey("color_palettes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("brand_id", "palette_id", name="uq_brand_palettes_brand_palette"),
    )
    op.create_index("ix_brand_palettes_brand", "brand_palettes", ["brand_id"])

    op.add_column("colors", sa.Column("palette_id", sa.Integer(), sa.ForeignKey("color_palettes.id"), nullable=True))
    op.create_index("ix_colors_palette_category_active", "colors", ["palette_id", "category", "active"])

    op.add_column("projects", sa.Column("selected_brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=True))

    op.alter_column("colors", "brand_id", existing_type=sa.Integer(), nullable=True)

    conn = op.get_bind()
    brands = conn.execute(
        sa.text(
            """
            SELECT DISTINCT b.id, b.name, COALESCE(b.color_code_system, 'manufacturer') AS code_system
            FROM brands b
            JOIN colors c ON c.brand_id = b.id
            """
        )
    ).fetchall()

    for brand_id, brand_name, code_system in brands:
        palette_name = f"{brand_name} — палітра"
        palette_id = conn.execute(
            sa.text(
                """
                INSERT INTO color_palettes (name, code_system, active)
                VALUES (:name, :code_system, true)
                RETURNING id
                """
            ),
            {"name": palette_name, "code_system": code_system},
        ).scalar_one()
        conn.execute(
            sa.text("UPDATE colors SET palette_id = :palette_id WHERE brand_id = :brand_id"),
            {"palette_id": palette_id, "brand_id": brand_id},
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO brand_palettes (brand_id, palette_id)
                VALUES (:brand_id, :palette_id)
                ON CONFLICT DO NOTHING
                """
            ),
            {"brand_id": brand_id, "palette_id": palette_id},
        )

    conn.execute(sa.text("UPDATE colors SET brand_id = NULL WHERE palette_id IS NOT NULL"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE colors c
            SET brand_id = bp.brand_id
            FROM brand_palettes bp
            WHERE c.palette_id = bp.palette_id AND c.brand_id IS NULL
            """
        )
    )

    op.drop_column("projects", "selected_brand_id")
    op.drop_index("ix_colors_palette_category_active", table_name="colors")
    op.drop_column("colors", "palette_id")
    op.drop_index("ix_brand_palettes_brand", table_name="brand_palettes")
    op.drop_table("brand_palettes")
    op.drop_table("color_palettes")
