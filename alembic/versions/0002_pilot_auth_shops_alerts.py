"""0002 pilot auth, shops, alert dispatches, implemented_at & indexes.

Revision ID: 0002_pilot_auth_shops_alerts
Revises: 0001_baseline_core_tables
Create Date: 2026-11-23
"""

from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "0002_pilot_auth_shops_alerts"
down_revision = "0001_baseline_core_tables"
branch_labels = None
depends_on = None


def _has_column(table_name: str, col_name: str) -> bool:
    insp = inspect(op.get_bind())
    return any(c["name"] == col_name for c in insp.get_columns(table_name))


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    id_type = (
        "SERIAL PRIMARY KEY" if dialect == "postgresql" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS pilot_shops (
            id {id_type},
            slug TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            industry TEXT NOT NULL DEFAULT 'raincoat',
            platforms TEXT NOT NULL DEFAULT '["shopee","tiktok"]',
            alert_config TEXT NOT NULL DEFAULT '{{}}',
            webhook_secret TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS users (
            id {id_type},
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'owner',
            allowed_shops TEXT NOT NULL DEFAULT '[]',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            last_login_at TEXT
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS alert_dispatches (
            id {id_type},
            scenario_tag TEXT NOT NULL,
            dedup_key TEXT NOT NULL UNIQUE,
            channel TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'MEDIUM',
            title TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'SENT',
            error_message TEXT,
            created_at TEXT,
            sent_at TEXT
        )
        """
    )

    if not _has_column("actions", "implemented_at"):
        op.execute("ALTER TABLE actions ADD COLUMN implemented_at TEXT")
    if not _has_column("system_jobs_audit", "scenario_tag"):
        op.execute("ALTER TABLE system_jobs_audit ADD COLUMN scenario_tag TEXT")

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_reviews_scenario_created "
        "ON reviews(scenario_tag, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_reviews_scenario_rating ON reviews(scenario_tag, rating)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_alert_dispatches_scenario "
        "ON alert_dispatches(scenario_tag, status)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_scenario ON system_jobs_audit(scenario_tag)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS alert_dispatches")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TABLE IF EXISTS pilot_shops")


# CreBy: MenBoyBMN
