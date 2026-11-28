"""Safe idempotent backfill script for created_at_ts and daily_aspect_metrics."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from ecomreview.db.database import DatabaseManager  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill reviews.created_at_ts and daily_aspect_metrics pre-aggregation table."
    )
    parser.add_argument(
        "--scenario-tag",
        default=None,
        help="Optional single scenario_tag to backfill (defaults to all scenarios).",
    )
    parser.add_argument(
        "--db-path",
        default=os.getenv("ECOMREVIEW_SQLITE_PATH"),
        help="Optional SQLite DB path override.",
    )
    args = parser.parse_args()

    db = DatabaseManager(db_path=args.db_path)
    summary = db.backfill_daily_aspect_metrics(scenario_tag=args.scenario_tag)
    print(f"Backfill completed: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# CreBy: MenBoyBMN
