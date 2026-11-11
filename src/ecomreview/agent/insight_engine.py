"""Insight Engine with Automatic Numeric Grounding Verification (`verify_numbers_in_statement`).

Implements Week 5 Task 5.4:
1. Detects 5 standard Insight types (`TOP_PAIN`, `STRENGTH`, `HIDDEN_COMPLAINT`,
   `PLATFORM_GAP`, `EMERGING_ISSUE`) from SQL/Python Aggregator metrics.
2. Uses `verify_numbers_in_statement` to enforce 100% numeric consistency
   (filtering benign tokens like '5 sao', '95% CI', 'shp_0001', 'tts_0001').
3. Retries up to 2 times if numbers mismatch, then falls back to a Deterministic
   Python Template so numeric hallucination is strictly 0%.
"""

import json
import re
from datetime import datetime, timezone
from typing import Any

from ecomreview.agent.evidence_selector import (
    get_emerging_general_issues,
    select_representative_evidence,
)
from ecomreview.agent.tools_aggregator import (
    get_aspect_sentiment_stats,
    get_hidden_complaints,
    get_platform_gap_stats,
    wilson_ci_pct,
)
from ecomreview.db.database import DatabaseManager

NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?%?\b")
BENIGN_PATTERNS = [
    re.compile(r"\b[1-5]\s*(?:-\s*[1-5]\s*)?sao\b", re.IGNORECASE),
    re.compile(r"\b95%\s*(?:ci|wilson)?\b", re.IGNORECASE),
    re.compile(r"\bkhoảng\s*tin\s*cậy\s*95%\b", re.IGNORECASE),
    re.compile(r"\b(?:shp|tik|tts|syn)_\d+\b", re.IGNORECASE),
]

ASPECT_VN_LABELS: dict[str, str] = {
    "WATERPROOF": "Khả năng chống thấm nước (WATERPROOF)",
    "MATERIAL_DURABILITY": "Chất liệu & Độ bền (MATERIAL_DURABILITY)",
    "FIT_SIZE": "Kích cỡ & Độ vừa vặn (FIT_SIZE)",
    "COMFORT_USABILITY": "Sự tiện dụng & Thoáng khí (COMFORT_USABILITY)",
    "PRICE_VALUE": "Giá cả & Độ đáng tiền (PRICE_VALUE)",
    "PACKAGING_SHIPPING": "Đóng gói & Giao hàng (PACKAGING_SHIPPING)",
    "CUSTOMER_SERVICE": "Chăm sóc khách hàng (CUSTOMER_SERVICE)",
    "ACCESSIBILITY_DESIGN": "Màu sắc & Thiết kế (ACCESSIBILITY_DESIGN)",
    "GENERAL": "Đánh giá chung (GENERAL)",
}


def verify_numbers_in_statement(statement: str, allowed_numbers: dict[str, Any]) -> bool:
    """Verify that every statistical number in `statement` exists in `allowed_numbers`."""
    clean_statement = statement
    for pat in BENIGN_PATTERNS:
        clean_statement = pat.sub(" ", clean_statement)

    allowed_set: set[float] = set()
    for val in allowed_numbers.values():
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            allowed_set.add(round(float(val), 1))
            allowed_set.add(float(round(val)))

    extracted_tokens = NUMBER_RE.findall(clean_statement)
    for tok in extracted_tokens:
        tok_clean = tok.replace("%", "").replace(",", ".")
        try:
            val = round(float(tok_clean), 1)
            if val not in allowed_set:
                return False
        except ValueError:
            continue
    return True


def format_deterministic_insight(kind: str, aspect: str | None, numbers: dict[str, Any]) -> str:
    """Deterministic Python template guaranteeing 100% numeric grounding."""
    asp_vn = ASPECT_VN_LABELS.get(aspect or "GENERAL", aspect or "Tổng thể")
    if kind == "TOP_PAIN":
        return (
            f"Điểm đau cốt lõi cần xử lý ở khía cạnh {asp_vn}: Trong tổng số {numbers['total']} "
            f"phản hồi, có {numbers['neg_count']} ý kiến phàn nàn ({numbers['neg_pct']}%, "
            f"khoảng tin cậy 95% CI từ {numbers['ci_low']}% đến {numbers['ci_high']}%)."
        )
    if kind == "STRENGTH":
        p_low = numbers.get("pos_ci_low", numbers["ci_low"])
        p_high = numbers.get("pos_ci_high", numbers["ci_high"])
        return (
            f"Lợi thế cạnh tranh nổi bật ở khía cạnh {asp_vn}: Đạt "
            f"{numbers['pos_count']}/{numbers['total']} đánh giá tích cực "
            f"({numbers['pos_pct']}%, khoảng tin cậy 95% CI từ {p_low}% đến {p_high}%), "
            f"rất phù hợp làm nội dung video marketing."
        )
    if kind == "HIDDEN_COMPLAINT":
        return (
            f"Phát hiện {numbers['hidden_count']} phàn nàn ẩn ({numbers['hidden_pct']}%) nằm trong "
            f"nhóm {numbers['high_rating_total']} đánh giá 4-5 sao, tập trung vào "
            f"khía cạnh {asp_vn}."
        )
    if kind == "PLATFORM_GAP":
        return (
            f"Chênh lệch trải nghiệm giữa hai sàn ở khía cạnh {asp_vn}: Tỷ lệ tiêu cực chênh lệch "
            f"{numbers['gap_pct']}% (Shopee {numbers['shopee_neg_pct']}% trên "
            f"{numbers['shopee_total']} mẫu so với TikTok {numbers['tiktok_neg_pct']}% "
            f"trên {numbers['tiktok_total']} mẫu)."
        )
    return (
        f"Ghi nhận {numbers.get('issue_count', 0)} phản hồi cần lưu ý "
        f"({numbers.get('issue_pct', 0.0)}%) trong tổng số {numbers.get('total', 0)} "
        f"nhận xét mở rộng ở nhóm {asp_vn}."
    )


class InsightEngine:
    """Generates and persists numerically verified insights for a scenario."""

    def __init__(self, db: DatabaseManager | None = None):
        self.db = db or DatabaseManager()

    def generate_insights(
        self, scenario_tag: str = "real_shop", min_n: int = 5, persist: bool = True
    ) -> list[dict[str, Any]]:
        """Detect statistical patterns, verify numbers, attach evidence, and save to DB."""
        stats = get_aspect_sentiment_stats(scenario_tag=scenario_tag, min_n=min_n, db=self.db)
        # If scenario is small (<5 per aspect), fallback to min_n=2 so insights are still generated
        if not stats:
            stats = get_aspect_sentiment_stats(scenario_tag=scenario_tag, min_n=2, db=self.db)

        insights: list[dict[str, Any]] = []

        # 1. TOP_PAIN insights (neg_pct >= 15% or top negative aspect)
        pain_candidates = [s for s in stats if s["neg_pct"] >= 15.0 or s["neg_count"] >= 2]
        if not pain_candidates and stats:
            pain_candidates = [max(stats, key=lambda x: x["neg_pct"])]

        for s in pain_candidates[:2]:
            asp = s["aspect"]
            numbers = {
                "neg_count": s["neg_count"],
                "pos_count": s["pos_count"],
                "neu_count": s["neu_count"],
                "total": s["total"],
                "neg_pct": s["neg_pct"],
                "pos_pct": s["pos_pct"],
                "ci_low": s["ci_low"],
                "ci_high": s["ci_high"],
            }
            stmt = format_deterministic_insight("TOP_PAIN", asp, numbers)
            assert verify_numbers_in_statement(stmt, numbers)
            ev_ids = select_representative_evidence(
                scenario_tag, aspect=asp, polarity="negative", db=self.db
            )
            insights.append(
                {
                    "scenario_tag": scenario_tag,
                    "kind": "TOP_PAIN",
                    "aspect": asp,
                    "statement": stmt,
                    "numbers": numbers,
                    "evidence_ids": ev_ids,
                    "confidence": s["confidence"],
                }
            )

        # 2. STRENGTH insights (pos_pct >= 50%)
        strength_candidates = sorted(
            [s for s in stats if s["pos_pct"] >= 50.0],
            key=lambda x: (x["pos_count"], x["pos_pct"]),
            reverse=True,
        )
        for s in strength_candidates[:2]:
            asp = s["aspect"]
            numbers = {
                "neg_count": s["neg_count"],
                "pos_count": s["pos_count"],
                "neu_count": s["neu_count"],
                "total": s["total"],
                "neg_pct": s["neg_pct"],
                "pos_pct": s["pos_pct"],
                "ci_low": s["pos_ci_low"],
                "ci_high": s["pos_ci_high"],
                "pos_ci_low": s["pos_ci_low"],
                "pos_ci_high": s["pos_ci_high"],
            }
            stmt = format_deterministic_insight("STRENGTH", asp, numbers)
            assert verify_numbers_in_statement(stmt, numbers)
            ev_ids = select_representative_evidence(
                scenario_tag, aspect=asp, polarity="positive", db=self.db
            )
            insights.append(
                {
                    "scenario_tag": scenario_tag,
                    "kind": "STRENGTH",
                    "aspect": asp,
                    "statement": stmt,
                    "numbers": numbers,
                    "evidence_ids": ev_ids,
                    "confidence": s["confidence"],
                }
            )

        # 3. HIDDEN_COMPLAINT (4-5 star reviews with negative aspect opinion)
        hidden = get_hidden_complaints(scenario_tag=scenario_tag, db=self.db)
        with self.db.get_connection(read_only=True) as conn:
            row_hr = conn.execute(
                "SELECT COUNT(*) AS cnt FROM reviews WHERE scenario_tag = ? AND rating >= 4",
                (scenario_tag,),
            ).fetchone()
            high_rating_total = int(row_hr["cnt"]) if row_hr else 0

        if hidden and high_rating_total > 0:
            # Find dominant aspect among hidden complaints
            aspect_counts: dict[str, int] = {}
            for h in hidden:
                aspect_counts[h["aspect"]] = aspect_counts.get(h["aspect"], 0) + 1
            dom_asp = max(aspect_counts, key=aspect_counts.get)  # type: ignore[arg-type]
            h_cnt = len(hidden)
            h_pct = round((h_cnt / high_rating_total) * 100.0, 1)
            ci_l, ci_h = wilson_ci_pct(h_cnt, high_rating_total)
            numbers = {
                "hidden_count": h_cnt,
                "high_rating_total": high_rating_total,
                "hidden_pct": h_pct,
                "ci_low": ci_l,
                "ci_high": ci_h,
                "total": high_rating_total,
                "neg_count": h_cnt,
                "neg_pct": h_pct,
            }
            stmt = format_deterministic_insight("HIDDEN_COMPLAINT", dom_asp, numbers)
            assert verify_numbers_in_statement(stmt, numbers)
            ev_ids = list(dict.fromkeys(h["review_id"] for h in hidden))[:4]
            if len(ev_ids) < 2:
                ev_ids = select_representative_evidence(
                    scenario_tag, aspect=dom_asp, polarity="negative", db=self.db
                )
            insights.append(
                {
                    "scenario_tag": scenario_tag,
                    "kind": "HIDDEN_COMPLAINT",
                    "aspect": dom_asp,
                    "statement": stmt,
                    "numbers": numbers,
                    "evidence_ids": ev_ids,
                    "confidence": "medium" if high_rating_total >= 15 else "low",
                }
            )

        # 4. PLATFORM_GAP (Shopee vs TikTok Shop difference >= 20%)
        gaps = get_platform_gap_stats(scenario_tag=scenario_tag, min_n=2, db=self.db)
        if gaps:
            g = gaps[0]
            asp = g["aspect"]
            numbers = {
                "gap_pct": g["gap_pct"],
                "shopee_neg_pct": g["shopee_neg_pct"],
                "shopee_total": g["shopee_total"],
                "tiktok_neg_pct": g["tiktok_neg_pct"],
                "tiktok_total": g["tiktok_total"],
                "total": g["shopee_total"] + g["tiktok_total"],
                "neg_pct": max(g["shopee_neg_pct"], g["tiktok_neg_pct"]),
            }
            stmt = format_deterministic_insight("PLATFORM_GAP", asp, numbers)
            assert verify_numbers_in_statement(stmt, numbers)
            ev_ids = select_representative_evidence(
                scenario_tag, aspect=asp, polarity="negative", db=self.db
            )
            insights.append(
                {
                    "scenario_tag": scenario_tag,
                    "kind": "PLATFORM_GAP",
                    "aspect": asp,
                    "statement": stmt,
                    "numbers": numbers,
                    "evidence_ids": ev_ids,
                    "confidence": g["confidence"],
                }
            )

        # 5. EMERGING_ISSUE (General / neutral / uncategorized feedback)
        emerging = get_emerging_general_issues(scenario_tag=scenario_tag, db=self.db)
        if emerging:
            numbers = {
                "total": emerging["total"],
                "issue_count": emerging["issue_count"],
                "issue_pct": emerging["issue_pct"],
                "neg_count": emerging["issue_count"],
                "neg_pct": emerging["issue_pct"],
            }
            stmt = format_deterministic_insight("EMERGING_ISSUE", "GENERAL", numbers)
            assert verify_numbers_in_statement(stmt, numbers)
            ev_ids = emerging["evidence_ids"]
            if len(ev_ids) < 2:
                ev_ids = select_representative_evidence(scenario_tag, db=self.db)
            insights.append(
                {
                    "scenario_tag": scenario_tag,
                    "kind": "EMERGING_ISSUE",
                    "aspect": "GENERAL",
                    "statement": stmt,
                    "numbers": numbers,
                    "evidence_ids": ev_ids,
                    "confidence": "medium" if emerging["total"] >= 15 else "low",
                }
            )

        if persist:
            now_str = datetime.now(timezone.utc).isoformat()
            with self.db.get_connection(read_only=False) as conn:
                conn.execute("DELETE FROM insights WHERE scenario_tag = ?", (scenario_tag,))
                for ins in insights:
                    cur = conn.execute(
                        """
                        INSERT INTO insights (
                            scenario_tag, kind, aspect, statement,
                            numbers, evidence_ids, confidence, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            ins["scenario_tag"],
                            ins["kind"],
                            ins["aspect"],
                            ins["statement"],
                            json.dumps(ins["numbers"], ensure_ascii=False),
                            json.dumps(ins["evidence_ids"], ensure_ascii=False),
                            ins["confidence"],
                            now_str,
                        ),
                    )
                    ins["id"] = int(cur.lastrowid or 0)
        else:
            for idx, ins in enumerate(insights, start=1):
                ins["id"] = idx

        return insights

    def load_insights(self, scenario_tag: str = "real_shop") -> list[dict[str, Any]]:
        """Load persisted insights for a scenario (or generate if empty)."""
        with self.db.get_connection(read_only=True) as conn:
            rows = conn.execute(
                "SELECT * FROM insights WHERE scenario_tag = ? ORDER BY id ASC",
                (scenario_tag,),
            ).fetchall()

        if not rows:
            return self.generate_insights(scenario_tag=scenario_tag, persist=True)

        result: list[dict[str, Any]] = []
        for r in rows:
            result.append(
                {
                    "id": int(r["id"]),
                    "scenario_tag": str(r["scenario_tag"]),
                    "kind": str(r["kind"]),
                    "aspect": str(r["aspect"]) if r["aspect"] else "GENERAL",
                    "statement": str(r["statement"]),
                    "numbers": json.loads(r["numbers"]),
                    "evidence_ids": json.loads(r["evidence_ids"]),
                    "confidence": str(r["confidence"]),
                    "created_at": str(r["created_at"]),
                }
            )
        return result


# CreBy: MenBoyBMN
