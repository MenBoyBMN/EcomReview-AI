"""0007 add tenant_subscriptions and usage_monthly tables for SaaS quota metering.

Revision ID: 0007_subscriptions_and_usage
Revises: 0006_timestamptz_and_daily_metrics
Create Date: 2026-11-24
"""

from __future__ import annotations

from alembic import op

revision = "0007_subscriptions_and_usage"
down_revision = "0006_timestamptz_and_daily_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    id_col = (
        "SERIAL PRIMARY KEY" if dialect == "postgresql" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS tenant_subscriptions (
            id                       {id_col},
            tenant_key               TEXT NOT NULL UNIQUE,
            plan_code                TEXT NOT NULL DEFAULT 'basic',
            status                   TEXT NOT NULL DEFAULT 'ACTIVE',
            monthly_llm_review_limit INTEGER NOT NULL DEFAULT 2000,
            max_shops                INTEGER NOT NULL DEFAULT 2,
            max_users                INTEGER NOT NULL DEFAULT 3,
            overage_policy           TEXT NOT NULL DEFAULT 'fallback_b1',
            trial_ends_at            TEXT,
            notes                    TEXT,
            updated_by               TEXT,
            created_at               TEXT,
            updated_at               TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_monthly (
            scenario_tag      TEXT NOT NULL,
            month_key         TEXT NOT NULL,
            llm_reviews_used  INTEGER NOT NULL DEFAULT 0,
            rule_reviews_used INTEGER NOT NULL DEFAULT 0,
            replies_generated INTEGER NOT NULL DEFAULT 0,
            updated_at        TEXT,
            PRIMARY KEY (scenario_tag, month_key)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_tenant_subs_key ON tenant_subscriptions(tenant_key)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_usage_monthly_month "
        "ON usage_monthly(month_key, scenario_tag)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_usage_monthly_month")
    op.execute("DROP INDEX IF EXISTS idx_tenant_subs_key")
    op.execute("DROP TABLE IF EXISTS usage_monthly")
    op.execute("DROP TABLE IF EXISTS tenant_subscriptions")


# CreBy: MenBoyBMN
