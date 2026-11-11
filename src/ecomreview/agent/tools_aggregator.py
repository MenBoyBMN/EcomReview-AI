"""Read-Only Aggregator & Statistical Tools with Wilson Score 95% Confidence Intervals.

Implements Week 5 Task 5.3:
- Zero-Hallucination Metrics: 100% of counts, percentages, and confidence intervals
  are computed deterministically via SQL/Python on READ-ONLY database connections.
- Enforces minimum sample threshold `min_n = 5` and assigns confidence tiers:
  - `low`: 5 <= n < 15
  - `medium`: 15 <= n < 30
  - `high`: n >= 30
"""

import json
from datetime import datetime, timedelta
from math import erf, sqrt
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


def two_proportion_ztest(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float]:
    """Compute pooled two-proportion z-statistic and two-sided p-value.

    Tests null hypothesis H0: p1 == p2 against two-sided alternative H1: p1 != p2.

    Args:
        k1: Positive/event occurrences in sample 1.
        n1: Total observations in sample 1.
        k2: Positive/event occurrences in sample 2.
        n2: Total observations in sample 2.

    Returns:
        (z_score, p_value) rounded to 4 decimal places.
    """
    if n1 <= 0 or n2 <= 0:
        return 0.0, 1.0

    p1 = k1 / n1
    p2 = k2 / n2
    pooled_p = (k1 + k2) / (n1 + n2)

    se = sqrt(pooled_p * (1.0 - pooled_p) * (1.0 / n1 + 1.0 / n2))
    if se <= 1e-9:
        return 0.0, 1.0

    z = (p2 - p1) / se
    # Two-sided p-value from standard normal distribution
    p_val = max(0.0, min(1.0, 1.0 - erf(abs(z) / sqrt(2.0))))
    return round(z, 4), round(p_val, 4)


def get_aspect_trend(
    scenario_tag: str = "real_shop",
    aspect: str | None = None,
    period: str = "month",
    min_n: int = 3,
    db: DatabaseManager | None = None,
) -> list[dict[str, Any]]:
    """Aggregate review opinions by chronological period (month or week) with Wilson 95% CI.

    Args:
        scenario_tag: Target scenario partition.
        aspect: Optional aspect filter. If None, computes overall and aspect breakdown.
        period: 'month' (YYYY-MM) or 'week' (YYYY-Www).
        min_n: Minimum sample size per period bucket to include.
        db: DatabaseManager instance.

    Returns:
        Sorted list of period stats with total, negative count, negative pct, and CI.
    """
    db_mgr = db or DatabaseManager()
    query = """
        SELECT r.created_at, o.aspect, o.polarity
        FROM reviews r
        JOIN opinions o ON r.review_id = o.review_id AND r.scenario_tag = o.scenario_tag
        WHERE r.scenario_tag = ? AND r.created_at IS NOT NULL AND r.created_at != ''
    """
    params: list[Any] = [scenario_tag]
    if aspect and aspect != "ALL":
        query += " AND o.aspect = ?"
        params.append(aspect)

    with db_mgr.get_connection(read_only=True) as conn:
        rows = conn.execute(query, tuple(params)).fetchall()

    buckets: dict[str, dict[str, int]] = {}
    for r in rows:
        raw_dt = str(r["created_at"])[:10]
        try:
            dt = datetime.strptime(raw_dt, "%Y-%m-%d")
        except ValueError:
            continue

        if period == "week":
            bucket_key = f"{dt.isocalendar().year}-W{dt.isocalendar().week:02d}"
        else:
            bucket_key = dt.strftime("%Y-%m")

        if bucket_key not in buckets:
            buckets[bucket_key] = {"total": 0, "pos": 0, "neg": 0, "neu": 0}

        pol = str(r["polarity"]).lower()
        buckets[bucket_key]["total"] += 1
        if pol == "positive":
            buckets[bucket_key]["pos"] += 1
        elif pol == "negative":
            buckets[bucket_key]["neg"] += 1
        else:
            buckets[bucket_key]["neu"] += 1

    trend_list = []
    for b_key in sorted(buckets.keys()):
        data = buckets[b_key]
        tot = data["total"]
        if tot < min_n:
            continue
        neg_c = data["neg"]
        neg_pct = round((neg_c / tot) * 100.0, 1) if tot > 0 else 0.0
        ci_low, ci_high = wilson_ci_pct(neg_c, tot)
        trend_list.append(
            {
                "period": b_key,
                "aspect": aspect or "ALL",
                "total": tot,
                "neg_count": neg_c,
                "pos_count": data["pos"],
                "neu_count": data["neu"],
                "neg_pct": neg_pct,
                "wilson_ci_low": ci_low,
                "wilson_ci_high": ci_high,
                "confidence": _confidence_tier(tot),
            }
        )

    return trend_list


def detect_trend_alerts(
    scenario_tag: str = "real_shop",
    period: str = "month",
    baseline_periods: int = 3,
    min_n: int = 5,
    min_delta_pp: float = 10.0,
    alpha: float = 0.05,
    as_of: str | None = None,
    db: DatabaseManager | None = None,
) -> list[dict[str, Any]]:
    """Detect statistical spike alerts when recent negative rate exceeds historical baseline.

    Uses two-proportion one-sided z-test comparing latest period against pooled baseline.

    Args:
        scenario_tag: Target scenario partition.
        period: 'month' or 'week'.
        baseline_periods: Number of preceding periods to pool as baseline.
        min_n: Minimum sample size in both baseline and latest period.
        min_delta_pp: Minimum increase in percentage points (e.g. 10.0 for +10%).
        alpha: Statistical significance threshold.
        as_of: Optional cutoff date for evaluation (defaults to latest available date).
        db: DatabaseManager instance.

    Returns:
        List of alert dictionaries sorted by delta_pp descending.
    """
    db_mgr = db or DatabaseManager()
    # Discover all distinct aspects
    with db_mgr.get_connection(read_only=True) as conn:
        aspect_rows = conn.execute(
            "SELECT DISTINCT aspect FROM opinions WHERE scenario_tag = ? AND aspect != 'GENERAL'",
            (scenario_tag,),
        ).fetchall()
        aspects = [str(r["aspect"]) for r in aspect_rows]

    alerts: list[dict[str, Any]] = []

    for asp in aspects:
        trend = get_aspect_trend(
            scenario_tag=scenario_tag,
            aspect=asp,
            period=period,
            min_n=min_n,
            db=db_mgr,
        )
        if len(trend) < 2:
            continue

        latest_bucket = trend[-1]
        preceding = trend[:-1][-baseline_periods:]

        base_tot = sum(p["total"] for p in preceding)
        base_neg = sum(p["neg_count"] for p in preceding)
        if base_tot < min_n:
            continue

        base_pct = round((base_neg / base_tot) * 100.0, 1)
        latest_pct = latest_bucket["neg_pct"]
        delta_pp = round(latest_pct - base_pct, 1)

        if delta_pp >= min_delta_pp:
            # One-sided z-test for increase
            z, two_sided_p = two_proportion_ztest(
                base_neg, base_tot, latest_bucket["neg_count"], latest_bucket["total"]
            )
            one_sided_p = (
                max(0.0, min(1.0, 0.5 * (1.0 - erf(z / sqrt(2.0)))))
                if z > 0
                else 1.0 - 0.5 * (1.0 - erf(abs(z) / sqrt(2.0)))
            )
            if one_sided_p <= alpha:
                severity = "HIGH" if (one_sided_p < 0.01 and delta_pp >= 20.0) else "MEDIUM"
                alerts.append(
                    {
                        "aspect": asp,
                        "period": latest_bucket["period"],
                        "severity": severity,
                        "delta_pp": delta_pp,
                        "latest_neg_pct": latest_pct,
                        "baseline_neg_pct": base_pct,
                        "latest_n": latest_bucket["total"],
                        "baseline_n": base_tot,
                        "z_score": z,
                        "p_value": round(one_sided_p, 4),
                        "message": (
                            f"Cảnh báo {severity}: Khía cạnh {asp} tăng đột biến +{delta_pp}pp "
                            f"(từ {base_pct}% lên {latest_pct}%, p={round(one_sided_p, 4)})."
                        ),
                    }
                )

    return sorted(alerts, key=lambda a: a["delta_pp"], reverse=True)


def get_platform_comparison(
    scenario_tag: str = "real_shop",
    min_n: int = 5,
    db: DatabaseManager | None = None,
) -> list[dict[str, Any]]:
    """Compare negative sentiment rates between Shopee and TikTok Shop with two-sided z-test.

    Args:
        scenario_tag: Target scenario partition.
        min_n: Minimum opinions count per platform.
        db: DatabaseManager instance.

    Returns:
        List of per-aspect comparison metrics including z_score and p_value.
    """
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

    results: list[dict[str, Any]] = []
    all_aspects = sorted(set(shopee_stats.keys()) & set(tiktok_stats.keys()))

    for asp in all_aspects:
        sh = shopee_stats[asp]
        tk = tiktok_stats[asp]
        sh_neg, sh_tot = sh["neg_count"], sh["total"]
        tk_neg, tk_tot = tk["neg_count"], tk["total"]

        z, p_val = two_proportion_ztest(sh_neg, sh_tot, tk_neg, tk_tot)
        diff_pp = round(abs(sh["neg_pct"] - tk["neg_pct"]), 1)
        higher = (
            "shopee"
            if sh["neg_pct"] > tk["neg_pct"]
            else "tiktok"
            if tk["neg_pct"] > sh["neg_pct"]
            else "equal"
        )

        results.append(
            {
                "aspect": asp,
                "shopee_neg_pct": sh["neg_pct"],
                "shopee_total": sh_tot,
                "shopee_ci_95": [sh["wilson_ci_low"], sh["wilson_ci_high"]],
                "tiktok_neg_pct": tk["neg_pct"],
                "tiktok_total": tk_tot,
                "tiktok_ci_95": [tk["wilson_ci_low"], tk["wilson_ci_high"]],
                "gap_pct": diff_pp,
                "higher_platform": higher,
                "z_score": z,
                "p_value": p_val,
                "significant": bool(p_val < 0.05),
                "confidence": _confidence_tier(min(sh_tot, tk_tot)),
            }
        )

    return sorted(results, key=lambda r: r["gap_pct"], reverse=True)


def get_action_impact(
    action_id: int,
    window_days: int = 30,
    since: str | None = None,
    min_n: int = 3,
    db: DatabaseManager | None = None,
) -> dict[str, Any]:
    """Measure pre vs post intervention sentiment for aspects targeted by an approved action.

    Args:
        action_id: ID of the action proposal.
        window_days: Observation window before and after intervention.
        since: Optional intervention date (ISO YYYY-MM-DD). If omitted, uses decision date.
        min_n: Minimum sample size required in both pre and post windows.
        db: DatabaseManager instance.

    Returns:
        Impact analysis report with pre/post negative rates, Wilson CI, and status.
    """
    db_mgr = db or DatabaseManager()
    with db_mgr.get_connection(read_only=True) as conn:
        act_row = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
        if not act_row:
            return {"action_id": action_id, "status": "action_not_found"}

        dec_row = conn.execute(
            "SELECT * FROM action_feedback WHERE action_id = ? ORDER BY id DESC LIMIT 1",
            (action_id,),
        ).fetchone()

    scenario_tag = str(act_row["scenario_tag"])
    milestone_raw = (
        since
        or (str(dec_row["decided_at"])[:10] if dec_row and dec_row["decided_at"] else None)
        or (str(act_row["created_at"])[:10] if act_row["created_at"] else None)
    )

    if not milestone_raw:
        return {"action_id": action_id, "status": "missing_milestone_date"}

    try:
        milestone_dt = datetime.strptime(milestone_raw[:10], "%Y-%m-%d")
    except ValueError:
        return {"action_id": action_id, "status": "invalid_date_format"}

    pre_start = (milestone_dt - timedelta(days=window_days)).strftime("%Y-%m-%d")
    post_end = (milestone_dt + timedelta(days=window_days)).strftime("%Y-%m-%d")
    milestone_str = milestone_dt.strftime("%Y-%m-%d")

    # Discover target aspects from insight_ids
    insight_ids = []
    try:
        raw_iids = act_row["insight_ids"]
        insight_ids = json.loads(raw_iids) if isinstance(raw_iids, str) else list(raw_iids)
    except Exception:
        insight_ids = []

    target_aspects = []
    if insight_ids:
        with db_mgr.get_connection(read_only=True) as conn:
            ph = ",".join(["?"] * len(insight_ids))
            i_rows = conn.execute(
                f"SELECT aspect FROM insights WHERE id IN ({ph}) AND scenario_tag = ?",
                (*insight_ids, scenario_tag),
            ).fetchall()
            for i_row in i_rows:
                if i_row and i_row["aspect"] and str(i_row["aspect"]) != "GENERAL":
                    target_aspects.append(str(i_row["aspect"]))

    target_aspects = list(dict.fromkeys(target_aspects))

    aspect_filter = ""
    params_pre: list[Any] = [scenario_tag, pre_start, milestone_str]
    params_post: list[Any] = [scenario_tag, milestone_str, post_end]
    if target_aspects:
        placeholders = ",".join(["?"] * len(target_aspects))
        aspect_filter = f" AND o.aspect IN ({placeholders})"
        params_pre.extend(target_aspects)
        params_post.extend(target_aspects)

    query_base = f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN o.polarity = 'negative' THEN 1 ELSE 0 END) AS neg_count
        FROM reviews r
        JOIN opinions o ON r.review_id = o.review_id AND r.scenario_tag = o.scenario_tag
        WHERE r.scenario_tag = ? AND r.created_at >= ? AND r.created_at < ? {aspect_filter}
    """

    with db_mgr.get_connection(read_only=True) as conn:
        pre_res = conn.execute(query_base, tuple(params_pre)).fetchone()
        post_res = conn.execute(query_base.replace("< ?", "<= ?"), tuple(params_post)).fetchone()

    pre_tot = int(pre_res["total"] or 0)
    pre_neg = int(pre_res["neg_count"] or 0)
    post_tot = int(post_res["total"] or 0)
    post_neg = int(post_res["neg_count"] or 0)

    if pre_tot < min_n or post_tot < min_n:
        return {
            "action_id": action_id,
            "scenario_tag": scenario_tag,
            "target_aspects": target_aspects,
            "milestone_date": milestone_str,
            "window_days": window_days,
            "pre_window": {"total": pre_tot, "neg_count": pre_neg},
            "post_window": {"total": post_tot, "neg_count": post_neg},
            "status": "insufficient_data",
            "note": f"Cần tối thiểu {min_n} mẫu trong cả 2 cửa sổ trước/sau để kiểm định.",
        }

    pre_pct = round((pre_neg / pre_tot) * 100.0, 1)
    post_pct = round((post_neg / post_tot) * 100.0, 1)
    delta_pp = round(post_pct - pre_pct, 1)
    z, p_val = two_proportion_ztest(pre_neg, pre_tot, post_neg, post_tot)

    if delta_pp < 0 and p_val < 0.05:
        impact_status = "improved"
    elif delta_pp > 0 and p_val < 0.05:
        impact_status = "worsened"
    else:
        impact_status = "no_significant_change"

    return {
        "action_id": action_id,
        "scenario_tag": scenario_tag,
        "target_aspects": target_aspects,
        "milestone_date": milestone_str,
        "window_days": window_days,
        "pre_window": {
            "total": pre_tot,
            "neg_count": pre_neg,
            "neg_pct": pre_pct,
            "ci_95": wilson_ci_pct(pre_neg, pre_tot),
        },
        "post_window": {
            "total": post_tot,
            "neg_count": post_neg,
            "neg_pct": post_pct,
            "ci_95": wilson_ci_pct(post_neg, post_tot),
        },
        "delta_pp": delta_pp,
        "z_score": z,
        "p_value": p_val,
        "status": impact_status,
        "disclaimer": (
            "Quan sát đối chứng trước/sau can thiệp; không mang tính quy kết nhân quả tuyệt đối."
        ),
    }


# CreBy: MenBoyBMN
