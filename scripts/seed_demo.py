"""One-Click Demo Seeder & OpenAPI Schema Exporter.

1. Seeds `real_shop` reviews into `data/ecomreview.db` if empty.
2. Exports OpenAPI 3.1 specification (18 endpoints) to `results/openapi.json`.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (str(_PROJECT_ROOT), str(_PROJECT_ROOT / "src")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from ecomreview.api.main import create_app  # noqa: E402
from ecomreview.db.database import DatabaseManager  # noqa: E402
from scripts.ingest import ingest_real_shop_data  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def seed_demo_and_export_openapi(force_reseed: bool = False) -> None:
    """Seed all demo data and export results/openapi.json."""
    db_mgr = DatabaseManager()
    has_data = False
    try:
        with db_mgr.get_connection(read_only=True) as conn:
            query = "SELECT count(*) AS cnt FROM reviews WHERE scenario_tag = 'real_shop'"
            row = conn.execute(query).fetchone()
            count_val = int(row["cnt"] if isinstance(row, dict) else row[0]) if row else 0
            has_data = bool(count_val > 0)
    except Exception:
        has_data = False

    if has_data and not force_reseed:
        logger.info("Database already seeded with demo data (real_shop present).")
    else:
        logger.info("Seeding real_shop into database...")
        ingest_real_shop_data(db=db_mgr)

    app = create_app()
    openapi_schema = app.openapi()
    out_path = _PROJECT_ROOT / "results" / "openapi.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(openapi_schema, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Exported OpenAPI specification (18 endpoints) to %s", out_path)


if __name__ == "__main__":
    seed_demo_and_export_openapi()

# CreBy: MenBoyBMN
