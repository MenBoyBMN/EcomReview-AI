"""One-Click Demo Seeder & OpenAPI Schema Exporter for Week 7.

1. Seeds `real_shop` (150 real reviews) + `S1..S10` scenarios into `data/ecomreview.db`.
2. Runs the P1 State-Graph (`EcomReviewGraphRunner`) so Insights and Actions are ready.
3. Exports the OpenAPI 3.1 specification of the 10 RESTful endpoints to `docs/openapi.json`.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ecomreview.api.main import create_app
from ecomreview.db.database import DatabaseManager
from scripts.ingest import ingest_real_shop_data

try:
    from scripts.build_10_scenarios import build_and_run_10_scenarios
except ImportError:
    try:
        from Abount_System.scripts.build_10_scenarios import build_and_run_10_scenarios
    except ImportError:
        build_and_run_10_scenarios = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def seed_demo_and_export_openapi(force_reseed: bool = False) -> None:
    """Seed all demo data and export docs/openapi.json."""
    db_mgr = DatabaseManager()
    has_data = False
    try:
        with db_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM reviews WHERE scenario_tag = 'real_shop'")
            row = cur.fetchone()
            has_data = bool(row and row[0] > 0)
    except Exception:
        has_data = False

    if has_data and not force_reseed:
        logger.info("Database already seeded with demo data (real_shop present).")
    else:
        logger.info("Seeding real_shop and scenarios into database...")
        ingest_real_shop_data(db=db_mgr)
        if build_and_run_10_scenarios is not None:
            build_and_run_10_scenarios()

    app = create_app()
    openapi_schema = app.openapi()
    out_path = Path("Abount_System/docs/openapi.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(openapi_schema, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Exported OpenAPI specification (10 endpoints) to %s", out_path)


if __name__ == "__main__":
    seed_demo_and_export_openapi()

# CreBy: MenBoyBMN
