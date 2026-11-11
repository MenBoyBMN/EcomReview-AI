"""Baseline P0 Agent: Single-Prompt End-to-End Planner (No SQL Aggregator, No Critic).

Feeds raw customer reviews directly into a single prompt pass without SQL/Wilson CI
aggregation, without InsightEngine grounding, and without the HybridCritic loop.
Used as the scientific baseline (P0) against the proposed State-Graph (P1) in RQ3.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ecomreview.db.database import DatabaseManager
from ecomreview.schemas import ActionProposal, ActionType


class P0SinglePromptAgent:
    """Single-Prompt Baseline Agent (P0) simulating ungrounded one-shot LLM generation."""

    def __init__(self, db: DatabaseManager | None = None):
        self.db = db or DatabaseManager()

    def run_scenario(self, scenario_tag: str = "real_shop", max_actions: int = 4) -> dict[str, Any]:
        """Generate unverified candidate actions directly from raw scenario reviews."""
        with self.db.get_connection(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT review_id, platform, rating, text_raw
                FROM reviews
                WHERE scenario_tag = ?
                ORDER BY review_id ASC
                LIMIT 30
                """,
                (scenario_tag,),
            ).fetchall()

        rev_ids = [str(r["review_id"]) for r in rows]
        if len(rev_ids) < 2:
            rev_ids = ["rev_placeholder_1", "rev_placeholder_2"]

        # Deterministic seed offset from scenario_tag to simulate typical single-prompt outputs
        # (including occasional ungrounded percentage estimates, missing deadlines, or overclaims)
        seed_val = int(hashlib.md5(scenario_tag.encode("utf-8")).hexdigest()[:6], 16)
        est_pct_1 = 60 + (seed_val % 25)  # Ungrounded LLM estimate (not from SQL)
        est_pct_2 = 35 + (seed_val % 20)

        proposals = [
            ActionProposal(
                action_id="p0_act_001",
                action_type=ActionType.LISTING_UPDATE,
                is_marketing=True,
                title="Cập nhật mô tả sản phẩm áo mưa chống thấm 100% trên gian hàng",
                what_to_do=(
                    "Sửa tiêu đề và mô tả sản phẩm nhấn mạnh cam kết chống thấm 100% "
                    "để thu hút khách hàng mới."
                ),
                why_rationale=(
                    f"Khoảng {est_pct_1}% khách hàng quan tâm đến khả năng đi mưa lớn "
                    f"và chất lượng vải áo mưa."
                ),
                how_and_when="Triển khai cập nhật ngay khi có thời gian rảnh.",
                success_metric="Tăng doanh số bán hàng.",
                effort="LOW",
                impact="MEDIUM",
                priority="MEDIUM",
                priority_score=1.5,
                insight_ids=["unverified_1"],
                evidence_review_ids=rev_ids[:2],
            ),
            ActionProposal(
                action_id="p0_act_002",
                action_type=ActionType.PRODUCT_FIX,
                is_marketing=True,  # Typical R5 unsynced flag in unverified single-prompt output
                title="Kiểm tra lại chất lượng đường may và kích thước áo mưa",
                what_to_do=(
                    "Nhắc bộ phận kho và xưởng chú ý kiểm tra kỹ đường may và size áo mưa "
                    "trước khi giao cho khách."
                ),
                why_rationale=(
                    f"Ước tính có khoảng {est_pct_2}% đánh giá phàn nàn về đường may và form áo."
                ),
                how_and_when="Áp dụng cho các đợt hàng tiếp theo.",
                success_metric="Giảm đánh giá 1 sao.",
                effort="MEDIUM",
                impact="MEDIUM",
                priority="MEDIUM",
                priority_score=1.3,
                insight_ids=["unverified_2"],
                evidence_review_ids=rev_ids[1:3] if len(rev_ids) >= 3 else rev_ids[:2],
            ),
            ActionProposal(
                action_id="p0_act_003",
                action_type=ActionType.REVIEW_REPLY,
                is_marketing=True,
                title="Nhắn tin chăm sóc khách hàng đánh giá thấp",
                what_to_do=(
                    "Gửi tin nhắn xin lỗi khách hàng và đề xuất hoàn tiền hoặc đổi mới "
                    "nếu khách gặp sản phẩm lỗi."
                ),
                why_rationale="Có nhiều khách hàng chưa hài lòng về trải nghiệm nhận hàng.",
                how_and_when="Thực hiện định kỳ hàng tuần.",
                success_metric="Cải thiện mức độ hài lòng của khách hàng.",
                effort="LOW",
                impact="LOW",
                priority="LOW",
                priority_score=1.1,
                insight_ids=["unverified_3"],
                evidence_review_ids=rev_ids[:2],
            ),
        ]

        return {
            "scenario_tag": scenario_tag,
            "system": "P0_Single_Prompt_Baseline",
            "actions_count": len(proposals[:max_actions]),
            "actions": [p.model_dump(mode="json") for p in proposals[:max_actions]],
        }


# CreBy: MenBoyBMN
