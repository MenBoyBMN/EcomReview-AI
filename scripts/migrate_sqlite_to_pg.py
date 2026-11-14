"""Migration utility to sync SQLite demo database to PostgreSQL 16."""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from dotenv import load_dotenv

try:
    import psycopg
except ImportError:
    psycopg = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TABLES = [
    "reviews",
    "opinions",
    "insights",
    "actions",
    "action_feedback",
    "review_replies",
    "system_jobs_audit",
]


def migrate_sqlite_to_postgres(
    sqlite_path: str | Path = "data/ecomreview.db",
    pg_url: str | None = None,
    if_empty: bool = False,
) -> int:
    """Migrate data from local SQLite database to PostgreSQL.

    Args:
        sqlite_path: Path to source SQLite .db file.
        pg_url: Target PostgreSQL connection string (defaults to DATABASE_URL).
        if_empty: If True, only migrate if target 'reviews' table is empty.

    Returns:
        Total number of records migrated.
    """
    load_dotenv()
    if not psycopg:
        logger.error("psycopg is not installed. Cannot migrate to PostgreSQL.")
        return -1

    url = pg_url or os.getenv("DATABASE_URL")
    if not url:
        logger.error("No PostgreSQL URL configured (DATABASE_URL is empty).")
        return -1

    sqlite_file = Path(sqlite_path)
    if not sqlite_file.exists():
        logger.warning("Source SQLite file %s does not exist. Nothing to migrate.", sqlite_file)
        return 0

    with psycopg.connect(url) as pg_conn:
        if if_empty:
            with pg_conn.cursor() as cur:
                cur.execute(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM information_schema.tables WHERE table_name = 'reviews'"
                    ")"
                )
                exists = cur.fetchone()[0]
                if exists:
                    cur.execute("SELECT COUNT(*) FROM reviews")
                    cnt = cur.fetchone()[0]
                    if cnt > 0:
                        logger.info(
                            "PostgreSQL already contains %d reviews. Skipping migration.",
                            cnt,
                        )
                        return 0

        # Run init.sql to ensure tables exist
        project_root = Path(__file__).resolve().parents[1]
        init_sql = project_root / "docker" / "db" / "init.sql"
        if not init_sql.exists():
            init_sql = Path("docker/db/init.sql")
        if init_sql.exists():
            with pg_conn.cursor() as cur:
                cur.execute(init_sql.read_text(encoding="utf-8"))
            pg_conn.commit()

        total_migrated = 0
        with closing(sqlite3.connect(sqlite_file)) as sl_conn:
            sl_conn.row_factory = sqlite3.Row

            for table in TABLES:
                try:
                    rows = sl_conn.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608
                except sqlite3.OperationalError as e:
                    logger.warning("Could not read table %s in SQLite: %s", table, e)
                    continue

                if not rows:
                    continue

                valid_action_ids: set[int] | None = None
                if table == "action_feedback":
                    with pg_conn.cursor() as cur:
                        cur.execute("SELECT id FROM actions")
                        valid_action_ids = {int(row[0]) for row in cur.fetchall()}

                cols = list(rows[0].keys())
                col_names = ", ".join(cols)
                placeholders = ", ".join(["%s"] * len(cols))

                inserted_for_table = 0
                skipped_orphans = 0
                with pg_conn.cursor() as cur:
                    for r in rows:
                        if (
                            valid_action_ids is not None
                            and int(r["action_id"]) not in valid_action_ids
                        ):
                            skipped_orphans += 1
                            continue
                        vals = tuple(r[c] for c in cols)
                        cur.execute(
                            f"INSERT INTO {table} ({col_names}) "  # noqa: S608
                            f"VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                            vals,
                        )
                        if cur.rowcount and cur.rowcount > 0:
                            inserted_for_table += cur.rowcount

                if skipped_orphans:
                    logger.warning(
                        "Skipped %d orphan rows in %s referencing missing action_id",
                        skipped_orphans,
                        table,
                    )
                total_migrated += inserted_for_table
                logger.info("Migrated %d rows into %s", inserted_for_table, table)

                # Reset Postgres sequence for SERIAL / BIGSERIAL primary keys
                if table != "reviews":
                    with pg_conn.cursor() as cur:
                        cur.execute(
                            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "  # noqa: S608
                            f"COALESCE((SELECT MAX(id) FROM {table}), 1), "
                            f"(SELECT MAX(id) IS NOT NULL FROM {table}));"
                        )

        pg_conn.commit()

    logger.info("Successfully migrated %d total records to PostgreSQL.", total_migrated)
    return total_migrated


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite to PostgreSQL for EcomReview AI")
    parser.add_argument("--sqlite-path", default="data/ecomreview.db")
    parser.add_argument("--pg-url", default=None)
    parser.add_argument("--if-empty", action="store_true", help="Only migrate if target is empty")
    args = parser.parse_args()

    count = migrate_sqlite_to_postgres(
        sqlite_path=args.sqlite_path, pg_url=args.pg_url, if_empty=args.if_empty
    )
    sys.exit(0 if count >= 0 else 1)


if __name__ == "__main__":
    main()

# CreBy: MenBoyBMN
