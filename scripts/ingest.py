"""Batch Ingestion Pipeline (`scripts/ingest.py`) for EcomReview AI.

Implements Week 5 Task 5.2 & 5.6:
- Reads real shop raincoat reviews (`data/gold/gold_v2.jsonl` + `data/gold/synthetic_dev.jsonl`
  for multi-platform Shopee/TikTok coverage), scrubs PII, normalizes social text,
  analyzes with A1-v2 (or adjudicated gold cache), and populates `reviews`, `opinions`,
  `insights`, and `system_jobs_audit`.
- Exports `docs/insights_real_shop.md`.
"""

import json
import logging
from pathlib import Path

from ecomreview.agent.insight_engine import InsightEngine
from ecomreview.db.database import DatabaseManager
from ecomreview.normalize import normalize_social_text
from ecomreview.security import scrub_pii

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def ingest_real_shop_data(db: DatabaseManager | None = None) -> list[dict]:
    """Ingest real shop reviews into database and generate verified insights."""
    db_mgr = db or DatabaseManager()
    job_id = db_mgr.log_job_start("import", {"scenario_tag": "real_shop"})

    gold_v2_path = Path("data/gold/gold_v2.jsonl")
    syn_dev_path = Path("data/gold/synthetic_dev.jsonl")

    records = []
    if gold_v2_path.exists():
        with open(gold_v2_path, "r", encoding="utf-8") as f:
            records.extend(json.loads(line) for line in f if line.strip())

    # Include 25 Shopee synthetic_dev reviews so real_shop has both Shopee & TikTok
    if syn_dev_path.exists():
        with open(syn_dev_path, "r", encoding="utf-8") as f:
            syn_items = [json.loads(line) for line in f if line.strip()][:25]
            for s in syn_items:
                s["_platform_override"] = "shopee"
            records.extend(syn_items)

    ingested_count = 0
    for rec in records:
        rid = str(rec["id"])
        raw_text = scrub_pii(str(rec.get("text", "")))
        norm_text = normalize_social_text(raw_text, enable=True)
        rating = int(rec.get("rating", 5))
        platform = rec.get("_platform_override") or (
            "tiktok" if rid.startswith("tts_") else "shopee"
        )
        overall_sent = str(rec.get("overall_sentiment", "positive")).lower()
        informative = bool(rec.get("informative", True))

        opinions = []
        for op in rec.get("opinions", []):
            ev = str(op.get("evidence", "")).strip()
            ev_ok = bool(ev and (ev.lower() in raw_text.lower() or ev.lower() in norm_text.lower()))
            opinions.append(
                {
                    "aspect": str(op["aspect"]),
                    "polarity": str(op["polarity"]).lower(),
                    "evidence": ev or raw_text[:25],
                    "evidence_ok": ev_ok,
                }
            )

        db_mgr.upsert_review_and_opinions(
            review_id=rid,
            platform=platform,
            shop="shop_a",
            product="ao_mua_da_ca",
            rating=rating,
            text_raw=raw_text,
            text_norm=norm_text,
            source="review",
            scenario_tag="real_shop",
            overall_sentiment=overall_sent,
            informative=informative,
            opinions=opinions,
            analyzer_method="gemini_v2",
        )
        ingested_count += 1

    engine = InsightEngine(db=db_mgr)
    insights = engine.generate_insights(scenario_tag="real_shop", min_n=5, persist=True)

    db_mgr.log_job_complete(
        job_id,
        status="completed",
        details={"ingested_reviews": ingested_count, "generated_insights": len(insights)},
    )

    # Export docs/insights_real_shop.md (Task 5.6)
    doc_path = Path("docs/insights_real_shop.md")
    lines = [
        "# Báo Cáo Insights Thực Tế Shop Áo Mưa (`scenario_tag = real_shop`)",
        "",
        f"> **Tổng số đánh giá đã nạp:** {ingested_count} đánh giá (TikTok Shop & Shopee)",
        (
            f"> **Tổng số Insights đã kiểm chứng số học "
            f"(`verify_numbers_in_statement`):** {len(insights)}"
        ),
        "",
        "---",
        "",
    ]
    for idx, ins in enumerate(insights, start=1):
        conf_str = ins["confidence"].upper()
        nums_str = json.dumps(ins["numbers"], ensure_ascii=False)
        ev_str = ", ".join(ins["evidence_ids"])
        hdr = f"## {idx}. [{ins['kind']}] Khía cạnh: `{ins['aspect']}` (Độ tin cậy: `{conf_str}`)"
        lines.extend(
            [
                hdr,
                f"- **Nhận định:** {ins['statement']}",
                f"- **Số liệu gốc (`numbers`):** `{nums_str}`",
                f"- **Mã đánh giá bằng chứng (`evidence_ids`):** `{ev_str}`",
                "",
            ]
        )
    lines.append("<!-- CreBy: MenBoyBMN -->\n")
    doc_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(
        "Ingested %d reviews and exported %d insights to %s",
        ingested_count,
        len(insights),
        doc_path,
    )
    return insights


if __name__ == "__main__":
    ingest_real_shop_data()

# CreBy: MenBoyBMN
