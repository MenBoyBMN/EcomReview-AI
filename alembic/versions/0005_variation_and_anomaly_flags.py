"""0005 add product variation and anomaly_flags columns to reviews.

Revision ID: 0005_variation_and_anomaly_flags
Revises: 0004_marketplace_connections
Create Date: 2026-11-24
"""

from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "0005_variation_and_anomaly_flags"
down_revision = "0004_marketplace_connections"
branch_labels = None
depends_on = None


def _has_column(table_name: str, col_name: str) -> bool:
    insp = inspect(op.get_bind())
    return any(c["name"] == col_name for c in insp.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("reviews", "variation"):
        op.execute("ALTER TABLE reviews ADD COLUMN variation TEXT NOT NULL DEFAULT ''")
    if not _has_column("reviews", "anomaly_flags"):
        op.execute("ALTER TABLE reviews ADD COLUMN anomaly_flags TEXT NOT NULL DEFAULT '[]'")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_reviews_scenario_product_var "
        "ON reviews(scenario_tag, product, variation)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_reviews_scenario_product_var")


# CreBy: MenBoyBMN
