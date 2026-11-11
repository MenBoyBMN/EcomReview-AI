"""Read-Only Aggregator & Statistical Tools with Wilson Score 95% Confidence Intervals.

Implements Week 5 Task 5.3:
- Zero-Hallucination Metrics: 100% of counts, percentages, and confidence intervals
  are computed deterministically via SQL/Python on READ-ONLY database connections.
- Enforces minimum sample threshold `min_n = 5` and assigns confidence tiers:
  - `low`: 5 <= n < 15
  - `medium`: 15 <= n < 30
  - `high`: n >= 30
"""

from math import sqrt
from typing import Any

from ecomreview.db.database import DatabaseManager


def wilson_ci_pct(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Compute 95% Wilson Score Confidence Interval (in %) for proportion k/n."""
    if n <= 0:
        return 0.0, 0.0
    p = k / n
    denom = 1.0 + (z * z) / n
    center = p + (z * z) / (2.0 * n)
    margin = z * sqrt((p * (1.0 - p) / n) + (z * z) / (4.0 * n * n))
    low = max(0.0, (center - margin) / denom) * 100.0
    high = min(100.0, (center + margin) / denom) * 100.0
    return round(low, 1), round(high, 1)


def _confidence_tier(n: int) -> str:
    """Assign statistical confidence tier based on sample size n."""
    if n >= 30:
        return "high"
    if n >= 15:
        return "medium"
    return "low"


def get_aspect_sentiment_stats(
    scenario_tag: str = "real_shop",
    platform: str | None = None,
    product: str | None = None,
    min_n: int = 5,
    db: DatabaseManager | None = None,
) -> list[dict[str, Any]]:
    """Query aspect sentiment counts, percentages, and Wilson 95% CI (Read-Only)."""
    db_mgr = db or DatabaseManager()
    filters = ["o.scenario_tag = ?"]
    params: list[Any] = [scenario_tag]

    if platform:
        filters.append("r.platform = ?")
        params.append(platform)
    if product:
        filters.append("r.product = ?")
        params.append(product)

    where_sql = " AND ".join(filters)
    sql = f"""
        SELECT
            o.aspect AS aspect,
            SUM(CASE WHEN o.polarity = 'positive' THEN 1 ELSE 0 END) AS pos_count,
            SUM(CASE WHEN o.polarity = 'negative' THEN 1 ELSE 0 END) AS neg_count,
            SUM(CASE WHEN o.polarity = 'neutral' THEN 1 ELSE 0 END) AS neu_count,
            COUNT(*) AS total
        FROM opinions o
        JOIN reviews r
          ON o.review_id = r.review_id AND o.scenario_tag = r.scenario_tag
        WHERE {where_sql} AND o.aspect != 'GENERAL'
        GROUP BY o.aspect
        HAVING COUNT(*) >= ?
        ORDER BY neg_count DESC, total DESC
    """
    params.append(min_n)

    stats: list[dict[str, Any]] = []
    with db_mgr.get_connection(read_only=True) as conn:
        rows = conn.execute(sql, params).fetchall()
        for row in rows:
            total = int(row["total"])
            pos_c = int(row["pos_count"])
            neg_c = int(row["neg_count"])
            neu_c = int(row["neu_count"])
            neg_pct = round((neg_c / total) * 100.0, 1) if total > 0 else 0.0
            pos_pct = round((pos_c / total) * 100.0, 1) if total > 0 else 0.0
            ci_low, ci_high = wilson_ci_pct(neg_c, total)
            pos_ci_low, pos_ci_high = wilson_ci_pct(pos_c, total)

            stats.append(
                {
                    "aspect": str(row["aspect"]),
                    "pos_count": pos_c,
                    "neg_count": neg_c,
                    "neu_count": neu_c,
                    "total": total,
                    "neg_pct": neg_pct,
                    "pos_pct": pos_pct,
                    "wilson_ci_low": ci_low,
                    "wilson_ci_high": ci_high,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "pos_ci_low": pos_ci_low,
                    "pos_ci_high": pos_ci_high,
                    "confidence": _confidence_tier(total),
                }
            )
    return stats


def get_platform_gap_stats(
    scenario_tag: str = "real_shop",
    min_n: int = 5,
    db: DatabaseManager | None = None,
) -> list[dict[str, Any]]:
    """Compare negative rates per aspect between Shopee and TikTok Shop."""
    db_mgr = db or DatabaseManager()
    shopee_stats = {
        s["aspect"]: s
        for s in get_aspect_sentiment_stats(
            scenario_tag=scenario_tag, platform="shopee", min_n=min_n, db=db_mgr
        )
    }
    tiktok_stats = {
        s["aspect"]: s
        for s in get_aspect_sentiment_stats(
            scenario_tag=scenario_tag, platform="tiktok", min_n=min_n, db=db_mgr
        )
    }

    gaps: list[dict[str, Any]] = []
    common_aspects = sorted(set(shopee_stats.keys()) & set(tiktok_stats.keys()))
    for asp in common_aspects:
        sh = shopee_stats[asp]
        tk = tiktok_stats[asp]
        gap_pct = round(abs(sh["neg_pct"] - tk["neg_pct"]), 1)
        if gap_pct >= 20.0:
            higher_platform = "shopee" if sh["neg_pct"] > tk["neg_pct"] else "tiktok"
            gaps.append(
                {
                    "aspect": asp,
                    "shopee_neg_pct": sh["neg_pct"],
                    "shopee_total": sh["total"],
                    "tiktok_neg_pct": tk["neg_pct"],
                    "tiktok_total": tk["total"],
                    "gap_pct": gap_pct,
                    "higher_platform": higher_platform,
                    "confidence": _confidence_tier(min(sh["total"], tk["total"])),
                }
            )
    return sorted(gaps, key=lambda x: x["gap_pct"], reverse=True)


def get_hidden_complaints(
    scenario_tag: str = "real_shop",
    db: DatabaseManager | None = None,
) -> list[dict[str, Any]]:
    """Find 4-5 star reviews that contain at least one negative aspect opinion."""
    db_mgr = db or DatabaseManager()
    sql = """
        SELECT
            r.review_id,
            r.platform,
            r.rating,
            r.text_raw,
            o.aspect,
            o.evidence
        FROM reviews r
        JOIN opinions o
          ON r.review_id = o.review_id AND r.scenario_tag = o.scenario_tag
        WHERE r.scenario_tag = ?
          AND r.rating >= 4
          AND o.polarity = 'negative'
        ORDER BY r.rating DESC, r.review_id ASC
    """
    with db_mgr.get_connection(read_only=True) as conn:
        rows = conn.execute(sql, (scenario_tag,)).fetchall()
        return [
            {
                "review_id": str(r["review_id"]),
                "platform": str(r["platform"]),
                "rating": int(r["rating"]),
                "text_raw": str(r["text_raw"]),
                "aspect": str(r["aspect"]),
                "evidence": str(r["evidence"]),
            }
            for r in rows
        ]


def get_reviews_by_aspect(
    scenario_tag: str = "real_shop",
    aspect: str = "WATERPROOF",
    polarity: str = "negative",
    limit: int = 5,
    db: DatabaseManager | None = None,
) -> list[dict[str, Any]]:
    """Retrieve original reviews for a specific aspect and polarity (prioritizing evidence_ok)."""
    db_mgr = db or DatabaseManager()
    sql = """
        SELECT
            r.review_id,
            r.platform,
            r.rating,
            r.text_raw,
            o.aspect,
            o.polarity,
            o.evidence,
            o.evidence_ok
        FROM reviews r
        JOIN opinions o
          ON r.review_id = o.review_id AND r.scenario_tag = o.scenario_tag
        WHERE r.scenario_tag = ?
          AND o.aspect = ?
          AND o.polarity = ?
        ORDER BY o.evidence_ok DESC, LENGTH(r.text_raw) DESC
        LIMIT ?
    """
    with db_mgr.get_connection(read_only=True) as conn:
        rows = conn.execute(sql, (scenario_tag, aspect, polarity, limit)).fetchall()
        return [
            {
                "review_id": str(r["review_id"]),
                "platform": str(r["platform"]),
                "rating": int(r["rating"]),
                "text_raw": str(r["text_raw"]),
                "aspect": str(r["aspect"]),
                "polarity": str(r["polarity"]),
                "evidence": str(r["evidence"]),
                "evidence_ok": bool(r["evidence_ok"]),
            }
            for r in rows
        ]


# CreBy: MenBoyBMN
