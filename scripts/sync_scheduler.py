"""Periodic background scheduler that triggers marketplace review auto-sync jobs."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from ecomreview.jobs.queue_worker import (  # noqa: E402
    run_scheduled_marketplace_sync,
    run_scheduled_weekly_digests,
)

logging.basicConfig(
    level=os.getenv("ECOMREVIEW_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ecomreview.sync_scheduler")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run EcomReview AI periodic Shopee/TikTok Shop review sync scheduler."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single sync scan and exit.",
    )
    parser.add_argument(
        "--interval-sec",
        type=int,
        default=300,
        help="Polling interval in seconds when running continuously (default: 300).",
    )
    parser.add_argument(
        "--analyzer",
        default=os.getenv("ECOMREVIEW_SYNC_ANALYZER", "a1_gemini_v2"),
        help="Analyzer method used for newly synced reviews.",
    )
    args = parser.parse_args()

    while True:
        try:
            triggered = run_scheduled_marketplace_sync(analyzer_method=args.analyzer)
            if triggered:
                logger.info("Scheduled %d marketplace sync job(s): %s", len(triggered), triggered)
            digests = run_scheduled_weekly_digests()
            if digests:
                logger.info("Scheduled %d weekly digest job(s): %s", len(digests), digests)
        except Exception as exc:
            logger.exception("Marketplace sync scheduler tick failed: %s", exc)

        if args.once:
            return 0
        time.sleep(max(30, args.interval_sec))


if __name__ == "__main__":
    raise SystemExit(main())

# CreBy: MenBoyBMN
