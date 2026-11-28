"""0004 shop marketplace OAuth connections and reply external sync status.

Revision ID: 0004_marketplace_connections
Revises: 0003_security_audit_and_keys
Create Date: 2026-11-24
"""

from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "0004_marketplace_connections"
down_revision = "0003_security_audit_and_keys"
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
        CREATE TABLE IF NOT EXISTS shop_marketplace_connections (
            id {id_type},
            scenario_tag TEXT NOT NULL,
            platform TEXT NOT NULL,
            external_shop_id TEXT NOT NULL,
            shop_name TEXT,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            token_expires_at TEXT,
            refresh_expires_at TEXT,
            auto_sync_enabled INTEGER NOT NULL DEFAULT 1,
            sync_interval_minutes INTEGER NOT NULL DEFAULT 30,
            last_synced_at TEXT,
            last_sync_status TEXT NOT NULL DEFAULT 'NEVER',
            last_sync_error TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE (scenario_tag, platform)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_mp_conn_active "
        "ON shop_marketplace_connections(is_active, auto_sync_enabled, platform)"
    )

    if not _has_column("review_replies", "external_sync_status"):
        op.execute(
            "ALTER TABLE review_replies "
            "ADD COLUMN external_sync_status TEXT NOT NULL DEFAULT 'LOCAL_ONLY'"
        )
    if not _has_column("review_replies", "external_sync_error"):
        op.execute("ALTER TABLE review_replies ADD COLUMN external_sync_error TEXT")
    if not _has_column("review_replies", "external_synced_at"):
        op.execute("ALTER TABLE review_replies ADD COLUMN external_synced_at TEXT")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS shop_marketplace_connections")


# CreBy: MenBoyBMN
