"""0003 scoped shop API keys, audit logs, refresh tokens, and user token_version.

Revision ID: 0003_security_audit_and_keys
Revises: 0002_pilot_auth_shops_alerts
Create Date: 2026-11-24
"""

from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "0003_security_audit_and_keys"
down_revision = "0002_pilot_auth_shops_alerts"
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

    if not _has_column("users", "token_version"):
        op.execute("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 1")

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS shop_api_keys (
            id {id_type},
            scenario_tag TEXT NOT NULL,
            name TEXT NOT NULL,
            key_prefix TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL DEFAULT 'owner',
            scopes TEXT NOT NULL DEFAULT '["read","write"]',
            created_by TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            last_used_at TEXT,
            revoked_at TEXT
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id {id_type},
            actor TEXT NOT NULL,
            actor_role TEXT NOT NULL DEFAULT 'system',
            action TEXT NOT NULL,
            scenario_tag TEXT,
            target_type TEXT,
            target_id TEXT,
            ip_address TEXT,
            request_id TEXT,
            details TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id {id_type},
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            family_id TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            replaced_by_hash TEXT,
            created_at TEXT
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_shop_api_keys_scenario "
        "ON shop_api_keys(scenario_tag, is_active)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_scenario_created "
        "ON audit_logs(scenario_tag, created_at)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor, created_at)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id, revoked_at)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_family ON refresh_tokens(family_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS refresh_tokens")
    op.execute("DROP TABLE IF EXISTS audit_logs")
    op.execute("DROP TABLE IF EXISTS shop_api_keys")


# CreBy: MenBoyBMN
