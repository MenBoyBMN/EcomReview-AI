"""Database connection, schema initialization, and repository helpers.

Supports PostgreSQL 16 (production/Docker) and automatic SQLite fallback (local dev/testing)
with strict READ-ONLY connection mode enforcement for AI Agent tools.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ecomreview.crypto import decrypt_secret, encrypt_secret

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

try:
    from psycopg_pool import ConnectionPool
except ImportError:
    ConnectionPool = None

logger = logging.getLogger(__name__)

DEFAULT_SQLITE_PATH = Path("data/ecomreview.db")

_INITIALIZED_TARGETS: set[str] = set()
_INIT_LOCK = threading.Lock()
_PG_POOLS: dict[tuple[str, bool], Any] = {}
_POOL_LOCK = threading.Lock()

SQLITE_INIT_SCRIPT = """
CREATE TABLE IF NOT EXISTS reviews (
    review_id         TEXT NOT NULL,
    scenario_tag      TEXT NOT NULL DEFAULT 'real_shop',
    platform          TEXT NOT NULL DEFAULT 'tiktok',
    shop              TEXT NOT NULL DEFAULT 'shop_a',
    product           TEXT NOT NULL DEFAULT 'ao_mua_da_ca',
    rating            INTEGER CHECK (rating BETWEEN 1 AND 5),
    text_raw          TEXT NOT NULL,
    text_norm         TEXT NOT NULL,
    source            TEXT NOT NULL DEFAULT 'review',
    overall_sentiment TEXT,
    informative       INTEGER DEFAULT 1,
    created_at        TEXT,
    created_at_ts     TEXT,
    imported_at       TEXT,
    variation         TEXT NOT NULL DEFAULT '',
    anomaly_flags     TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (review_id, scenario_tag)
);

CREATE TABLE IF NOT EXISTS opinions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id         TEXT NOT NULL,
    scenario_tag      TEXT NOT NULL DEFAULT 'real_shop',
    aspect            TEXT NOT NULL,
    polarity          TEXT NOT NULL,
    evidence          TEXT NOT NULL,
    evidence_ok       INTEGER NOT NULL DEFAULT 1,
    analyzer_method   TEXT NOT NULL DEFAULT 'gemini_v2',
    created_at        TEXT,
    FOREIGN KEY (review_id, scenario_tag)
        REFERENCES reviews(review_id, scenario_tag) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS insights (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_tag      TEXT NOT NULL DEFAULT 'real_shop',
    kind              TEXT NOT NULL,
    aspect            TEXT,
    statement         TEXT NOT NULL,
    numbers           TEXT NOT NULL,
    evidence_ids      TEXT NOT NULL,
    confidence        TEXT NOT NULL,
    run_id            TEXT,
    is_archived       INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT
);

CREATE TABLE IF NOT EXISTS actions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_tag        TEXT NOT NULL DEFAULT 'real_shop',
    action_type         TEXT NOT NULL,
    is_marketing        INTEGER NOT NULL DEFAULT 1,
    title               TEXT NOT NULL,
    what_to_do          TEXT NOT NULL,
    why_rationale       TEXT NOT NULL,
    how_and_when        TEXT NOT NULL,
    success_metric      TEXT NOT NULL,
    effort              TEXT NOT NULL,
    impact              TEXT NOT NULL,
    priority_score      REAL NOT NULL DEFAULT 0.0,
    insight_ids         TEXT NOT NULL,
    evidence_review_ids TEXT NOT NULL,
    critic_passed       INTEGER NOT NULL DEFAULT 1,
    critic_trace        TEXT,
    status              TEXT NOT NULL DEFAULT 'PENDING',
    run_id              TEXT,
    is_archived         INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT
);

CREATE TABLE IF NOT EXISTS action_feedback (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id         INTEGER NOT NULL,
    decision          TEXT NOT NULL,
    reason_category   TEXT,
    note              TEXT,
    edited_content    TEXT,
    decided_by        TEXT,
    decided_at        TEXT,
    FOREIGN KEY (action_id) REFERENCES actions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS review_replies (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id            TEXT NOT NULL,
    scenario_tag         TEXT NOT NULL DEFAULT 'real_shop',
    reply_text           TEXT NOT NULL,
    mode_used            TEXT NOT NULL DEFAULT 'template',
    guardrail_passed     INTEGER NOT NULL DEFAULT 1,
    violations           TEXT NOT NULL DEFAULT '[]',
    status               TEXT NOT NULL DEFAULT 'DRAFT',
    created_by           TEXT,
    created_at           TEXT,
    sent_at              TEXT,
    external_sync_status TEXT NOT NULL DEFAULT 'LOCAL_ONLY',
    external_sync_error  TEXT,
    external_synced_at   TEXT,
    FOREIGN KEY (review_id, scenario_tag)
        REFERENCES reviews(review_id, scenario_tag) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS system_jobs_audit (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type          TEXT NOT NULL,
    scenario_tag      TEXT,
    status            TEXT NOT NULL,
    details           TEXT,
    created_at        TEXT,
    completed_at      TEXT
);

CREATE TABLE IF NOT EXISTS pilot_shops (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slug              TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    industry          TEXT NOT NULL DEFAULT 'raincoat',
    platforms         TEXT NOT NULL DEFAULT '["shopee","tiktok"]',
    alert_config      TEXT NOT NULL DEFAULT '{}',
    webhook_secret    TEXT,
    is_active         INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    email             TEXT NOT NULL UNIQUE,
    password_hash     TEXT NOT NULL,
    full_name         TEXT NOT NULL,
    role              TEXT NOT NULL DEFAULT 'owner',
    allowed_shops     TEXT NOT NULL DEFAULT '[]',
    is_active         INTEGER NOT NULL DEFAULT 1,
    token_version     INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT,
    last_login_at     TEXT
);

CREATE TABLE IF NOT EXISTS alert_dispatches (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_tag      TEXT NOT NULL,
    dedup_key         TEXT NOT NULL UNIQUE,
    channel           TEXT NOT NULL,
    severity          TEXT NOT NULL DEFAULT 'MEDIUM',
    title             TEXT NOT NULL,
    payload           TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'SENT',
    error_message     TEXT,
    created_at        TEXT,
    sent_at           TEXT
);

CREATE TABLE IF NOT EXISTS shop_api_keys (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_tag      TEXT NOT NULL,
    name              TEXT NOT NULL,
    key_prefix        TEXT NOT NULL,
    key_hash          TEXT NOT NULL UNIQUE,
    role              TEXT NOT NULL DEFAULT 'owner',
    scopes            TEXT NOT NULL DEFAULT '["read","write"]',
    created_by        TEXT,
    is_active         INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT,
    last_used_at      TEXT,
    revoked_at        TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    actor             TEXT NOT NULL,
    actor_role        TEXT NOT NULL DEFAULT 'system',
    action            TEXT NOT NULL,
    scenario_tag      TEXT,
    target_type       TEXT,
    target_id         TEXT,
    ip_address        TEXT,
    request_id        TEXT,
    details           TEXT NOT NULL DEFAULT '{}',
    created_at        TEXT
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    token_hash        TEXT NOT NULL UNIQUE,
    family_id         TEXT NOT NULL,
    expires_at        TEXT NOT NULL,
    revoked_at        TEXT,
    replaced_by_hash  TEXT,
    created_at        TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS shop_marketplace_connections (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_tag          TEXT NOT NULL,
    platform              TEXT NOT NULL,
    external_shop_id      TEXT NOT NULL,
    shop_name             TEXT,
    access_token          TEXT NOT NULL,
    refresh_token         TEXT,
    token_expires_at      TEXT,
    refresh_expires_at    TEXT,
    auto_sync_enabled     INTEGER NOT NULL DEFAULT 1,
    sync_interval_minutes INTEGER NOT NULL DEFAULT 30,
    last_synced_at        TEXT,
    last_sync_status      TEXT NOT NULL DEFAULT 'NEVER',
    last_sync_error       TEXT,
    is_active             INTEGER NOT NULL DEFAULT 1,
    created_at            TEXT,
    updated_at            TEXT,
    UNIQUE (scenario_tag, platform)
);

CREATE INDEX IF NOT EXISTS idx_reviews_scenario ON reviews(scenario_tag, platform);
CREATE INDEX IF NOT EXISTS idx_reviews_scenario_created ON reviews(scenario_tag, created_at);
CREATE INDEX IF NOT EXISTS idx_reviews_scenario_rating ON reviews(scenario_tag, rating);
CREATE INDEX IF NOT EXISTS idx_opinions_aspect_pol ON opinions(scenario_tag, aspect, polarity);
CREATE INDEX IF NOT EXISTS idx_actions_scenario_status ON actions(scenario_tag, status);
CREATE INDEX IF NOT EXISTS idx_opinions_review ON opinions(scenario_tag, review_id);
CREATE INDEX IF NOT EXISTS idx_insights_scenario_kind ON insights(scenario_tag, kind);
CREATE INDEX IF NOT EXISTS idx_action_feedback_action_id ON action_feedback(action_id);
CREATE INDEX IF NOT EXISTS idx_review_replies_review ON review_replies(scenario_tag, review_id);
CREATE INDEX IF NOT EXISTS idx_alert_dispatches_scenario ON alert_dispatches(scenario_tag, status);
CREATE INDEX IF NOT EXISTS idx_shop_api_keys_scenario ON shop_api_keys(scenario_tag, is_active);
CREATE INDEX IF NOT EXISTS idx_audit_logs_scenario_created ON audit_logs(scenario_tag, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor, created_at);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id, revoked_at);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_family ON refresh_tokens(family_id);
CREATE INDEX IF NOT EXISTS idx_mp_conn_active
    ON shop_marketplace_connections(is_active, auto_sync_enabled, platform);

CREATE TABLE IF NOT EXISTS daily_aspect_metrics (
    scenario_tag      TEXT NOT NULL,
    metric_date       TEXT NOT NULL,
    platform          TEXT NOT NULL DEFAULT 'all',
    aspect            TEXT NOT NULL,
    pos_count         INTEGER NOT NULL DEFAULT 0,
    neg_count         INTEGER NOT NULL DEFAULT 0,
    neu_count         INTEGER NOT NULL DEFAULT 0,
    total_count       INTEGER NOT NULL DEFAULT 0,
    updated_at        TEXT,
    PRIMARY KEY (scenario_tag, metric_date, platform, aspect)
);

CREATE TABLE IF NOT EXISTS tenant_subscriptions (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
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
);

CREATE TABLE IF NOT EXISTS usage_monthly (
    scenario_tag      TEXT NOT NULL,
    month_key         TEXT NOT NULL,
    llm_reviews_used  INTEGER NOT NULL DEFAULT 0,
    rule_reviews_used INTEGER NOT NULL DEFAULT 0,
    replies_generated INTEGER NOT NULL DEFAULT 0,
    updated_at        TEXT,
    PRIMARY KEY (scenario_tag, month_key)
);

CREATE INDEX IF NOT EXISTS idx_tenant_subs_key ON tenant_subscriptions(tenant_key);
CREATE INDEX IF NOT EXISTS idx_usage_monthly_month ON usage_monthly(month_key, scenario_tag);
"""

_QMARK_RE = re.compile(r"\?")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_created_at_ts(raw_created_at: str | None, fallback_iso: str) -> str:
    """Normalize arbitrary date/datetime string into UTC ISO-8601 timestamp."""
    raw = str(raw_created_at or "").strip()
    if not raw:
        return fallback_iso
    if len(raw) == 10:
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat()
    except ValueError:
        return fallback_iso


def _extract_metric_date(raw_created_at: str | None) -> str:
    """Extract YYYY-MM-DD bucket or 'unknown' from a review created_at string."""
    val = str(raw_created_at or "").strip()
    return val[:10] if len(val) >= 10 else "unknown"


class _PgConnection:
    """Adapter exposing sqlite3-like execute() interface over a psycopg connection."""

    def __init__(self, conn: Any):
        self._conn = conn

    def cursor(self) -> Any:
        return self._conn.cursor(row_factory=dict_row)

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        cur = self._conn.cursor(row_factory=dict_row)
        if params:
            escaped_sql = sql.replace("%", "%%")
            pg_sql = _QMARK_RE.sub("%s", escaped_sql)
            cur.execute(pg_sql, tuple(params))
        else:
            cur.execute(sql)
        return cur

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


class DatabaseManager:
    """Unified Database Manager supporting Read-Write (API/Ingest) and Read-Only (Agent Tools)."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        db_backend: str | None = None,
        database_url: str | None = None,
        database_url_ro: str | None = None,
    ):
        backend = (db_backend or os.getenv("ECOMREVIEW_DB_BACKEND", "sqlite")).strip().lower()
        self.backend = backend
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self.database_url_ro = database_url_ro or os.getenv("DATABASE_URL_RO") or self.database_url

        env_path = os.getenv("ECOMREVIEW_SQLITE_PATH")
        self.db_path = Path(db_path or env_path or DEFAULT_SQLITE_PATH)
        if self.backend == "sqlite":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def init_db(self) -> None:
        """Initialize the 6 core tables and indexes (cached per process to prevent locking)."""
        target_key = (
            f"pg:{self.database_url}"
            if self.backend == "postgres"
            else f"sqlite:{self.db_path.resolve()}"
        )
        with _INIT_LOCK:
            if target_key in _INITIALIZED_TARGETS:
                return

            if self.backend == "postgres":
                if not psycopg:
                    raise ImportError("psycopg is required for PostgreSQL backend.")
                if not self.database_url:
                    raise ValueError("DATABASE_URL is required when backend is postgres.")
                init_sql_path = Path(__file__).resolve().parents[3] / "docker" / "db" / "init.sql"
                if not init_sql_path.exists():
                    init_sql_path = Path("docker/db/init.sql")
                if init_sql_path.exists():
                    sql_content = init_sql_path.read_text(encoding="utf-8")
                    with psycopg.connect(self.database_url) as conn:
                        with conn.cursor() as cur:
                            cur.execute(sql_content)
                        conn.commit()
                _INITIALIZED_TARGETS.add(target_key)
                return

            with closing(sqlite3.connect(self.db_path, timeout=30.0)) as conn:
                with conn:
                    conn.execute("PRAGMA journal_mode = WAL;")
                    conn.execute("PRAGMA synchronous = NORMAL;")
                    conn.execute("PRAGMA foreign_keys = ON;")
                    conn.executescript(SQLITE_INIT_SCRIPT)
                    migration_alters = (
                        "ALTER TABLE action_feedback ADD COLUMN decided_by TEXT",
                        "ALTER TABLE insights ADD COLUMN run_id TEXT",
                        "ALTER TABLE insights ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0",
                        "ALTER TABLE actions ADD COLUMN run_id TEXT",
                        "ALTER TABLE actions ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0",
                        "ALTER TABLE actions ADD COLUMN implemented_at TEXT",
                        "ALTER TABLE review_replies ADD COLUMN sent_at TEXT",
                        (
                            "ALTER TABLE review_replies ADD COLUMN external_sync_status "
                            "TEXT NOT NULL DEFAULT 'LOCAL_ONLY'"
                        ),
                        "ALTER TABLE review_replies ADD COLUMN external_sync_error TEXT",
                        "ALTER TABLE review_replies ADD COLUMN external_synced_at TEXT",
                        "ALTER TABLE system_jobs_audit ADD COLUMN scenario_tag TEXT",
                        "ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 1",
                        "ALTER TABLE reviews ADD COLUMN variation TEXT NOT NULL DEFAULT ''",
                        "ALTER TABLE reviews ADD COLUMN anomaly_flags TEXT NOT NULL DEFAULT '[]'",
                        "ALTER TABLE reviews ADD COLUMN created_at_ts TEXT",
                    )
                    for alter_sql in migration_alters:
                        try:
                            conn.execute(alter_sql)
                        except sqlite3.OperationalError:
                            pass
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_actions_scenario_archived "
                        "ON actions(scenario_tag, is_archived)"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_jobs_scenario "
                        "ON system_jobs_audit(scenario_tag)"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_reviews_scenario_product_var "
                        "ON reviews(scenario_tag, product, variation)"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_reviews_scenario_created_ts "
                        "ON reviews(scenario_tag, created_at_ts)"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_daily_metrics_scenario_date "
                        "ON daily_aspect_metrics(scenario_tag, metric_date, aspect)"
                    )
            _INITIALIZED_TARGETS.add(target_key)

    def _get_pg_pool(self, url: str, read_only: bool) -> Any:
        """Return or initialize a shared psycopg_pool.ConnectionPool for PostgreSQL."""
        if (
            ConnectionPool is None
            or os.getenv("ECOMREVIEW_DB_POOL_DISABLE", "false").strip().lower() == "true"
        ):
            return None
        key = (url, read_only)
        with _POOL_LOCK:
            pool = _PG_POOLS.get(key)
            if pool is None:
                min_size = int(os.getenv("ECOMREVIEW_PG_POOL_MIN", "1"))
                max_size = int(os.getenv("ECOMREVIEW_PG_POOL_MAX", "10"))
                pool = ConnectionPool(
                    conninfo=url,
                    min_size=max(1, min_size),
                    max_size=max(2, max_size),
                    open=True,
                )
                _PG_POOLS[key] = pool
            return pool

    @staticmethod
    def close_pools() -> None:
        """Close all open PostgreSQL connection pools cleanly on application shutdown."""
        with _POOL_LOCK:
            for pool in _PG_POOLS.values():
                try:
                    pool.close()
                except Exception as exc:
                    logger.debug("Error closing PG pool: %s", exc)
            _PG_POOLS.clear()

    @contextmanager
    def get_connection(self, read_only: bool = False) -> Iterator[Any]:
        """Context manager returning a connection; enforces read_only protection."""
        if self.backend == "postgres":
            if not psycopg:
                raise ImportError("psycopg is required for PostgreSQL backend.")
            url = (
                self.database_url_ro if (read_only and self.database_url_ro) else self.database_url
            )
            if not url:
                raise ValueError("DATABASE_URL is not configured for PostgreSQL.")
            pool = self._get_pg_pool(url, read_only=read_only)
            if pool is not None:
                with pool.connection() as conn:
                    try:
                        if read_only:
                            with conn.cursor() as cur:
                                cur.execute("SET TRANSACTION READ ONLY;")
                        yield _PgConnection(conn)
                        if read_only:
                            conn.rollback()
                        else:
                            conn.commit()
                    except Exception:
                        conn.rollback()
                        raise
                return

            conn = psycopg.connect(url)
            try:
                if read_only:
                    try:
                        conn.read_only = True
                    except Exception as exc:
                        logger.debug("Could not set psycopg conn.read_only=True: %s", exc)
                    with conn.cursor() as cur:
                        cur.execute("SET TRANSACTION READ ONLY;")
                yield _PgConnection(conn)
                if not read_only:
                    conn.commit()
            except Exception:
                if not read_only:
                    conn.rollback()
                raise
            finally:
                conn.close()
            return

        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            if read_only:
                conn.execute("PRAGMA query_only = ON;")
            yield conn
            if not read_only:
                conn.commit()
        except Exception:
            if not read_only:
                conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _extract_returning_id(cur: Any) -> int:
        """Extract inserted row ID from a RETURNING id cursor across SQLite/Postgres."""
        row = cur.fetchone()
        if row is not None:
            return int(row["id"] if isinstance(row, (dict, sqlite3.Row)) else row[0])
        return int(getattr(cur, "lastrowid", 0) or 0)

    def log_job_start(
        self,
        job_type: str,
        details: dict[str, Any] | None = None,
        scenario_tag: str | None = None,
    ) -> int:
        """Create a running job record in system_jobs_audit and return job_id."""
        resolved_scenario = scenario_tag or (details or {}).get("scenario_tag")
        with self.get_connection(read_only=False) as conn:
            cur = conn.execute(
                """
                INSERT INTO system_jobs_audit (job_type, scenario_tag, status, details, created_at)
                VALUES (?, ?, 'running', ?, ?)
                RETURNING id
                """,
                (
                    job_type,
                    resolved_scenario,
                    json.dumps(details or {}, ensure_ascii=False),
                    _now_iso(),
                ),
            )
            return self._extract_returning_id(cur)

    def update_job_progress(self, job_id: int, details: dict[str, Any]) -> None:
        """Update details JSON for an in-flight background job."""
        with self.get_connection(read_only=False) as conn:
            conn.execute(
                "UPDATE system_jobs_audit SET details = ? WHERE id = ?",
                (json.dumps(details, ensure_ascii=False), job_id),
            )

    def log_job_complete(
        self, job_id: int, status: str = "completed", details: dict[str, Any] | None = None
    ) -> None:
        """Update job record upon completion or failure."""
        with self.get_connection(read_only=False) as conn:
            conn.execute(
                """
                UPDATE system_jobs_audit
                SET status = ?, details = COALESCE(?, details), completed_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    json.dumps(details, ensure_ascii=False) if details is not None else None,
                    _now_iso(),
                    job_id,
                ),
            )

    def upsert_review_and_opinions(
        self,
        review_id: str,
        platform: str,
        shop: str,
        product: str,
        rating: int,
        text_raw: str,
        text_norm: str,
        source: str,
        scenario_tag: str,
        overall_sentiment: str,
        informative: bool,
        opinions: list[dict[str, Any]],
        analyzer_method: str = "gemini_v2",
        created_at: str | None = None,
        variation: str = "",
        anomaly_flags: list[str] | None = None,
    ) -> None:
        """Idempotently insert or update a review and its ABSA opinions for a scenario."""
        now_str = _now_iso()
        eff_created_at = created_at or now_str[:10]
        eff_created_ts = _normalize_created_at_ts(eff_created_at, now_str)
        flags_json = json.dumps(list(anomaly_flags or []), ensure_ascii=False)
        with self.get_connection(read_only=False) as conn:
            prev_row = conn.execute(
                "SELECT created_at FROM reviews WHERE review_id = ? AND scenario_tag = ?",
                (review_id, scenario_tag),
            ).fetchone()
            affected_dates = {_extract_metric_date(eff_created_at)}
            if prev_row:
                affected_dates.add(_extract_metric_date(prev_row["created_at"]))

            conn.execute(
                """
                INSERT INTO reviews (
                    review_id, scenario_tag, platform, shop, product, rating,
                    text_raw, text_norm, source, overall_sentiment, informative,
                    created_at, created_at_ts, imported_at, variation, anomaly_flags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (review_id, scenario_tag) DO UPDATE SET
                    platform = EXCLUDED.platform,
                    shop = EXCLUDED.shop,
                    product = EXCLUDED.product,
                    rating = EXCLUDED.rating,
                    text_raw = EXCLUDED.text_raw,
                    text_norm = EXCLUDED.text_norm,
                    source = EXCLUDED.source,
                    overall_sentiment = EXCLUDED.overall_sentiment,
                    informative = EXCLUDED.informative,
                    created_at = EXCLUDED.created_at,
                    created_at_ts = EXCLUDED.created_at_ts,
                    imported_at = EXCLUDED.imported_at,
                    variation = EXCLUDED.variation,
                    anomaly_flags = EXCLUDED.anomaly_flags
                """,
                (
                    review_id,
                    scenario_tag,
                    platform,
                    shop,
                    product,
                    rating,
                    text_raw,
                    text_norm,
                    source,
                    overall_sentiment,
                    1 if informative else 0,
                    eff_created_at,
                    eff_created_ts,
                    now_str,
                    str(variation or "")[:160],
                    flags_json,
                ),
            )
            conn.execute(
                "DELETE FROM opinions WHERE review_id = ? AND scenario_tag = ?",
                (review_id, scenario_tag),
            )
            for op in opinions:
                conn.execute(
                    """
                    INSERT INTO opinions (
                        review_id, scenario_tag, aspect, polarity,
                        evidence, evidence_ok, analyzer_method, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        review_id,
                        scenario_tag,
                        str(op["aspect"]),
                        str(op["polarity"]),
                        str(op.get("evidence", "")),
                        1 if op.get("evidence_ok", True) else 0,
                        analyzer_method,
                        now_str,
                    ),
                )
            self._refresh_daily_aspect_metrics_on_conn(conn, scenario_tag, sorted(affected_dates))

    def bulk_upsert_reviews_and_opinions(
        self,
        records: Sequence[dict[str, Any]],
        chunk_size: int = 200,
    ) -> int:
        """Upsert reviews and their opinions in batched transactions for high throughput."""
        items = list(records)
        if not items:
            return 0
        step = max(1, int(chunk_size))
        total_written = 0
        now_str = _now_iso()

        review_sql = """
            INSERT INTO reviews (
                review_id, scenario_tag, platform, shop, product, rating,
                text_raw, text_norm, source, overall_sentiment, informative,
                created_at, created_at_ts, imported_at, variation, anomaly_flags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (review_id, scenario_tag) DO UPDATE SET
                platform = EXCLUDED.platform,
                shop = EXCLUDED.shop,
                product = EXCLUDED.product,
                rating = EXCLUDED.rating,
                text_raw = EXCLUDED.text_raw,
                text_norm = EXCLUDED.text_norm,
                source = EXCLUDED.source,
                overall_sentiment = EXCLUDED.overall_sentiment,
                informative = EXCLUDED.informative,
                created_at = EXCLUDED.created_at,
                created_at_ts = EXCLUDED.created_at_ts,
                imported_at = EXCLUDED.imported_at,
                variation = EXCLUDED.variation,
                anomaly_flags = EXCLUDED.anomaly_flags
        """
        opinion_sql = """
            INSERT INTO opinions (
                review_id, scenario_tag, aspect, polarity,
                evidence, evidence_ok, analyzer_method, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        for start in range(0, len(items), step):
            chunk = items[start : start + step]
            affected_by_scenario: dict[str, set[str]] = {}
            with self.get_connection(read_only=False) as conn:
                by_stag_rids: dict[str, list[str]] = {}
                for rec in chunk:
                    by_stag_rids.setdefault(str(rec["scenario_tag"]), []).append(
                        str(rec["review_id"])
                    )
                for stag_key, rids in by_stag_rids.items():
                    ph = ", ".join("?" for _ in rids)
                    prev_rows = conn.execute(
                        f"SELECT created_at FROM reviews "
                        f"WHERE scenario_tag = ? AND review_id IN ({ph})",
                        (stag_key, *rids),
                    ).fetchall()
                    for prow in prev_rows:
                        affected_by_scenario.setdefault(stag_key, set()).add(
                            _extract_metric_date(prow["created_at"])
                        )

                for rec in chunk:
                    rid = str(rec["review_id"])
                    stag = str(rec["scenario_tag"])
                    eff_created_at = rec.get("created_at") or now_str[:10]
                    eff_created_ts = _normalize_created_at_ts(eff_created_at, now_str)
                    affected_by_scenario.setdefault(stag, set()).add(
                        _extract_metric_date(eff_created_at)
                    )
                    flags_json = json.dumps(
                        list(rec.get("anomaly_flags") or []), ensure_ascii=False
                    )
                    conn.execute(
                        review_sql,
                        (
                            rid,
                            stag,
                            str(rec["platform"]),
                            str(rec["shop"]),
                            str(rec["product"]),
                            int(rec["rating"]),
                            str(rec["text_raw"]),
                            str(rec["text_norm"]),
                            str(rec["source"]),
                            str(rec["overall_sentiment"]),
                            1 if rec.get("informative", True) else 0,
                            eff_created_at,
                            eff_created_ts,
                            now_str,
                            str(rec.get("variation") or "")[:160],
                            flags_json,
                        ),
                    )
                    conn.execute(
                        "DELETE FROM opinions WHERE review_id = ? AND scenario_tag = ?",
                        (rid, stag),
                    )
                    method = str(rec.get("analyzer_method") or "gemini_v2")
                    for op in rec.get("opinions") or []:
                        conn.execute(
                            opinion_sql,
                            (
                                rid,
                                stag,
                                str(op["aspect"]),
                                str(op["polarity"]),
                                str(op.get("evidence", "")),
                                1 if op.get("evidence_ok", True) else 0,
                                method,
                                now_str,
                            ),
                        )
                for stag_key, dates_set in affected_by_scenario.items():
                    self._refresh_daily_aspect_metrics_on_conn(conn, stag_key, sorted(dates_set))
            total_written += len(chunk)
        return total_written

    def _refresh_daily_aspect_metrics_on_conn(
        self,
        conn: Any,
        scenario_tag: str,
        metric_dates: Sequence[str] | None = None,
    ) -> int:
        """Recompute daily_aspect_metrics buckets for scenario_tag (optionally scoped to dates)."""
        now_str = _now_iso()
        date_expr = (
            "CASE WHEN r.created_at IS NOT NULL AND LENGTH(TRIM(r.created_at)) >= 10 "
            "THEN SUBSTR(TRIM(r.created_at), 1, 10) ELSE 'unknown' END"
        )
        plat_expr = "LOWER(COALESCE(NULLIF(r.platform, ''), 'unknown'))"
        if metric_dates is not None:
            clean_dates = sorted({(str(d).strip()[:10] or "unknown") for d in metric_dates})
            if not clean_dates:
                return 0
            ph = ", ".join("?" for _ in clean_dates)
            conn.execute(
                f"DELETE FROM daily_aspect_metrics "
                f"WHERE scenario_tag = ? AND metric_date IN ({ph})",
                (scenario_tag, *clean_dates),
            )
            cur = conn.execute(
                f"""
                INSERT INTO daily_aspect_metrics (
                    scenario_tag, metric_date, platform, aspect,
                    pos_count, neg_count, neu_count, total_count, updated_at
                )
                SELECT
                    r.scenario_tag,
                    {date_expr} AS metric_date,
                    {plat_expr} AS platform,
                    o.aspect AS aspect,
                    SUM(CASE WHEN o.polarity = 'positive' THEN 1 ELSE 0 END) AS pos_count,
                    SUM(CASE WHEN o.polarity = 'negative' THEN 1 ELSE 0 END) AS neg_count,
                    SUM(CASE WHEN o.polarity = 'neutral' THEN 1 ELSE 0 END) AS neu_count,
                    COUNT(*) AS total_count,
                    ? AS updated_at
                FROM opinions o
                JOIN reviews r
                  ON o.review_id = r.review_id AND o.scenario_tag = r.scenario_tag
                WHERE r.scenario_tag = ?
                  AND ({date_expr}) IN ({ph})
                GROUP BY r.scenario_tag, ({date_expr}), ({plat_expr}), o.aspect
                """,
                (now_str, scenario_tag, *clean_dates),
            )
            return int(getattr(cur, "rowcount", 0) or 0)

        conn.execute("DELETE FROM daily_aspect_metrics WHERE scenario_tag = ?", (scenario_tag,))
        cur = conn.execute(
            f"""
            INSERT INTO daily_aspect_metrics (
                scenario_tag, metric_date, platform, aspect,
                pos_count, neg_count, neu_count, total_count, updated_at
            )
            SELECT
                r.scenario_tag,
                {date_expr} AS metric_date,
                {plat_expr} AS platform,
                o.aspect AS aspect,
                SUM(CASE WHEN o.polarity = 'positive' THEN 1 ELSE 0 END) AS pos_count,
                SUM(CASE WHEN o.polarity = 'negative' THEN 1 ELSE 0 END) AS neg_count,
                SUM(CASE WHEN o.polarity = 'neutral' THEN 1 ELSE 0 END) AS neu_count,
                COUNT(*) AS total_count,
                ? AS updated_at
            FROM opinions o
            JOIN reviews r
              ON o.review_id = r.review_id AND o.scenario_tag = r.scenario_tag
            WHERE r.scenario_tag = ?
            GROUP BY r.scenario_tag, ({date_expr}), ({plat_expr}), o.aspect
            """,
            (now_str, scenario_tag),
        )
        return int(getattr(cur, "rowcount", 0) or 0)

    def refresh_daily_aspect_metrics(
        self,
        scenario_tag: str,
        metric_dates: Sequence[str] | None = None,
    ) -> int:
        """Public helper to refresh daily_aspect_metrics for one scenario."""
        with self.get_connection(read_only=False) as conn:
            return self._refresh_daily_aspect_metrics_on_conn(conn, scenario_tag, metric_dates)

    def backfill_daily_aspect_metrics(self, scenario_tag: str | None = None) -> dict[str, Any]:
        """Backfill created_at_ts on existing reviews and rebuild daily_aspect_metrics."""
        now_str = _now_iso()
        updated_ts = 0
        scenarios: list[str] = []
        with self.get_connection(read_only=False) as conn:
            if scenario_tag:
                rows = conn.execute(
                    "SELECT review_id, scenario_tag, created_at FROM reviews "
                    "WHERE scenario_tag = ? AND (created_at_ts IS NULL OR created_at_ts = '')",
                    (scenario_tag,),
                ).fetchall()
                scenarios = [scenario_tag]
            else:
                rows = conn.execute(
                    "SELECT review_id, scenario_tag, created_at FROM reviews "
                    "WHERE created_at_ts IS NULL OR created_at_ts = ''"
                ).fetchall()
                sc_rows = conn.execute("SELECT DISTINCT scenario_tag FROM reviews").fetchall()
                scenarios = [str(r["scenario_tag"]) for r in sc_rows]

            for row in rows:
                norm_ts = _normalize_created_at_ts(row["created_at"], now_str)
                conn.execute(
                    "UPDATE reviews SET created_at_ts = ? WHERE review_id = ? AND scenario_tag = ?",
                    (norm_ts, str(row["review_id"]), str(row["scenario_tag"])),
                )
                updated_ts += 1

            rebuilt_rows = 0
            for stag in scenarios:
                rebuilt_rows += self._refresh_daily_aspect_metrics_on_conn(conn, stag, None)
        return {
            "scenarios": scenarios,
            "updated_created_at_ts": updated_ts,
            "daily_metric_rows": rebuilt_rows,
        }

    def _insert_action_on_conn(
        self,
        conn: Any,
        *,
        scenario_tag: str,
        action_type: str,
        is_marketing: bool,
        title: str,
        what_to_do: str,
        why_rationale: str,
        how_and_when: str,
        success_metric: str,
        effort: str,
        impact: str,
        priority_score: float,
        insight_ids: list[int | str],
        evidence_review_ids: list[str],
        critic_passed: bool = True,
        critic_score: float = 5.0,
        critic_violations: list[dict[str, Any]] | None = None,
        retries: int = 0,
        status: str = "PENDING",
        run_id: str | None = None,
    ) -> int:
        """Insert a single action proposal using an existing writable DB connection."""
        trace_obj = {
            "critic_score": critic_score,
            "retries": retries,
            "violations": critic_violations or [],
        }
        cur = conn.execute(
            """
            INSERT INTO actions (
                scenario_tag, action_type, is_marketing, title,
                what_to_do, why_rationale, how_and_when, success_metric,
                effort, impact, priority_score, insight_ids,
                evidence_review_ids, critic_passed, critic_trace, status,
                run_id, is_archived, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            RETURNING id
            """,
            (
                scenario_tag,
                action_type,
                1 if is_marketing else 0,
                title,
                what_to_do,
                why_rationale,
                how_and_when,
                success_metric,
                effort,
                impact,
                priority_score,
                json.dumps([str(i) for i in insight_ids], ensure_ascii=False),
                json.dumps(list(evidence_review_ids), ensure_ascii=False),
                1 if critic_passed else 0,
                json.dumps(trace_obj, ensure_ascii=False),
                status,
                run_id,
                _now_iso(),
            ),
        )
        return self._extract_returning_id(cur)

    def insert_action(
        self,
        scenario_tag: str,
        action_type: str,
        is_marketing: bool,
        title: str,
        what_to_do: str,
        why_rationale: str,
        how_and_when: str,
        success_metric: str,
        effort: str,
        impact: str,
        priority_score: float,
        insight_ids: list[int | str],
        evidence_review_ids: list[str],
        critic_passed: bool = True,
        critic_score: float = 5.0,
        critic_violations: list[dict[str, Any]] | None = None,
        retries: int = 0,
        status: str = "PENDING",
        run_id: str | None = None,
    ) -> int:
        """Persist a verified ActionProposal into the actions table and return its row id."""
        with self.get_connection(read_only=False) as conn:
            return self._insert_action_on_conn(
                conn,
                scenario_tag=scenario_tag,
                action_type=action_type,
                is_marketing=is_marketing,
                title=title,
                what_to_do=what_to_do,
                why_rationale=why_rationale,
                how_and_when=how_and_when,
                success_metric=success_metric,
                effort=effort,
                impact=impact,
                priority_score=priority_score,
                insight_ids=insight_ids,
                evidence_review_ids=evidence_review_ids,
                critic_passed=critic_passed,
                critic_score=critic_score,
                critic_violations=critic_violations,
                retries=retries,
                status=status,
                run_id=run_id,
            )

    def replace_scenario_actions(
        self, scenario_tag: str, action_records: list[dict[str, Any]]
    ) -> list[int]:
        """Atomically archive existing active actions and insert a new batch."""
        saved_ids: list[int] = []
        with self.get_connection(read_only=False) as conn:
            conn.execute(
                "UPDATE actions SET is_archived = 1 "
                "WHERE scenario_tag = ? AND COALESCE(is_archived, 0) = 0",
                (scenario_tag,),
            )
            for rec in action_records:
                saved_ids.append(
                    self._insert_action_on_conn(conn, scenario_tag=scenario_tag, **rec)
                )
        return saved_ids

    def record_action_decision(
        self,
        action_id: int,
        decision: str,
        note: str = "",
        edited_content: str = "",
        reason_category: str = "",
        decided_by: str = "",
    ) -> dict[str, Any]:
        """Record human decision (APPROVED, EDITED, REJECTED) and compute edit distance."""
        dec_upper = decision.strip().upper()
        with self.get_connection(read_only=False) as conn:
            row = conn.execute(
                "SELECT what_to_do FROM actions WHERE id = ?", (action_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Action {action_id} not found.")
            orig_text = str(row["what_to_do"])
            if edited_content.strip():
                matcher = difflib.SequenceMatcher(None, orig_text.strip(), edited_content.strip())
                edit_dist = max(len(orig_text.strip()), len(edited_content.strip())) - sum(
                    block.size for block in matcher.get_matching_blocks()
                )
            else:
                edit_dist = 0

            if dec_upper == "EDITED" and edited_content.strip():
                conn.execute(
                    "UPDATE actions SET status = ?, what_to_do = ? WHERE id = ?",
                    (dec_upper, edited_content.strip(), action_id),
                )
            else:
                conn.execute(
                    "UPDATE actions SET status = ? WHERE id = ?",
                    (dec_upper, action_id),
                )
            cur = conn.execute(
                """
                INSERT INTO action_feedback (
                    action_id, decision, reason_category, note,
                    edited_content, decided_by, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    action_id,
                    dec_upper,
                    reason_category or f"edit_dist:{edit_dist}",
                    note,
                    edited_content,
                    decided_by,
                    _now_iso(),
                ),
            )
            feedback_id = self._extract_returning_id(cur)
        return {
            "feedback_id": feedback_id,
            "action_id": action_id,
            "decision": dec_upper,
            "decided_by": decided_by,
            "edit_distance_chars": edit_dist,
        }

    def insert_review_reply(
        self,
        review_id: str,
        scenario_tag: str,
        reply_text: str,
        mode_used: str = "template",
        guardrail_passed: bool = True,
        violations: list[str] | None = None,
        status: str = "DRAFT",
        created_by: str = "",
    ) -> int:
        """Persist a customer care reply draft for audit and status tracking."""
        norm_status = status.strip().upper()
        sent_at = _now_iso() if norm_status == "SENT" else None
        with self.get_connection(read_only=False) as conn:
            cur = conn.execute(
                """
                INSERT INTO review_replies (
                    review_id, scenario_tag, reply_text, mode_used,
                    guardrail_passed, violations, status, created_by, created_at, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    review_id,
                    scenario_tag,
                    reply_text,
                    mode_used,
                    1 if guardrail_passed else 0,
                    json.dumps(violations or [], ensure_ascii=False),
                    norm_status,
                    created_by,
                    _now_iso(),
                    sent_at,
                ),
            )
            return self._extract_returning_id(cur)

    def update_review_reply_status(
        self,
        reply_id: int,
        status: str,
        reply_text: str | None = None,
        guardrail_passed: bool | None = None,
        violations: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Update status (DRAFT/APPROVED/SENT) and optional edited text for a reply."""
        norm_status = status.strip().upper()
        with self.get_connection(read_only=False) as conn:
            row = conn.execute("SELECT * FROM review_replies WHERE id = ?", (reply_id,)).fetchone()
            if not row:
                return None

            new_text = (
                reply_text.strip()
                if (reply_text and reply_text.strip())
                else str(row["reply_text"])
            )
            new_passed = (
                (1 if guardrail_passed else 0)
                if guardrail_passed is not None
                else int(row["guardrail_passed"])
            )
            new_viol = (
                json.dumps(violations or [], ensure_ascii=False)
                if violations is not None
                else str(row["violations"] or "[]")
            )
            sent_at = _now_iso() if norm_status == "SENT" else None
            conn.execute(
                """
                UPDATE review_replies
                SET status = ?, reply_text = ?, guardrail_passed = ?, violations = ?, sent_at = ?
                WHERE id = ?
                """,
                (norm_status, new_text, new_passed, new_viol, sent_at, reply_id),
            )
            updated = conn.execute(
                "SELECT * FROM review_replies WHERE id = ?", (reply_id,)
            ).fetchone()
        if not updated:
            return None
        raw_viol = updated["violations"]
        viol_list = (
            json.loads(raw_viol or "[]") if isinstance(raw_viol, str) else list(raw_viol or [])
        )
        return {
            "id": int(updated["id"]),
            "review_id": str(updated["review_id"]),
            "scenario_tag": str(updated["scenario_tag"]),
            "reply_text": str(updated["reply_text"]),
            "mode_used": str(updated["mode_used"]),
            "guardrail_passed": bool(updated["guardrail_passed"]),
            "violations": viol_list,
            "status": str(updated["status"]),
            "created_by": str(updated["created_by"] or ""),
            "created_at": str(updated["created_at"] or ""),
            "sent_at": str(updated["sent_at"]) if updated["sent_at"] else None,
            "external_sync_status": (
                str(updated["external_sync_status"] or "LOCAL_ONLY")
                if "external_sync_status" in updated.keys()
                else "LOCAL_ONLY"
            ),
            "external_sync_error": (
                updated["external_sync_error"] if "external_sync_error" in updated.keys() else None
            ),
            "external_synced_at": (
                str(updated["external_synced_at"])
                if ("external_synced_at" in updated.keys() and updated["external_synced_at"])
                else None
            ),
        }

    def list_review_replies(
        self, review_id: str, scenario_tag: str = "real_shop"
    ) -> list[dict[str, Any]]:
        """Retrieve persisted customer care reply drafts for a review, newest first."""
        with self.get_connection(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT id, review_id, scenario_tag, reply_text, mode_used,
                       guardrail_passed, violations, status, created_by, created_at, sent_at,
                       external_sync_status, external_sync_error, external_synced_at
                FROM review_replies
                WHERE review_id = ? AND scenario_tag = ?
                ORDER BY id DESC
                """,
                (review_id, scenario_tag),
            ).fetchall()

        result: list[dict[str, Any]] = []
        for r in rows:
            raw_viol = r["violations"]
            viol_list = (
                json.loads(raw_viol or "[]") if isinstance(raw_viol, str) else list(raw_viol or [])
            )
            result.append(
                {
                    "id": int(r["id"]),
                    "review_id": str(r["review_id"]),
                    "scenario_tag": str(r["scenario_tag"]),
                    "reply_text": str(r["reply_text"]),
                    "mode_used": str(r["mode_used"]),
                    "guardrail_passed": bool(r["guardrail_passed"]),
                    "violations": viol_list,
                    "status": str(r["status"]),
                    "created_by": str(r["created_by"] or ""),
                    "created_at": str(r["created_at"] or ""),
                    "sent_at": str(r["sent_at"]) if r["sent_at"] else None,
                    "external_sync_status": str(r["external_sync_status"] or "LOCAL_ONLY"),
                    "external_sync_error": r["external_sync_error"],
                    "external_synced_at": (
                        str(r["external_synced_at"]) if r["external_synced_at"] else None
                    ),
                }
            )
        return result

    def mark_action_implemented(
        self, action_id: int, implemented_at: str | None = None
    ) -> dict[str, Any] | None:
        """Record actual implementation date on an action for Pre/Post Impact Tracking."""
        impl_date = (implemented_at or _now_iso())[:10]
        with self.get_connection(read_only=False) as conn:
            row = conn.execute(
                "SELECT id, scenario_tag, status FROM actions WHERE id = ?", (action_id,)
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE actions SET implemented_at = ? WHERE id = ?",
                (impl_date, action_id),
            )
        return {
            "action_id": action_id,
            "scenario_tag": str(row["scenario_tag"]),
            "status": str(row["status"]),
            "implemented_at": impl_date,
        }

    # --- Pilot Shops, Users & Alert Dispatches CRUD ---

    @staticmethod
    def _encrypt_alert_config(cfg: dict[str, Any] | None) -> dict[str, Any]:
        """Return a shallow copy of alert_config with sensitive tokens encrypted at-rest."""
        out = dict(cfg or {})
        raw_tg = str(out.get("telegram_bot_token") or "").strip()
        if raw_tg:
            out["telegram_bot_token"] = encrypt_secret(raw_tg)
        return out

    @staticmethod
    def _row_to_shop(row: Any, include_secret: bool = False) -> dict[str, Any]:
        raw_plat = row["platforms"]
        platforms = (
            json.loads(raw_plat or "[]") if isinstance(raw_plat, str) else list(raw_plat or [])
        )
        raw_alert = row["alert_config"]
        alert_cfg = (
            json.loads(raw_alert or "{}") if isinstance(raw_alert, str) else dict(raw_alert or {})
        )
        has_tg_token = bool(alert_cfg.get("telegram_bot_token"))
        if include_secret:
            if has_tg_token:
                alert_cfg["telegram_bot_token"] = decrypt_secret(
                    str(alert_cfg["telegram_bot_token"])
                )
        else:
            alert_cfg["telegram_bot_token_configured"] = has_tg_token
            alert_cfg["telegram_bot_token"] = ""

        data = {
            "id": int(row["id"]),
            "slug": str(row["slug"]),
            "name": str(row["name"]),
            "industry": str(row["industry"] or "raincoat"),
            "platforms": platforms,
            "alert_config": alert_cfg,
            "is_active": bool(row["is_active"]),
            "created_at": str(row["created_at"] or ""),
        }
        if include_secret:
            data["webhook_secret"] = decrypt_secret(str(row["webhook_secret"] or ""))
        return data

    def create_pilot_shop(
        self,
        slug: str,
        name: str,
        industry: str = "raincoat",
        platforms: list[str] | None = None,
        alert_config: dict[str, Any] | None = None,
        webhook_secret: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a Pilot shop record (slug maps 1-to-1 to scenario_tag)."""
        clean_slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", slug.strip().lower())[:64]
        if not clean_slug:
            raise ValueError("Shop slug cannot be empty.")
        secret_val = webhook_secret or secrets.token_hex(24)
        enc_secret = encrypt_secret(secret_val)
        plat_json = json.dumps(platforms or ["shopee", "tiktok"], ensure_ascii=False)
        enc_alert = self._encrypt_alert_config(alert_config)
        alert_json = json.dumps(enc_alert, ensure_ascii=False)
        now_str = _now_iso()
        with self.get_connection(read_only=False) as conn:
            conn.execute(
                """
                INSERT INTO pilot_shops (
                    slug, name, industry, platforms, alert_config,
                    webhook_secret, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    industry = EXCLUDED.industry,
                    platforms = EXCLUDED.platforms,
                    is_active = 1
                """,
                (clean_slug, name.strip(), industry, plat_json, alert_json, enc_secret, now_str),
            )
            row = conn.execute("SELECT * FROM pilot_shops WHERE slug = ?", (clean_slug,)).fetchone()
        return self._row_to_shop(row, include_secret=True)

    def get_pilot_shop(self, slug: str, include_secret: bool = False) -> dict[str, Any] | None:
        """Fetch a single Pilot shop by slug."""
        with self.get_connection(read_only=False) as conn:
            row = conn.execute(
                "SELECT * FROM pilot_shops WHERE slug = ?", (slug.strip(),)
            ).fetchone()
        return self._row_to_shop(row, include_secret=include_secret) if row else None

    def list_pilot_shops(self, allowed_slugs: list[str] | None = None) -> list[dict[str, Any]]:
        """List active Pilot shops, optionally filtered to allowed slugs."""
        with self.get_connection(read_only=False) as conn:
            rows = conn.execute(
                "SELECT * FROM pilot_shops WHERE is_active = 1 ORDER BY id ASC"
            ).fetchall()
        shops = [self._row_to_shop(r, include_secret=False) for r in rows]
        if allowed_slugs is not None and "*" not in allowed_slugs:
            allowed_set = set(allowed_slugs)
            shops = [s for s in shops if s["slug"] in allowed_set]
        return shops

    def update_pilot_shop_alerts(
        self, slug: str, alert_config: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Update outbound alert configuration JSON for a Pilot shop."""
        with self.get_connection(read_only=False) as conn:
            row = conn.execute(
                "SELECT * FROM pilot_shops WHERE slug = ?", (slug.strip(),)
            ).fetchone()
            if not row:
                return None
            existing = json.loads(row["alert_config"] or "{}")
            merged = self._encrypt_alert_config({**existing, **alert_config})
            conn.execute(
                "UPDATE pilot_shops SET alert_config = ? WHERE slug = ?",
                (json.dumps(merged, ensure_ascii=False), slug.strip()),
            )
            updated = conn.execute(
                "SELECT * FROM pilot_shops WHERE slug = ?", (slug.strip(),)
            ).fetchone()
        return self._row_to_shop(updated, include_secret=False) if updated else None

    def update_pilot_shop_profile(
        self,
        slug: str,
        *,
        industry: str | None = None,
        brand_voice: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Update shop industry template and per-shop brand_voice configuration."""
        with self.get_connection(read_only=False) as conn:
            row = conn.execute(
                "SELECT * FROM pilot_shops WHERE slug = ?", (slug.strip(),)
            ).fetchone()
            if not row:
                return None
            new_ind = str(industry or row["industry"] or "raincoat").strip().lower()
            existing = json.loads(row["alert_config"] or "{}")
            if brand_voice is not None:
                prev_bv = existing.get("brand_voice")
                merged_bv = {**(prev_bv if isinstance(prev_bv, dict) else {}), **brand_voice}
                existing["brand_voice"] = merged_bv
            merged_cfg = self._encrypt_alert_config(existing)
            conn.execute(
                "UPDATE pilot_shops SET industry = ?, alert_config = ? WHERE slug = ?",
                (new_ind, json.dumps(merged_cfg, ensure_ascii=False), slug.strip()),
            )
            updated = conn.execute(
                "SELECT * FROM pilot_shops WHERE slug = ?", (slug.strip(),)
            ).fetchone()
        return self._row_to_shop(updated, include_secret=False) if updated else None

    @staticmethod
    def _row_to_user(row: Any, include_hash: bool = False) -> dict[str, Any]:
        raw_shops = row["allowed_shops"]
        shops = (
            json.loads(raw_shops or "[]") if isinstance(raw_shops, str) else list(raw_shops or [])
        )
        tv_raw = row["token_version"] if "token_version" in row.keys() else 1
        data = {
            "id": int(row["id"]),
            "email": str(row["email"]),
            "full_name": str(row["full_name"]),
            "role": str(row["role"]),
            "allowed_shops": shops,
            "is_active": bool(row["is_active"]),
            "token_version": int(tv_raw or 1),
            "created_at": str(row["created_at"] or ""),
            "last_login_at": str(row["last_login_at"]) if row["last_login_at"] else None,
        }
        if include_hash:
            data["password_hash"] = str(row["password_hash"])
        return data

    def upsert_user(
        self,
        email: str,
        password_hash: str,
        full_name: str,
        role: str = "owner",
        allowed_shops: list[str] | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        """Create or update a Pilot user account."""
        clean_email = email.strip().lower()
        clean_role = role.strip().lower()
        shops_json = json.dumps(list(allowed_shops or []), ensure_ascii=False)
        now_str = _now_iso()
        with self.get_connection(read_only=False) as conn:
            conn.execute(
                """
                INSERT INTO users (
                    email, password_hash, full_name, role, allowed_shops, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (email) DO UPDATE SET
                    password_hash = EXCLUDED.password_hash,
                    full_name = EXCLUDED.full_name,
                    role = EXCLUDED.role,
                    allowed_shops = EXCLUDED.allowed_shops,
                    is_active = EXCLUDED.is_active
                """,
                (
                    clean_email,
                    password_hash,
                    full_name.strip() or clean_email,
                    clean_role,
                    shops_json,
                    1 if is_active else 0,
                    now_str,
                ),
            )
            row = conn.execute("SELECT * FROM users WHERE email = ?", (clean_email,)).fetchone()
        return self._row_to_user(row, include_hash=False)

    def get_user_by_email(self, email: str, include_hash: bool = False) -> dict[str, Any] | None:
        """Lookup a user by normalized email address."""
        with self.get_connection(read_only=False) as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
            ).fetchone()
        return self._row_to_user(row, include_hash=include_hash) if row else None

    def update_user_allowed_shops(
        self, user_id: int, allowed_shops: list[str]
    ) -> dict[str, Any] | None:
        """Update allowed_shops list for a user without modifying password."""
        shops_json = json.dumps(list(dict.fromkeys(allowed_shops)), ensure_ascii=False)
        with self.get_connection(read_only=False) as conn:
            row = conn.execute("SELECT id FROM users WHERE id = ?", (int(user_id),)).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE users SET allowed_shops = ? WHERE id = ?",
                (shops_json, int(user_id)),
            )
            updated = conn.execute("SELECT * FROM users WHERE id = ?", (int(user_id),)).fetchone()
        return self._row_to_user(updated, include_hash=False) if updated else None

    def list_users(self) -> list[dict[str, Any]]:
        """List all Pilot users (password hashes excluded)."""
        with self.get_connection(read_only=False) as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
        return [self._row_to_user(r, include_hash=False) for r in rows]

    def update_user_last_login(self, user_id: int) -> None:
        """Record latest login timestamp for audit visibility."""
        with self.get_connection(read_only=False) as conn:
            conn.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?",
                (_now_iso(), user_id),
            )

    def record_alert_dispatch(
        self,
        scenario_tag: str,
        dedup_key: str,
        channel: str,
        severity: str,
        title: str,
        payload: dict[str, Any],
        status: str = "SENT",
        error_message: str | None = None,
    ) -> int | None:
        """Atomically record an alert dispatch; returns None if dedup_key already exists."""
        now_str = _now_iso()
        sent_at = now_str if status.upper() == "SENT" else None
        with self.get_connection(read_only=False) as conn:
            cur = conn.execute(
                """
                INSERT INTO alert_dispatches (
                    scenario_tag, dedup_key, channel, severity, title,
                    payload, status, error_message, created_at, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (dedup_key) DO NOTHING
                RETURNING id
                """,
                (
                    scenario_tag,
                    dedup_key,
                    channel,
                    severity,
                    title,
                    json.dumps(payload, ensure_ascii=False),
                    status.upper(),
                    error_message,
                    now_str,
                    sent_at,
                ),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return int(row["id"] if isinstance(row, (dict, sqlite3.Row)) else row[0])

    def has_alert_dispatch(self, dedup_key: str) -> bool:
        """Check whether an alert with the given dedup_key was already dispatched."""
        with self.get_connection(read_only=True) as conn:
            row = conn.execute(
                "SELECT 1 FROM alert_dispatches WHERE dedup_key = ?", (dedup_key,)
            ).fetchone()
        return row is not None

    def list_alert_dispatches(self, scenario_tag: str, limit: int = 50) -> list[dict[str, Any]]:
        """List outbound alert history for a shop, newest first."""
        with self.get_connection(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT id, scenario_tag, dedup_key, channel, severity, title,
                       payload, status, error_message, created_at, sent_at
                FROM alert_dispatches
                WHERE scenario_tag = ?
                ORDER BY id DESC LIMIT ?
                """,
                (scenario_tag, max(1, min(200, limit))),
            ).fetchall()
        out = []
        for r in rows:
            raw_p = r["payload"]
            out.append(
                {
                    "id": int(r["id"]),
                    "scenario_tag": str(r["scenario_tag"]),
                    "dedup_key": str(r["dedup_key"]),
                    "channel": str(r["channel"]),
                    "severity": str(r["severity"]),
                    "title": str(r["title"]),
                    "payload": json.loads(raw_p or "{}") if isinstance(raw_p, str) else raw_p,
                    "status": str(r["status"]),
                    "error_message": r["error_message"],
                    "created_at": str(r["created_at"] or ""),
                    "sent_at": str(r["sent_at"]) if r["sent_at"] else None,
                }
            )
        return out

    def update_alert_dispatch_status(self, dispatch_id: int, status: str) -> dict[str, Any] | None:
        """Transition alert dispatch status (ACK / RESOLVED)."""
        norm = status.strip().upper()
        with self.get_connection(read_only=False) as conn:
            row = conn.execute(
                "SELECT * FROM alert_dispatches WHERE id = ?", (dispatch_id,)
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE alert_dispatches SET status = ? WHERE id = ?",
                (norm, dispatch_id),
            )
        return {
            "id": int(row["id"]),
            "scenario_tag": str(row["scenario_tag"]),
            "status": norm,
        }

    # --- User Lifecycle, Refresh Token Rotation, Scoped Shop API Keys & Audit Logs ---

    def get_user_by_id(self, user_id: int, include_hash: bool = False) -> dict[str, Any] | None:
        """Lookup a user by numeric primary key."""
        with self.get_connection(read_only=True) as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row_to_user(row, include_hash=include_hash) if row else None

    def update_user_password(self, user_id: int, new_password_hash: str) -> bool:
        """Update user password, bump token_version, and revoke all refresh tokens."""
        now_str = _now_iso()
        with self.get_connection(read_only=False) as conn:
            row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                return False
            conn.execute(
                "UPDATE users SET password_hash = ?, token_version = token_version + 1 "
                "WHERE id = ?",
                (new_password_hash, user_id),
            )
            conn.execute(
                "UPDATE refresh_tokens SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (now_str, user_id),
            )
        return True

    def set_user_active(self, user_id: int, is_active: bool) -> dict[str, Any] | None:
        """Enable or disable a user; disabling immediately revokes active JWT/refresh tokens."""
        now_str = _now_iso()
        with self.get_connection(read_only=False) as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                return None
            if is_active:
                conn.execute("UPDATE users SET is_active = 1 WHERE id = ?", (user_id,))
            else:
                conn.execute(
                    "UPDATE users SET is_active = 0, token_version = token_version + 1 "
                    "WHERE id = ?",
                    (user_id,),
                )
                conn.execute(
                    "UPDATE refresh_tokens SET revoked_at = ? "
                    "WHERE user_id = ? AND revoked_at IS NULL",
                    (now_str, user_id),
                )
            updated = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row_to_user(updated, include_hash=False) if updated else None

    def create_refresh_token(
        self,
        user_id: int,
        token_hash: str,
        family_id: str,
        expires_at: str,
    ) -> None:
        """Persist a newly issued refresh token hash."""
        now_str = _now_iso()
        with self.get_connection(read_only=False) as conn:
            conn.execute(
                """
                INSERT INTO refresh_tokens (
                    user_id, token_hash, family_id, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, token_hash, family_id, expires_at, now_str),
            )

    def rotate_refresh_token(
        self,
        old_token_hash: str,
        new_token_hash: str,
        new_expires_at: str,
    ) -> dict[str, Any]:
        """Atomically rotate a refresh token; revokes entire family on reuse detection."""
        now_str = _now_iso()
        with self.get_connection(read_only=False) as conn:
            row = conn.execute(
                "SELECT * FROM refresh_tokens WHERE token_hash = ?",
                (old_token_hash,),
            ).fetchone()
            if not row:
                return {"status": "invalid"}

            user_id = int(row["user_id"])
            family_id = str(row["family_id"])
            if row["revoked_at"] is not None:
                # Reuse attack detected: revoke all tokens in this family
                conn.execute(
                    "UPDATE refresh_tokens SET revoked_at = ? "
                    "WHERE family_id = ? AND revoked_at IS NULL",
                    (now_str, family_id),
                )
                return {"status": "reused", "user_id": user_id, "family_id": family_id}

            if str(row["expires_at"]) <= now_str:
                conn.execute(
                    "UPDATE refresh_tokens SET revoked_at = ? WHERE id = ?",
                    (now_str, int(row["id"])),
                )
                return {"status": "expired", "user_id": user_id}

            conn.execute(
                "UPDATE refresh_tokens SET revoked_at = ?, replaced_by_hash = ? WHERE id = ?",
                (now_str, new_token_hash, int(row["id"])),
            )
            conn.execute(
                """
                INSERT INTO refresh_tokens (
                    user_id, token_hash, family_id, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, new_token_hash, family_id, new_expires_at, now_str),
            )
        return {"status": "ok", "user_id": user_id, "family_id": family_id}

    def revoke_refresh_token(self, token_hash: str) -> None:
        """Revoke a single refresh token (e.g. on logout)."""
        if not token_hash:
            return
        with self.get_connection(read_only=False) as conn:
            conn.execute(
                "UPDATE refresh_tokens SET revoked_at = ? "
                "WHERE token_hash = ? AND revoked_at IS NULL",
                (_now_iso(), token_hash),
            )

    def revoke_all_user_refresh_tokens(self, user_id: int) -> None:
        """Revoke all active refresh tokens belonging to a user."""
        with self.get_connection(read_only=False) as conn:
            conn.execute(
                "UPDATE refresh_tokens SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (_now_iso(), user_id),
            )

    @staticmethod
    def _row_to_shop_api_key(row: Any) -> dict[str, Any]:
        raw_scopes = row["scopes"]
        scopes = (
            json.loads(raw_scopes or "[]")
            if isinstance(raw_scopes, str)
            else list(raw_scopes or [])
        )
        return {
            "id": int(row["id"]),
            "scenario_tag": str(row["scenario_tag"]),
            "name": str(row["name"]),
            "key_prefix": str(row["key_prefix"]),
            "role": str(row["role"]),
            "scopes": scopes,
            "created_by": row["created_by"],
            "is_active": bool(row["is_active"]),
            "created_at": str(row["created_at"] or ""),
            "last_used_at": str(row["last_used_at"]) if row["last_used_at"] else None,
            "revoked_at": str(row["revoked_at"]) if row["revoked_at"] else None,
        }

    def create_shop_api_key(
        self,
        scenario_tag: str,
        name: str,
        role: str = "owner",
        scopes: list[str] | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Create a scoped API key bound strictly to a single shop (never global admin)."""
        clean_role = role.strip().lower()
        if clean_role not in {"owner", "cskh"}:
            raise ValueError("Shop API key role must be 'owner' or 'cskh'.")
        clean_name = name.strip()[:120]
        if not clean_name:
            raise ValueError("API key name cannot be empty.")

        raw_key = f"ek_live_{secrets.token_hex(24)}"
        key_prefix = raw_key[:14]
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        scopes_json = json.dumps(list(scopes or ["read", "write"]), ensure_ascii=False)
        now_str = _now_iso()

        with self.get_connection(read_only=False) as conn:
            cur = conn.execute(
                """
                INSERT INTO shop_api_keys (
                    scenario_tag, name, key_prefix, key_hash, role,
                    scopes, created_by, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                RETURNING id
                """,
                (
                    scenario_tag.strip(),
                    clean_name,
                    key_prefix,
                    key_hash,
                    clean_role,
                    scopes_json,
                    created_by,
                    now_str,
                ),
            )
            inserted = cur.fetchone()
            kid = int(inserted["id"] if isinstance(inserted, (dict, sqlite3.Row)) else inserted[0])
            row = conn.execute("SELECT * FROM shop_api_keys WHERE id = ?", (kid,)).fetchone()
        data = self._row_to_shop_api_key(row)
        data["api_key"] = raw_key
        return data

    def list_shop_api_keys(self, scenario_tag: str) -> list[dict[str, Any]]:
        """List metadata of API keys belonging to a shop (hashes omitted)."""
        with self.get_connection(read_only=True) as conn:
            rows = conn.execute(
                "SELECT * FROM shop_api_keys WHERE scenario_tag = ? ORDER BY id DESC",
                (scenario_tag.strip(),),
            ).fetchall()
        return [self._row_to_shop_api_key(r) for r in rows]

    def revoke_shop_api_key(self, key_id: int, scenario_tag: str) -> dict[str, Any] | None:
        """Revoke an existing shop-scoped API key."""
        now_str = _now_iso()
        with self.get_connection(read_only=False) as conn:
            row = conn.execute(
                "SELECT * FROM shop_api_keys WHERE id = ? AND scenario_tag = ?",
                (key_id, scenario_tag.strip()),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE shop_api_keys SET is_active = 0, revoked_at = ? WHERE id = ?",
                (now_str, key_id),
            )
            updated = conn.execute("SELECT * FROM shop_api_keys WHERE id = ?", (key_id,)).fetchone()
        return self._row_to_shop_api_key(updated) if updated else None

    def verify_shop_api_key(self, raw_key: str) -> dict[str, Any] | None:
        """Verify an incoming raw shop API key against stored SHA-256 hash."""
        clean = (raw_key or "").strip()
        if not clean:
            return None
        key_hash = hashlib.sha256(clean.encode("utf-8")).hexdigest()
        now_str = _now_iso()
        with self.get_connection(read_only=False) as conn:
            row = conn.execute(
                "SELECT * FROM shop_api_keys "
                "WHERE key_hash = ? AND is_active = 1 AND revoked_at IS NULL",
                (key_hash,),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE shop_api_keys SET last_used_at = ? WHERE id = ?",
                (now_str, int(row["id"])),
            )
        return self._row_to_shop_api_key(row)

    def record_audit_log(
        self,
        actor: str,
        actor_role: str,
        action: str,
        scenario_tag: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> int:
        """Append an immutable audit log entry for sensitive operations."""
        now_str = _now_iso()
        with self.get_connection(read_only=False) as conn:
            cur = conn.execute(
                """
                INSERT INTO audit_logs (
                    actor, actor_role, action, scenario_tag, target_type,
                    target_id, ip_address, request_id, details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    actor[:160],
                    actor_role[:32],
                    action[:100],
                    scenario_tag,
                    target_type,
                    str(target_id)[:120] if target_id is not None else None,
                    ip_address,
                    request_id,
                    json.dumps(details or {}, ensure_ascii=False),
                    now_str,
                ),
            )
            row = cur.fetchone()
        return int(row["id"] if isinstance(row, (dict, sqlite3.Row)) else row[0])

    def list_audit_logs(
        self,
        scenario_tag: str | None = None,
        allowed_shops: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List audit log records filtered by shop or allowed_shops, newest first."""
        safe_limit = max(1, min(500, limit))
        clauses: list[str] = []
        params: list[Any] = []
        if scenario_tag:
            clauses.append("scenario_tag = ?")
            params.append(scenario_tag.strip())
        elif allowed_shops is not None and "*" not in allowed_shops:
            if not allowed_shops:
                return []
            placeholders = ", ".join("?" for _ in allowed_shops)
            clauses.append(f"scenario_tag IN ({placeholders})")
            params.extend(allowed_shops)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM audit_logs {where_sql} ORDER BY id DESC LIMIT ?"
        params.append(safe_limit)

        with self.get_connection(read_only=True) as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()

        out: list[dict[str, Any]] = []
        for r in rows:
            raw_d = r["details"]
            out.append(
                {
                    "id": int(r["id"]),
                    "actor": str(r["actor"]),
                    "actor_role": str(r["actor_role"]),
                    "action": str(r["action"]),
                    "scenario_tag": r["scenario_tag"],
                    "target_type": r["target_type"],
                    "target_id": r["target_id"],
                    "ip_address": r["ip_address"],
                    "request_id": r["request_id"],
                    "details": json.loads(raw_d or "{}") if isinstance(raw_d, str) else raw_d,
                    "created_at": str(r["created_at"] or ""),
                }
            )
        return out

    # --- Per-Shop Two-Way Marketplace Connections & Reply Push Sync ---

    @staticmethod
    def _row_to_marketplace_connection(row: Any, include_tokens: bool = False) -> dict[str, Any]:
        raw_access = str(row["access_token"] or "")
        raw_refresh = str(row["refresh_token"] or "")
        data: dict[str, Any] = {
            "id": int(row["id"]),
            "scenario_tag": str(row["scenario_tag"]),
            "platform": str(row["platform"]),
            "external_shop_id": str(row["external_shop_id"]),
            "shop_name": str(row["shop_name"] or ""),
            "has_access_token": bool(raw_access),
            "has_refresh_token": bool(raw_refresh),
            "token_expires_at": str(row["token_expires_at"]) if row["token_expires_at"] else None,
            "refresh_expires_at": (
                str(row["refresh_expires_at"]) if row["refresh_expires_at"] else None
            ),
            "auto_sync_enabled": bool(row["auto_sync_enabled"]),
            "sync_interval_minutes": int(row["sync_interval_minutes"] or 30),
            "last_synced_at": str(row["last_synced_at"]) if row["last_synced_at"] else None,
            "last_sync_status": str(row["last_sync_status"] or "NEVER"),
            "last_sync_error": row["last_sync_error"],
            "is_active": bool(row["is_active"]),
            "created_at": str(row["created_at"] or ""),
            "updated_at": str(row["updated_at"] or ""),
        }
        if include_tokens:
            data["access_token"] = decrypt_secret(raw_access)
            data["refresh_token"] = decrypt_secret(raw_refresh)
        return data

    def upsert_marketplace_connection(
        self,
        scenario_tag: str,
        platform: str,
        external_shop_id: str,
        access_token: str,
        refresh_token: str | None = None,
        token_expires_at: str | None = None,
        refresh_expires_at: str | None = None,
        shop_name: str | None = None,
        auto_sync_enabled: bool = True,
        sync_interval_minutes: int = 30,
    ) -> dict[str, Any]:
        """Store or update an encrypted OAuth connection for a shop & marketplace."""
        clean_plat = platform.strip().lower()
        clean_tag = scenario_tag.strip()
        enc_access = encrypt_secret(access_token.strip())
        enc_refresh = encrypt_secret(refresh_token.strip()) if refresh_token else ""
        now_str = _now_iso()
        with self.get_connection(read_only=False) as conn:
            conn.execute(
                """
                INSERT INTO shop_marketplace_connections (
                    scenario_tag, platform, external_shop_id, shop_name,
                    access_token, refresh_token, token_expires_at, refresh_expires_at,
                    auto_sync_enabled, sync_interval_minutes, last_sync_status,
                    is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'NEVER', 1, ?, ?)
                ON CONFLICT (scenario_tag, platform) DO UPDATE SET
                    external_shop_id = EXCLUDED.external_shop_id,
                    shop_name = COALESCE(
                        NULLIF(EXCLUDED.shop_name, ''),
                        shop_marketplace_connections.shop_name
                    ),
                    access_token = EXCLUDED.access_token,
                    refresh_token = CASE
                        WHEN EXCLUDED.refresh_token <> '' THEN EXCLUDED.refresh_token
                        ELSE shop_marketplace_connections.refresh_token
                    END,
                    token_expires_at = EXCLUDED.token_expires_at,
                    refresh_expires_at = COALESCE(
                        EXCLUDED.refresh_expires_at,
                        shop_marketplace_connections.refresh_expires_at
                    ),
                    auto_sync_enabled = EXCLUDED.auto_sync_enabled,
                    sync_interval_minutes = EXCLUDED.sync_interval_minutes,
                    is_active = 1,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    clean_tag,
                    clean_plat,
                    external_shop_id.strip(),
                    (shop_name or "").strip(),
                    enc_access,
                    enc_refresh,
                    token_expires_at,
                    refresh_expires_at,
                    1 if auto_sync_enabled else 0,
                    max(5, int(sync_interval_minutes)),
                    now_str,
                    now_str,
                ),
            )
            row = conn.execute(
                "SELECT * FROM shop_marketplace_connections "
                "WHERE scenario_tag = ? AND platform = ?",
                (clean_tag, clean_plat),
            ).fetchone()
        return self._row_to_marketplace_connection(row, include_tokens=False)

    def get_marketplace_connection(
        self,
        scenario_tag: str,
        platform: str,
        include_tokens: bool = False,
    ) -> dict[str, Any] | None:
        """Fetch an active marketplace connection for a shop & platform."""
        with self.get_connection(read_only=True) as conn:
            row = conn.execute(
                "SELECT * FROM shop_marketplace_connections "
                "WHERE scenario_tag = ? AND platform = ? AND is_active = 1",
                (scenario_tag.strip(), platform.strip().lower()),
            ).fetchone()
        return (
            self._row_to_marketplace_connection(row, include_tokens=include_tokens) if row else None
        )

    def list_marketplace_connections(
        self,
        scenario_tag: str | None = None,
        only_auto_sync: bool = False,
        include_tokens: bool = False,
    ) -> list[dict[str, Any]]:
        """List active marketplace connections optionally filtered by shop or auto-sync."""
        clauses = ["is_active = 1"]
        params: list[Any] = []
        if scenario_tag:
            clauses.append("scenario_tag = ?")
            params.append(scenario_tag.strip())
        if only_auto_sync:
            clauses.append("auto_sync_enabled = 1")
        where_sql = " AND ".join(clauses)
        with self.get_connection(read_only=True) as conn:
            rows = conn.execute(
                f"SELECT * FROM shop_marketplace_connections WHERE {where_sql} ORDER BY id ASC",
                tuple(params),
            ).fetchall()
        return [self._row_to_marketplace_connection(r, include_tokens=include_tokens) for r in rows]

    def delete_marketplace_connection(self, scenario_tag: str, platform: str) -> bool:
        """Disconnect a marketplace integration and wipe stored encrypted tokens."""
        with self.get_connection(read_only=False) as conn:
            row = conn.execute(
                "SELECT id FROM shop_marketplace_connections "
                "WHERE scenario_tag = ? AND platform = ? AND is_active = 1",
                (scenario_tag.strip(), platform.strip().lower()),
            ).fetchone()
            if not row:
                return False
            conn.execute(
                """
                UPDATE shop_marketplace_connections
                SET is_active = 0, auto_sync_enabled = 0, access_token = '',
                    refresh_token = '', updated_at = ?
                WHERE id = ?
                """,
                (_now_iso(), int(row["id"])),
            )
        return True

    def record_marketplace_sync_result(
        self,
        scenario_tag: str,
        platform: str,
        status: str,
        synced_at: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update sync status and cursor timestamp after a marketplace fetch run."""
        now_str = _now_iso()
        with self.get_connection(read_only=False) as conn:
            conn.execute(
                """
                UPDATE shop_marketplace_connections
                SET last_sync_status = ?,
                    last_synced_at = COALESCE(?, last_synced_at),
                    last_sync_error = ?,
                    updated_at = ?
                WHERE scenario_tag = ? AND platform = ?
                """,
                (
                    status.strip().upper(),
                    synced_at,
                    error_message,
                    now_str,
                    scenario_tag.strip(),
                    platform.strip().lower(),
                ),
            )

    def update_review_reply_external_sync(
        self,
        reply_id: int,
        external_sync_status: str,
        error_message: str | None = None,
    ) -> dict[str, Any] | None:
        """Record the outcome of pushing an approved CSKH reply to Shopee/TikTok."""
        norm = external_sync_status.strip().upper()
        synced_at = _now_iso() if norm == "PUSHED" else None
        with self.get_connection(read_only=False) as conn:
            row = conn.execute("SELECT id FROM review_replies WHERE id = ?", (reply_id,)).fetchone()
            if not row:
                return None
            conn.execute(
                """
                UPDATE review_replies
                SET external_sync_status = ?,
                    external_sync_error = ?,
                    external_synced_at = COALESCE(?, external_synced_at)
                WHERE id = ?
                """,
                (norm, error_message, synced_at, reply_id),
            )
            updated = conn.execute(
                "SELECT * FROM review_replies WHERE id = ?", (reply_id,)
            ).fetchone()
        if not updated:
            return None
        return {
            "id": int(updated["id"]),
            "review_id": str(updated["review_id"]),
            "scenario_tag": str(updated["scenario_tag"]),
            "status": str(updated["status"]),
            "external_sync_status": str(updated["external_sync_status"] or "LOCAL_ONLY"),
            "external_sync_error": updated["external_sync_error"],
            "external_synced_at": (
                str(updated["external_synced_at"]) if updated["external_synced_at"] else None
            ),
        }

    # --- Tenant Subscriptions & Monthly Usage Metering ---

    @staticmethod
    def _row_to_subscription(row: Any) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "tenant_key": str(row["tenant_key"]),
            "plan_code": str(row["plan_code"] or "basic"),
            "status": str(row["status"] or "ACTIVE"),
            "monthly_llm_review_limit": int(row["monthly_llm_review_limit"] or 2000),
            "max_shops": int(row["max_shops"] or 2),
            "max_users": int(row["max_users"] or 3),
            "overage_policy": str(row["overage_policy"] or "fallback_b1"),
            "trial_ends_at": str(row["trial_ends_at"]) if row["trial_ends_at"] else None,
            "notes": str(row["notes"]) if row["notes"] else None,
            "updated_by": str(row["updated_by"]) if row["updated_by"] else None,
            "created_at": str(row["created_at"] or ""),
            "updated_at": str(row["updated_at"] or ""),
        }

    def upsert_tenant_subscription(
        self,
        tenant_key: str,
        *,
        plan_code: str = "basic",
        status: str = "ACTIVE",
        monthly_llm_review_limit: int = 2000,
        max_shops: int = 2,
        max_users: int = 3,
        overage_policy: str = "fallback_b1",
        trial_ends_at: str | None = None,
        notes: str | None = None,
        updated_by: str | None = None,
    ) -> dict[str, Any]:
        """Create or update SaaS plan & quota limits for a tenant key."""
        clean_key = tenant_key.strip().lower()[:160]
        now_str = _now_iso()
        with self.get_connection(read_only=False) as conn:
            conn.execute(
                """
                INSERT INTO tenant_subscriptions (
                    tenant_key, plan_code, status, monthly_llm_review_limit,
                    max_shops, max_users, overage_policy, trial_ends_at,
                    notes, updated_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_key) DO UPDATE SET
                    plan_code = EXCLUDED.plan_code,
                    status = EXCLUDED.status,
                    monthly_llm_review_limit = EXCLUDED.monthly_llm_review_limit,
                    max_shops = EXCLUDED.max_shops,
                    max_users = EXCLUDED.max_users,
                    overage_policy = EXCLUDED.overage_policy,
                    trial_ends_at = COALESCE(
                        EXCLUDED.trial_ends_at, tenant_subscriptions.trial_ends_at
                    ),
                    notes = EXCLUDED.notes,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    clean_key,
                    plan_code.strip().lower(),
                    status.strip().upper(),
                    max(0, int(monthly_llm_review_limit)),
                    max(1, int(max_shops)),
                    max(1, int(max_users)),
                    overage_policy.strip().lower(),
                    trial_ends_at,
                    notes,
                    updated_by,
                    now_str,
                    now_str,
                ),
            )
            row = conn.execute(
                "SELECT * FROM tenant_subscriptions WHERE tenant_key = ?", (clean_key,)
            ).fetchone()
        return self._row_to_subscription(row)

    def get_tenant_subscription(self, tenant_key: str) -> dict[str, Any] | None:
        """Fetch subscription record for a single tenant key (shop slug or owner email)."""
        clean_key = tenant_key.strip().lower()
        if not clean_key:
            return None
        with self.get_connection(read_only=False) as conn:
            row = conn.execute(
                "SELECT * FROM tenant_subscriptions WHERE tenant_key = ?", (clean_key,)
            ).fetchone()
        return self._row_to_subscription(row) if row else None

    def increment_monthly_usage(
        self,
        scenario_tag: str,
        month_key: str,
        *,
        llm_reviews: int = 0,
        rule_reviews: int = 0,
        replies_generated: int = 0,
    ) -> dict[str, Any]:
        """Atomically increment monthly usage counters for a shop."""
        now_str = _now_iso()
        with self.get_connection(read_only=False) as conn:
            conn.execute(
                """
                INSERT INTO usage_monthly (
                    scenario_tag, month_key, llm_reviews_used,
                    rule_reviews_used, replies_generated, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (scenario_tag, month_key) DO UPDATE SET
                    llm_reviews_used = (
                        usage_monthly.llm_reviews_used + EXCLUDED.llm_reviews_used
                    ),
                    rule_reviews_used = (
                        usage_monthly.rule_reviews_used + EXCLUDED.rule_reviews_used
                    ),
                    replies_generated = (
                        usage_monthly.replies_generated + EXCLUDED.replies_generated
                    ),
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    scenario_tag.strip(),
                    month_key.strip(),
                    max(0, int(llm_reviews)),
                    max(0, int(rule_reviews)),
                    max(0, int(replies_generated)),
                    now_str,
                ),
            )
            row = conn.execute(
                "SELECT * FROM usage_monthly WHERE scenario_tag = ? AND month_key = ?",
                (scenario_tag.strip(), month_key.strip()),
            ).fetchone()
        return {
            "scenario_tag": str(row["scenario_tag"]),
            "month_key": str(row["month_key"]),
            "llm_reviews_used": int(row["llm_reviews_used"] or 0),
            "rule_reviews_used": int(row["rule_reviews_used"] or 0),
            "replies_generated": int(row["replies_generated"] or 0),
            "updated_at": str(row["updated_at"] or ""),
        }

    def get_monthly_usage(self, scenario_tags: Sequence[str], month_key: str) -> dict[str, Any]:
        """Aggregate monthly usage totals across one or more shop scenario_tags."""
        tags = sorted({str(t).strip() for t in scenario_tags if str(t).strip()})
        if not tags:
            return {
                "month_key": month_key,
                "llm_reviews_used": 0,
                "rule_reviews_used": 0,
                "replies_generated": 0,
                "shops": {},
            }
        ph = ", ".join("?" for _ in tags)
        with self.get_connection(read_only=True) as conn:
            rows = conn.execute(
                f"SELECT * FROM usage_monthly WHERE month_key = ? AND scenario_tag IN ({ph})",
                (month_key, *tags),
            ).fetchall()
        by_shop: dict[str, dict[str, int]] = {}
        tot_llm = 0
        tot_rule = 0
        tot_rep = 0
        for row in rows:
            llm_u = int(row["llm_reviews_used"] or 0)
            rule_u = int(row["rule_reviews_used"] or 0)
            rep_u = int(row["replies_generated"] or 0)
            tot_llm += llm_u
            tot_rule += rule_u
            tot_rep += rep_u
            by_shop[str(row["scenario_tag"])] = {
                "llm_reviews_used": llm_u,
                "rule_reviews_used": rule_u,
                "replies_generated": rep_u,
            }
        return {
            "month_key": month_key,
            "llm_reviews_used": tot_llm,
            "rule_reviews_used": tot_rule,
            "replies_generated": tot_rep,
            "shops": by_shop,
        }


# CreBy: MenBoyBMN
