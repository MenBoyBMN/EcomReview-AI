"""Database connection, schema initialization, and repository helpers.

Supports PostgreSQL 16 (production/Docker) and automatic SQLite fallback (local dev/testing)
with strict READ-ONLY connection mode enforcement for AI Agent tools.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

logger = logging.getLogger(__name__)

DEFAULT_SQLITE_PATH = Path("data/ecomreview.db")

_INITIALIZED_TARGETS: set[str] = set()
_INIT_LOCK = threading.Lock()

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
    imported_at       TEXT,
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
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id        TEXT NOT NULL,
    scenario_tag     TEXT NOT NULL DEFAULT 'real_shop',
    reply_text       TEXT NOT NULL,
    mode_used        TEXT NOT NULL DEFAULT 'template',
    guardrail_passed INTEGER NOT NULL DEFAULT 1,
    violations       TEXT NOT NULL DEFAULT '[]',
    status           TEXT NOT NULL DEFAULT 'DRAFT',
    created_by       TEXT,
    created_at       TEXT,
    sent_at          TEXT,
    FOREIGN KEY (review_id, scenario_tag)
        REFERENCES reviews(review_id, scenario_tag) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS system_jobs_audit (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type          TEXT NOT NULL,
    status            TEXT NOT NULL,
    details           TEXT,
    created_at        TEXT,
    completed_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_reviews_scenario ON reviews(scenario_tag, platform);
CREATE INDEX IF NOT EXISTS idx_opinions_aspect_pol ON opinions(scenario_tag, aspect, polarity);
CREATE INDEX IF NOT EXISTS idx_actions_scenario_status ON actions(scenario_tag, status);
CREATE INDEX IF NOT EXISTS idx_opinions_review ON opinions(scenario_tag, review_id);
CREATE INDEX IF NOT EXISTS idx_insights_scenario_kind ON insights(scenario_tag, kind);
CREATE INDEX IF NOT EXISTS idx_action_feedback_action_id ON action_feedback(action_id);
CREATE INDEX IF NOT EXISTS idx_review_replies_review ON review_replies(scenario_tag, review_id);
"""

_QMARK_RE = re.compile(r"\?")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
                        "ALTER TABLE review_replies ADD COLUMN sent_at TEXT",
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
            _INITIALIZED_TARGETS.add(target_key)

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

    def log_job_start(self, job_type: str, details: dict[str, Any] | None = None) -> int:
        """Create a running job record in system_jobs_audit and return job_id."""
        with self.get_connection(read_only=False) as conn:
            cur = conn.execute(
                """
                INSERT INTO system_jobs_audit (job_type, status, details, created_at)
                VALUES (?, 'running', ?, ?)
                RETURNING id
                """,
                (job_type, json.dumps(details or {}, ensure_ascii=False), _now_iso()),
            )
            return self._extract_returning_id(cur)

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
    ) -> None:
        """Idempotently insert or update a review and its ABSA opinions for a scenario."""
        now_str = _now_iso()
        with self.get_connection(read_only=False) as conn:
            conn.execute(
                """
                INSERT INTO reviews (
                    review_id, scenario_tag, platform, shop, product, rating,
                    text_raw, text_norm, source, overall_sentiment, informative,
                    created_at, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    imported_at = EXCLUDED.imported_at
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
                    created_at or now_str[:10],
                    now_str,
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
        }

    def list_review_replies(
        self, review_id: str, scenario_tag: str = "real_shop"
    ) -> list[dict[str, Any]]:
        """Retrieve persisted customer care reply drafts for a review, newest first."""
        with self.get_connection(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT id, review_id, scenario_tag, reply_text, mode_used,
                       guardrail_passed, violations, status, created_by, created_at, sent_at
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
                }
            )
        return result


# CreBy: MenBoyBMN
