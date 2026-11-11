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
from scripts.build_10_scenarios import build_and_run_10_scenarios
from scripts.ingest import ingest_real_shop_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def seed_demo_and_export_openapi() -> None:
    """Seed all demo data and export docs/openapi.json."""
    ingest_real_shop_data()
    build_and_run_10_scenarios()

    app = create_app()
    openapi_schema = app.openapi()
    out_path = Path("docs/openapi.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(openapi_schema, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Exported OpenAPI specification (10 endpoints) to %s", out_path)


if __name__ == "__main__":
    seed_demo_and_export_openapi()

# CreBy: MenBoyBMN
