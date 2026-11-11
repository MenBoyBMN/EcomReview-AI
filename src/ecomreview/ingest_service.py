"""Shared review ingestion service used by both FastAPI and Streamlit UI."""

from __future__ import annotations

import logging
from typing import Any

from ecomreview.analyze.factory import get_analyzer
from ecomreview.db.database import DatabaseManager
from ecomreview.normalize import normalize_social_text
from ecomreview.schemas import Polarity
from ecomreview.security import scrub_pii

logger = logging.getLogger(__name__)


def ingest_review_batch(
    db: DatabaseManager,
    reviews: list[dict[str, Any]],
    scenario_tag: str = "real_shop",
    analyzer_method: str = "a1_gemini_v2",
) -> dict[str, Any]:
    """Process, sanitize, analyze, and upsert a batch of customer reviews into database.

    Args:
        db: DatabaseManager instance.
        reviews: List of review dictionaries containing text, platform, rating, etc.
        scenario_tag: Target scenario partition.
        analyzer_method: Method identifier ('a1_gemini_v2', 'b1_rule', etc.).

    Returns:
        Summary dict containing inserted_count and analyzer_used.
    """
    analyzer = get_analyzer(analyzer_method)
    inserted = 0

    for item in reviews:
        raw_text = str(item.get("text") or item.get("text_raw") or "").strip()
        if not raw_text:
            continue

        clean_raw = scrub_pii(raw_text)
        norm_txt = normalize_social_text(clean_raw, enable=True)
        platform = str(item.get("platform") or "tiktok").lower()
        shop = str(item.get("shop") or "shop_a")
        product = str(item.get("product") or "ao_mua_da_ca")
        rating = int(item.get("rating") or 5)
        created_at = item.get("created_at")

        opinions = item.get("opinions")
        actual_method = analyzer_method
        if opinions:
            ops = opinions
            ov_sent = item.get("overall_sentiment") or ("negative" if rating <= 2 else "positive")
            info_flag = bool(item.get("informative", True))
        else:
            res = analyzer.analyze_review(clean_raw)
            # Track fallback if analyzer was a1 but fell back to rule
            if analyzer_method.startswith("a1") and getattr(analyzer, "quota_exhausted", False):
                actual_method = f"{analyzer_method}+b1_fallback"

            ov_sent = item.get("overall_sentiment") or (
                res.overall_sentiment.value
                if isinstance(res.overall_sentiment, Polarity)
                else str(res.overall_sentiment)
            )
            info_flag = bool(res.informative)
            ops = [
                {
                    "aspect": op.aspect.value if hasattr(op.aspect, "value") else str(op.aspect),
                    "polarity": (
                        op.polarity.value if hasattr(op.polarity, "value") else str(op.polarity)
                    ),
                    "evidence": op.evidence,
                    "evidence_ok": getattr(op, "evidence_ok", True),
                }
                for op in res.opinions
            ]

        db.upsert_review_and_opinions(
            review_id=str(item.get("review_id")),
            platform=platform,
            shop=shop,
            product=product,
            rating=rating,
            text_raw=clean_raw,
            text_norm=norm_txt,
            source=str(item.get("source") or "upload"),
            scenario_tag=scenario_tag,
            overall_sentiment=ov_sent,
            informative=info_flag,
            opinions=ops,
            analyzer_method=actual_method,
            created_at=str(created_at) if created_at else None,
        )
        inserted += 1

    return {
        "scenario_tag": scenario_tag,
        "inserted_count": inserted,
        "analyzer_method": analyzer_method,
    }


# CreBy: MenBoyBMN
