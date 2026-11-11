"""Evidence-Grounded Action Planner (P1 Agent Node) for EcomReview AI.

Generates concrete marketing and operational/product ActionProposals from verified
Insights, grounded in the raincoat domain playbook (`knowledge/playbook_aomua.yaml`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ecomreview.agent.insight_engine import ASPECT_VN_LABELS
from ecomreview.schemas import MARKETING_ACTION_TYPES, ActionProposal, ActionType

IMPACT_WEIGHTS = {"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0}
CONFIDENCE_WEIGHTS = {"HIGH": 1.2, "MEDIUM": 1.0, "LOW": 0.8}
EFFORT_WEIGHTS = {"LOW": 1.0, "MEDIUM": 1.5, "HIGH": 2.2}


def compute_priority_score(
    impact: str,
    severity_pct: float,
    confidence: str = "HIGH",
    effort: str = "LOW",
) -> float:
    """Deterministic priority formula combining impact, severity, confidence & effort."""
    imp_w = IMPACT_WEIGHTS.get(str(impact).upper(), 2.0)
    conf_w = CONFIDENCE_WEIGHTS.get(str(confidence).upper(), 1.0)
    eff_w = EFFORT_WEIGHTS.get(str(effort).upper(), 1.5)
    sev_factor = 1.0 + max(0.0, min(100.0, float(severity_pct))) / 100.0
    score = (imp_w * sev_factor * conf_w) / eff_w
    return round(score, 2)


class ActionPlanner:
    """Playbook-guided & evidence-grounded Action Planner for Raincoat SMEs."""

    def __init__(
        self,
        playbook_path: str | Path = "knowledge/playbook_aomua.yaml",
        prompt_path: str | Path = "prompts/planner_v1.md",
    ):
        self.playbook_path = Path(playbook_path)
        self.prompt_path = Path(prompt_path)
        self.playbook_data: dict[str, Any] = {"playbook_rules": [], "guardrails": {}}
        if self.playbook_path.exists():
            self.playbook_data = (
                yaml.safe_load(self.playbook_path.read_text(encoding="utf-8")) or {}
            )
        self.rules: list[dict[str, Any]] = self.playbook_data.get("playbook_rules", [])

    def _find_matching_rules(self, aspect: str, kind: str) -> list[dict[str, Any]]:
        """Find playbook templates matching (aspect, trigger) with graceful fallbacks."""
        exact = [r for r in self.rules if r.get("aspect") == aspect and r.get("trigger") == kind]
        if exact:
            return exact

        by_aspect = [r for r in self.rules if r.get("aspect") == aspect]
        if by_aspect:
            return by_aspect[:1]

        # Generic fallback rule
        if kind == "STRENGTH":
            return [
                {
                    "action_type": "CONTENT",
                    "is_marketing": True,
                    "title": f"Khai thác nội dung truyền thông điểm mạnh {aspect}",
                    "what_to_do": (
                        f"Tổng hợp các phản hồi tích cực của khách hàng về {aspect} "
                        f"để làm video ngắn và gắn lên đầu trang sản phẩm Shopee/TikTok."
                    ),
                    "how_and_when": "Sản xuất và đăng tải nội dung trong vòng 48h.",
                    "success_metric": "Tăng tỷ lệ chuyển đổi trang sản phẩm thêm 1.5% sau 14 ngày.",
                    "effort": "LOW",
                    "impact": "HIGH",
                }
            ]
        return [
            {
                "action_type": "CUSTOMER_CARE",
                "is_marketing": True,
                "title": f"Rà soát quy trình chăm sóc & cải thiện trải nghiệm {aspect}",
                "what_to_do": (
                    f"Kiểm tra toàn bộ phản hồi phàn nàn về {aspect}, liên hệ hỗ trợ "
                    f"khách hàng bị ảnh hưởng và cập nhật hướng dẫn sử dụng trên gian hàng."
                ),
                "how_and_when": "Rà soát và phản hồi khách hàng trong vòng 24h.",
                "success_metric": "Giảm 30% tỷ lệ phàn nàn lặp lại ở khía cạnh này trong 14 ngày.",
                "effort": "LOW",
                "impact": "HIGH",
            }
        ]

    def generate_proposals(
        self,
        insights: list[dict[str, Any]],
        fallback_review_ids: list[str] | None = None,
        critic_feedback: str = "",
        max_actions: int = 5,
    ) -> list[ActionProposal]:
        """Generate a diverse, numerically grounded set of ActionProposals from Insights."""
        proposals: list[ActionProposal] = []
        seen_titles: set[str] = set()
        fallback_ids = list(fallback_review_ids or [])

        for ins in insights:
            if len(proposals) >= max_actions:
                break

            ins_id = ins.get("insight_id", 1)
            aspect = str(ins.get("aspect") or "GENERAL")
            kind = str(ins.get("kind") or "TOP_PAIN")
            conf = str(ins.get("confidence") or "MEDIUM").upper()
            nums = ins.get("numbers") or {}
            stmt = str(ins.get("statement") or "")
            ev_ids = [str(eid) for eid in (ins.get("evidence_ids") or []) if eid]

            # Ensure at least 2 valid evidence_review_ids (Architectural Invariant #2)
            if len(ev_ids) < 2:
                for fid in fallback_ids:
                    if fid not in ev_ids:
                        ev_ids.append(fid)
                    if len(ev_ids) >= 2:
                        break
            if len(ev_ids) < 2:
                continue

            matched_rules = self._find_matching_rules(aspect, kind)
            for rule in matched_rules:
                if len(proposals) >= max_actions:
                    break
                title = str(rule["title"])
                if title in seen_titles:
                    asp_vn = ASPECT_VN_LABELS.get(aspect, aspect)
                    title = f"{title} ({asp_vn} - {kind})"
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                act_type = ActionType(rule["action_type"])
                is_mkt = act_type in MARKETING_ACTION_TYPES
                effort = str(rule.get("effort", "LOW")).upper()
                impact = str(rule.get("impact", "HIGH")).upper()

                sev_pct = float(
                    nums.get("neg_pct")
                    or nums.get("hidden_pct")
                    or nums.get("gap_pct")
                    or nums.get("pos_pct")
                    or 25.0
                )
                prio_score = compute_priority_score(
                    impact=impact,
                    severity_pct=sev_pct,
                    confidence=conf,
                    effort=effort,
                )
                prio_label = (
                    "HIGH" if prio_score >= 2.5 else ("MEDIUM" if prio_score >= 1.5 else "LOW")
                )

                # Ground why_rationale strictly in the verified insight statement
                why_rat = f"Căn cứ trực tiếp từ dữ liệu: {stmt}"
                how_when = str(rule["how_and_when"])
                if (
                    "giờ" not in how_when.lower()
                    and "h" not in how_when.lower()
                    and "ngày" not in how_when.lower()
                ):
                    how_when = f"{how_when.rstrip('.')} trong vòng 48h."

                # If retrying after Critic feedback, ensure extra specificity
                what_do = str(rule["what_to_do"])
                if critic_feedback and "WATERPROOF" in aspect:
                    what_do = what_do.replace("chống thấm 100%", "cải thiện khả năng chống thấm")

                act_idx = len(proposals) + 1
                proposals.append(
                    ActionProposal(
                        action_id=f"act_{act_idx:03d}",
                        action_type=act_type,
                        is_marketing=is_mkt,
                        title=title,
                        description=what_do,
                        what_to_do=what_do,
                        why_rationale=why_rat,
                        how_and_when=how_when,
                        success_metric=str(rule["success_metric"]),
                        target_metric=str(rule["success_metric"]),
                        effort=effort,
                        impact=impact,
                        priority=prio_label,
                        priority_score=prio_score,
                        insight_ids=[ins_id],
                        evidence_review_ids=ev_ids[:4],
                    )
                )

        # Sort by priority_score descending
        proposals.sort(key=lambda p: p.priority_score, reverse=True)
        for idx, prop in enumerate(proposals, start=1):
            prop.action_id = f"act_{idx:03d}"
        return proposals


# CreBy: MenBoyBMN
