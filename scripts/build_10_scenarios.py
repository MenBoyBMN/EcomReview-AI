"""Build 10 Realistic Raincoat E-Commerce Scenarios (S1..S10) & Run P0 vs P1 for RQ3.

Scenarios:
- S1: Waterproof Seam Crisis (High negative rate on WATERPROOF)
- S2: Size & Backpack Fit Mismatch (High negative rate on FIT_SIZE)
- S3: PVC Odor & Button Durability (High negative rate on MATERIAL_DURABILITY)
- S4: Foggy Visor & Mirror Sleeve Usability (High negative rate on COMFORT_USABILITY)
- S5: Price-Value Perception Gap (High negative rate on PRICE_VALUE)
- S6: Torn Packaging & Wrong Color Shipped (High negative rate on PACKAGING_SHIPPING)
- S7: Slow Chat & Warranty Dispute (High negative rate on CUSTOMER_SERVICE)
- S8: Viral Pastel Design & Durability Strength (High positive rate on ACCESSIBILITY_DESIGN)
- S9: Hidden Complaints in 4-5 Star Reviews (High 4-5 star rating with negative aspect opinions)
- S10: Shopee vs TikTok Platform Discrepancy (Large platform gap on MATERIAL_DURABILITY)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ecomreview.agent.critic import HybridCritic
from ecomreview.agent.graph_runner import EcomReviewGraphRunner
from ecomreview.agent.p0_single_prompt import P0SinglePromptAgent
from ecomreview.db.database import DatabaseManager
from ecomreview.schemas import ActionProposal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SCENARIO_SPECS: list[dict[str, Any]] = [
    {
        "tag": "S1",
        "name": "Khủng hoảng thấm nước đường may đáy quần (WATERPROOF Crisis)",
        "primary_aspect": "WATERPROOF",
        "neg_count": 14,
        "pos_count": 4,
        "quote_neg": "đi mưa to nước ngấm qua đường may đáy quần ướt hết",
        "quote_pos": "áo đi mưa nhỏ chống nước ổn",
    },
    {
        "tag": "S2",
        "name": "Bất cập kích cỡ khi đeo balo đi xe máy (FIT_SIZE Mismatch)",
        "primary_aspect": "FIT_SIZE",
        "neg_count": 12,
        "pos_count": 6,
        "quote_neg": "mặc đeo balo bị hớt tà sau ngắn quá ướt chân",
        "quote_pos": "form áo rộng rãi vừa người",
    },
    {
        "tag": "S3",
        "name": "Mùi nhựa PVC nồng và bung cúc bấm (MATERIAL_DURABILITY Issue)",
        "primary_aspect": "MATERIAL_DURABILITY",
        "neg_count": 13,
        "pos_count": 5,
        "quote_neg": "mùi nhựa nồng quá và cúc bấm mới gài đã bung",
        "quote_pos": "chất vải dù da cá dày dặn",
    },
    {
        "tag": "S4",
        "name": "Kính chắn mưa mờ do quên bóc seal bảo vệ (COMFORT_USABILITY)",
        "primary_aspect": "COMFORT_USABILITY",
        "neg_count": 11,
        "pos_count": 7,
        "quote_neg": "kính chắn mưa bị đục mờ khó nhìn đường ban đêm",
        "quote_pos": "có chụp gương chiếu hậu rất tiện dụng",
    },
    {
        "tag": "S5",
        "name": "Cảm nhận giá bán cao so với phụ kiện đi kèm (PRICE_VALUE)",
        "primary_aspect": "PRICE_VALUE",
        "neg_count": 10,
        "pos_count": 8,
        "quote_neg": "giá 165k hơi đắt so với các shop khác trên sàn",
        "quote_pos": "giá tiền hợp lý đáng mua",
    },
    {
        "tag": "S6",
        "name": "Rách túi đóng gói và giao nhầm màu áo mưa (PACKAGING_SHIPPING)",
        "primary_aspect": "PACKAGING_SHIPPING",
        "neg_count": 12,
        "pos_count": 6,
        "quote_neg": "túi đựng bị rách và đặt màu xanh rêu lại giao màu đen",
        "quote_pos": "giao hàng nhanh đóng gói gọn",
    },
    {
        "tag": "S7",
        "name": "Phản hồi tin nhắn chậm khi khách cần đổi size (CUSTOMER_SERVICE)",
        "primary_aspect": "CUSTOMER_SERVICE",
        "neg_count": 11,
        "pos_count": 5,
        "quote_neg": "nhắn tin xin đổi size mà shop trả lời chậm quá",
        "quote_pos": "nhân viên tư vấn nhiệt tình lịch sự",
    },
    {
        "tag": "S8",
        "name": "Điểm mạnh nổi bật về màu sắc Pastel Hàn Quốc (ACCESSIBILITY_DESIGN Strength)",
        "primary_aspect": "ACCESSIBILITY_DESIGN",
        "neg_count": 2,
        "pos_count": 18,
        "quote_neg": "màu thực tế hơi đậm hơn ảnh một chút",
        "quote_pos": "màu xanh pastel cực đẹp thời trang có dải phản quang sáng",
    },
    {
        "tag": "S9",
        "name": "Phàn nàn ẩn trong nhóm đánh giá 4-5 sao (Hidden Complaints)",
        "primary_aspect": "MATERIAL_DURABILITY",
        "neg_count": 10,
        "pos_count": 8,
        "high_rating_override": True,
        "quote_neg": "cho shop 5 sao vì giao nhanh nhưng vải áo hơi mỏng và có mùi nhựa",
        "quote_pos": "vải dày đẹp rất ưng ý",
    },
    {
        "tag": "S10",
        "name": "Chênh lệch chất lượng trải nghiệm giữa Shopee và TikTok Shop (Platform Gap)",
        "primary_aspect": "MATERIAL_DURABILITY",
        "neg_count": 9,
        "pos_count": 9,
        "platform_gap_mode": True,
        "quote_neg": "vải mỏng hơn mô tả trên bài viết",
        "quote_pos": "chất liệu vải dù dày dặn đúng như livestream",
    },
]


def build_and_run_10_scenarios(db_path: str | Path = "data/ecomreview.db") -> dict[str, Any]:
    """Seed S1..S10 into database and execute both P0 and P1 agents across all 10 scenarios."""
    db = DatabaseManager(db_path)
    runner_p1 = EcomReviewGraphRunner(db=db, max_retries=2, trace_dir="results/traces")
    runner_p0 = P0SinglePromptAgent(db=db)
    critic = HybridCritic()

    # Also run P1 on real_shop so trace_real_shop.json is generated
    runner_p1.run_scenario(scenario_tag="real_shop", min_n=5, max_actions=5, persist_db=True)

    candidates_out: list[dict[str, Any]] = []

    for spec in SCENARIO_SPECS:
        stag = spec["tag"]
        aspect = spec["primary_aspect"]
        n_neg = int(spec["neg_count"])
        n_pos = int(spec["pos_count"])
        total = n_neg + n_pos

        for idx in range(total):
            is_neg = idx < n_neg
            pol = "negative" if is_neg else "positive"
            quote = spec["quote_neg"] if is_neg else spec["quote_pos"]

            if spec.get("high_rating_override"):
                rating = 5
            else:
                rating = 2 if is_neg else 5

            if spec.get("platform_gap_mode"):
                platform = "shopee" if is_neg else "tiktok"
            else:
                platform = "tiktok" if idx % 2 == 0 else "shopee"

            rid = f"{stag.lower()}_rev_{idx + 1:03d}"
            text = f"Đánh giá thực tế đơn hàng #{idx + 1}: {quote}."

            db.upsert_review_and_opinions(
                review_id=rid,
                platform=platform,
                shop="shop_a",
                product="ao_mua_da_ca",
                rating=rating,
                text_raw=text,
                text_norm=text.lower(),
                source="review",
                scenario_tag=stag,
                overall_sentiment=pol,
                informative=True,
                opinions=[
                    {
                        "aspect": aspect,
                        "polarity": pol,
                        "evidence": quote,
                        "evidence_ok": True,
                    }
                ],
                analyzer_method="gemini_v2",
            )

        # Run P1 (Proposed State-Graph Agent)
        p1_res = runner_p1.run_scenario(scenario_tag=stag, min_n=5, max_actions=4, persist_db=True)

        # Run P0 (Single-Prompt Baseline Agent) and evaluate with HybridCritic for RQ3 comparison
        p0_res = runner_p0.run_scenario(scenario_tag=stag, max_actions=3)
        p0_props = [ActionProposal.model_validate(a) for a in p0_res["actions"]]
        valid_revs = set(runner_p1._get_valid_review_ids(stag))
        p0_critic = critic.evaluate(p0_props, p1_res["insights"], valid_revs)

        candidates_out.append(
            {
                "scenario_tag": stag,
                "scenario_name": spec["name"],
                "P0_Baseline": {
                    "system": "P0_Single_Prompt",
                    "actions_count": len(p0_props),
                    "critic_passed": p0_critic.passed,
                    "critic_score": p0_critic.score,
                    "violations_count": len(p0_critic.violations),
                    "violations": [v.model_dump(mode="json") for v in p0_critic.violations],
                    "actions": p0_res["actions"],
                },
                "P1_Proposed": {
                    "system": "P1_Evidence_Grounded_Critic_Graph",
                    "actions_count": p1_res["actions_count"],
                    "critic_passed": p1_res["final_critic_passed"],
                    "critic_score": p1_res["final_critic_score"],
                    "retries_used": p1_res["retries_used"],
                    "actions": p1_res["actions"],
                },
            }
        )

    out_path = Path("results/rq3_candidates.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(candidates_out, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Generated 10 scenarios (20 candidate sets P0 vs P1) -> %s", out_path)
    return {"scenarios_built": len(candidates_out), "output_path": str(out_path)}


if __name__ == "__main__":
    build_and_run_10_scenarios()

# CreBy: MenBoyBMN
