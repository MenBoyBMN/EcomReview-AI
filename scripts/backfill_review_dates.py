"""Backfill historical created_at dates into reviews table for real_shop scenario."""

from __future__ import annotations

import csv
import logging
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def backfill_dates(
    db_path: str | Path = "data/ecomreview.db",
    csv_path: str | Path = "data/interim/shop_reviews_anon.csv",
) -> int:
    """Update reviews.created_at using timestamps from shop_reviews_anon.csv.

    Args:
        db_path: Path to SQLite database.
        csv_path: Path to anonymized shop reviews CSV.

    Returns:
        Number of updated review records.
    """
    csv_file = Path(csv_path)
    db_file = Path(db_path)

    if not csv_file.exists() or not db_file.exists():
        logger.warning("CSV (%s) or DB (%s) not found.", csv_file, db_file)
        return 0

    date_map: dict[str, str] = {}
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = str(row.get("review_id", "")).strip()
            dt = str(row.get("created_at", "")).strip()
            if rid and dt:
                date_map[rid] = dt[:10]

    updated = 0
    with sqlite3.connect(db_file) as conn:
        for rid, dt in date_map.items():
            cur = conn.execute(
                "UPDATE reviews SET created_at = ? "
                "WHERE review_id = ? AND scenario_tag = 'real_shop'",
                (dt, rid),
            )
            updated += cur.rowcount
        conn.commit()

    logger.info("Updated %d reviews with original created_at timestamps.", updated)
    return updated


if __name__ == "__main__":
    backfill_dates()

# CreBy: MenBoyBMN
