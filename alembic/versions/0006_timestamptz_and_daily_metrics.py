"""0006 normalize review created_at_ts (TIMESTAMPTZ) and add daily_aspect_metrics.

Revision ID: 0006_timestamptz_and_daily_metrics
Revises: 0005_variation_and_anomaly_flags
Create Date: 2026-11-24
"""

from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "0006_timestamptz_and_daily_metrics"
down_revision = "0005_variation_and_anomaly_flags"
branch_labels = None
depends_on = None


def _has_column(table_name: str, col_name: str) -> bool:
    insp = inspect(op.get_bind())
    return any(c["name"] == col_name for c in insp.get_columns(table_name))


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if not _has_column("reviews", "created_at_ts"):
        col_type = "TIMESTAMPTZ" if dialect == "postgresql" else "TEXT"
        op.execute(f"ALTER TABLE reviews ADD COLUMN created_at_ts {col_type}")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_aspect_metrics (
            scenario_tag TEXT NOT NULL,
            metric_date  TEXT NOT NULL,
            platform     TEXT NOT NULL DEFAULT 'all',
            aspect       TEXT NOT NULL,
            pos_count    INTEGER NOT NULL DEFAULT 0,
            neg_count    INTEGER NOT NULL DEFAULT 0,
            neu_count    INTEGER NOT NULL DEFAULT 0,
            total_count  INTEGER NOT NULL DEFAULT 0,
            updated_at   TEXT,
            PRIMARY KEY (scenario_tag, metric_date, platform, aspect)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_reviews_scenario_created_ts "
        "ON reviews(scenario_tag, created_at_ts)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_daily_metrics_scenario_date "
        "ON daily_aspect_metrics(scenario_tag, metric_date, aspect)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_daily_metrics_scenario_date")
    op.execute("DROP INDEX IF EXISTS idx_reviews_scenario_created_ts")
    op.execute("DROP TABLE IF EXISTS daily_aspect_metrics")


# CreBy: MenBoyBMN
