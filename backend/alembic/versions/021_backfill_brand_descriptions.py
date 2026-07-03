"""Backfill customer-facing descriptions for existing KROINZ products.

Revision ID: 021_backfill_brand_descriptions
Revises: 020_brand_description
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "021_backfill_brand_descriptions"
down_revision: str | None = "020_brand_description"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DESCRIPTIONS: dict[str, str] = {
    "KROINZ Latex Matt": "Основна латексна матова — універсальна для стін і стелі.",
    "KROINZ Innen Wunder": "Матова латексна економ-клас — зазвичай дешевше за Latex Matt.",
    "KROINZ Seidenmatt Farbe": "Шовковисто-матова — приємний блиск, легше мити.",
    "KROINZ ExtraWeiße Waschbare": "Стійка до миття. Білу можна колерувати в RAL.",
    "KROINZ Eco White": "Готова біла фарба — без колерування, лише білий відтінок.",
}


def upgrade() -> None:
    conn = op.get_bind()
    for name, description in DESCRIPTIONS.items():
        conn.execute(
            sa.text(
                """
                UPDATE brands
                SET description = :description
                WHERE name = :name
                  AND (description IS NULL OR btrim(description) = '')
                """
            ),
            {"name": name, "description": description},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for name, description in DESCRIPTIONS.items():
        conn.execute(
            sa.text(
                """
                UPDATE brands
                SET description = NULL
                WHERE name = :name AND description = :description
                """
            ),
            {"name": name, "description": description},
        )
