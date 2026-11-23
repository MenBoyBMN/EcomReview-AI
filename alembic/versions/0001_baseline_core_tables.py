"""0001 baseline core tables (idempotent for existing deployments).

Revision ID: 0001_baseline_core_tables
Revises:
Create Date: 2026-11-23
"""

from __future__ import annotations

from alembic import op

revision = "0001_baseline_core_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    id_type = (
        "SERIAL PRIMARY KEY" if dialect == "postgresql" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )
    big_id_type = (
        "BIGSERIAL PRIMARY KEY" if dialect == "postgresql" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            review_id TEXT NOT NULL,
            scenario_tag TEXT NOT NULL DEFAULT 'real_shop',
            platform TEXT NOT NULL DEFAULT 'tiktok',
            shop TEXT NOT NULL DEFAULT 'shop_a',
            product TEXT NOT NULL DEFAULT 'ao_mua_da_ca',
            rating INTEGER CHECK (rating BETWEEN 1 AND 5),
            text_raw TEXT NOT NULL,
            text_norm TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'review',
            overall_sentiment TEXT,
            informative INTEGER DEFAULT 1,
            created_at TEXT,
            imported_at TEXT,
            PRIMARY KEY (review_id, scenario_tag)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS opinions (
            id {big_id_type},
            review_id TEXT NOT NULL,
            scenario_tag TEXT NOT NULL DEFAULT 'real_shop',
            aspect TEXT NOT NULL,
            polarity TEXT NOT NULL,
            evidence TEXT NOT NULL,
            evidence_ok INTEGER NOT NULL DEFAULT 1,
            analyzer_method TEXT NOT NULL DEFAULT 'gemini_v2',
            created_at TEXT,
            FOREIGN KEY (review_id, scenario_tag)
                REFERENCES reviews(review_id, scenario_tag) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS insights (
            id {id_type},
            scenario_tag TEXT NOT NULL DEFAULT 'real_shop',
            kind TEXT NOT NULL,
            aspect TEXT,
            statement TEXT NOT NULL,
            numbers TEXT NOT NULL,
            evidence_ids TEXT NOT NULL,
            confidence TEXT NOT NULL,
            run_id TEXT,
            is_archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS actions (
            id {id_type},
            scenario_tag TEXT NOT NULL DEFAULT 'real_shop',
            action_type TEXT NOT NULL,
            is_marketing INTEGER NOT NULL DEFAULT 1,
            title TEXT NOT NULL,
            what_to_do TEXT NOT NULL,
            why_rationale TEXT NOT NULL,
            how_and_when TEXT NOT NULL,
            success_metric TEXT NOT NULL,
            effort TEXT NOT NULL,
            impact TEXT NOT NULL,
            priority_score REAL NOT NULL DEFAULT 0.0,
            insight_ids TEXT NOT NULL,
            evidence_review_ids TEXT NOT NULL,
            critic_passed INTEGER NOT NULL DEFAULT 1,
            critic_trace TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            run_id TEXT,
            is_archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS action_feedback (
            id {id_type},
            action_id INTEGER NOT NULL REFERENCES actions(id) ON DELETE CASCADE,
            decision TEXT NOT NULL,
            reason_category TEXT,
            note TEXT,
            edited_content TEXT,
            decided_by TEXT,
            decided_at TEXT
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS review_replies (
            id {id_type},
            review_id TEXT NOT NULL,
            scenario_tag TEXT NOT NULL DEFAULT 'real_shop',
            reply_text TEXT NOT NULL,
            mode_used TEXT NOT NULL DEFAULT 'template',
            guardrail_passed INTEGER NOT NULL DEFAULT 1,
            violations TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'DRAFT',
            created_by TEXT,
            created_at TEXT,
            sent_at TEXT,
            FOREIGN KEY (review_id, scenario_tag)
                REFERENCES reviews(review_id, scenario_tag) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS system_jobs_audit (
            id {id_type},
            job_type TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            created_at TEXT,
            completed_at TEXT
        )
        """
    )


def downgrade() -> None:
    pass


# CreBy: MenBoyBMN
