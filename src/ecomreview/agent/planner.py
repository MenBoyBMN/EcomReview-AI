"""Evidence-Grounded Action Planner (P1 Agent Node) for EcomReview AI.

Generates concrete marketing and operational/product ActionProposals from verified
Insights, grounded in the raincoat domain playbook (`knowledge/playbook_aomua.yaml`).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from ecomreview.agent.insight_engine import ASPECT_VN_LABELS, verify_numbers_in_statement
from ecomreview.llm_provider import get_default_llm_client, is_agent_llm_enabled
from ecomreview.schemas import (
    MARKETING_ACTION_TYPES,
    ActionPlanBatch,
    ActionProposal,
    ActionType,
)

logger = logging.getLogger(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PLANNER_PROMPT_PATH = _PROJECT_ROOT / "prompts" / "planner_v1.md"

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
        prompt_path: str | Path = DEFAULT_PLANNER_PROMPT_PATH,
        llm_client: Any | None = None,
        use_llm: bool | None = None,
    ):
        pb_path = Path(playbook_path)
        self.playbook_path = pb_path if pb_path.is_absolute() else (_PROJECT_ROOT / pb_path)
        pr_path = Path(prompt_path)
        self.prompt_path = pr_path if pr_path.is_absolute() else (_PROJECT_ROOT / pr_path)
        self._llm_client = llm_client
        self.use_llm = is_agent_llm_enabled() if use_llm is None else bool(use_llm)
        self.last_used_llm: bool = False
        self.playbook_data: dict[str, Any] = {"playbook_rules": [], "guardrails": {}}
        if self.playbook_path.exists():
            self.playbook_data = (
                yaml.safe_load(self.playbook_path.read_text(encoding="utf-8")) or {}
            )
        self.rules: list[dict[str, Any]] = self.playbook_data.get("playbook_rules", [])
        if self.prompt_path.exists():
            self.system_prompt = self.prompt_path.read_text(encoding="utf-8")
        else:
            self.system_prompt = "Bạn là Action Planner Agent lập kế hoạch cho gian hàng SME."

    def _find_matching_rules(self, aspect: str, kind: str) -> list[dict[str, Any]]:
        """Find playbook templates matching (aspect, trigger) with graceful fallbacks."""
        exact = [r for r in self.rules if r.get("aspect") == aspect and r.get("trigger") == kind]
        if exact:
            return exact

        asp_vn = ASPECT_VN_LABELS.get(aspect, aspect)

        if kind == "STRENGTH":
            return [
                {
                    "action_type": "CONTENT",
                    "is_marketing": True,
                    "title": f"Khai thác nội dung truyền thông điểm mạnh {asp_vn}",
                    "what_to_do": (
                        f"Tổng hợp các phản hồi tích cực của khách hàng về {asp_vn} "
                        f"để làm video ngắn và gắn lên đầu trang sản phẩm Shopee/TikTok."
                    ),
                    "how_and_when": "Sản xuất và đăng tải nội dung trong vòng 48h.",
                    "success_metric": "Tăng tỷ lệ chuyển đổi trang sản phẩm thêm 1.5% sau 14 ngày.",
                    "effort": "LOW",
                    "impact": "HIGH",
                }
            ]

        by_aspect = [
            r for r in self.rules if r.get("aspect") == aspect and r.get("trigger") != "STRENGTH"
        ]
        if by_aspect:
            return by_aspect[:1]

        # Generic fallback rule for pain/issue insights
        return [
            {
                "action_type": "CUSTOMER_CARE",
                "is_marketing": True,
                "title": f"Rà soát quy trình chăm sóc & cải thiện trải nghiệm {asp_vn}",
                "what_to_do": (
                    f"Kiểm tra toàn bộ phản hồi phàn nàn về {asp_vn}, liên hệ hỗ trợ "
                    f"khách hàng bị ảnh hưởng và cập nhật hướng dẫn sử dụng trên gian hàng."
                ),
                "how_and_when": "Rà soát và phản hồi khách hàng trong vòng 24h.",
                "success_metric": "Giảm 30% tỷ lệ phàn nàn lặp lại ở khía cạnh này trong 14 ngày.",
                "effort": "LOW",
                "impact": "HIGH",
            }
        ]

    def _generate_playbook_proposals(
        self,
        insights: list[dict[str, Any]],
        fallback_review_ids: list[str] | None = None,
        critic_feedback: str = "",
        max_actions: int = 5,
    ) -> list[ActionProposal]:
        """Generate deterministic baseline proposals from domain Playbook rules."""
        proposals: list[ActionProposal] = []
        seen_titles: set[str] = set()
        fallback_ids = list(fallback_review_ids or [])

        for ins in insights:
            if len(proposals) >= max_actions:
                break

            ins_id = int(ins.get("insight_id") or ins.get("id") or 1)
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
                deadline_kws = ("giờ", "ngày", "tuần", "24h", "48h", "72h", "ngay", "trong vòng")
                if not any(dk in how_when.lower() for dk in deadline_kws):
                    how_when = f"{how_when.rstrip('.')} trong vòng 48h."

                what_do = str(rule["what_to_do"])

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

    def _refine_with_llm(
        self,
        baseline: list[ActionProposal],
        insights: list[dict[str, Any]],
        fallback_review_ids: list[str],
        critic_feedback: str,
        max_actions: int,
    ) -> list[ActionProposal]:
        """Refine baseline proposals using LLM while enforcing deterministic guardrails."""
        client = self._llm_client or get_default_llm_client()
        insight_map: dict[int, dict[str, Any]] = {}
        compact_insights: list[dict[str, Any]] = []
        for ins in insights:
            iid = int(ins.get("insight_id") or ins.get("id") or 0)
            if iid <= 0:
                continue
            insight_map[iid] = ins
            compact_insights.append(
                {
                    "insight_id": iid,
                    "kind": ins.get("kind"),
                    "aspect": ins.get("aspect"),
                    "statement": ins.get("statement"),
                    "numbers": ins.get("numbers"),
                    "evidence_ids": ins.get("evidence_ids") or [],
                    "confidence": ins.get("confidence", "MEDIUM"),
                }
            )

        if not insight_map:
            return baseline

        baseline_json = [p.model_dump(mode="json") for p in baseline]
        prompt_parts = [
            f"Danh sách Insights đã kiểm thực số liệu:\n"
            f"{json.dumps(compact_insights, ensure_ascii=False, indent=2)}",
            f"Đề xuất tham chiếu từ Playbook:\n"
            f"{json.dumps(baseline_json, ensure_ascii=False, indent=2)}",
            f"Hãy tạo tối đa {max_actions} đề xuất hành động cụ thể, bám sát từng ngữ cảnh "
            f"và trả về JSON khớp schema ActionPlanBatch.",
        ]
        if critic_feedback.strip():
            prompt_parts.append(f"Phản hồi từ HybridCritic cần khắc phục:\n{critic_feedback}")

        try:
            batch: ActionPlanBatch = client.generate_structured(
                prompt="\n\n".join(prompt_parts),
                schema_cls=ActionPlanBatch,
                system_instruction=self.system_prompt,
            )
        except Exception as exc:
            logger.warning("ActionPlanner LLM call failed (%s). Using playbook baseline.", exc)
            return baseline

        if not batch.proposals:
            return baseline

        valid_pool = set(fallback_review_ids)
        for ins in insight_map.values():
            valid_pool.update(str(e) for e in (ins.get("evidence_ids") or []) if e)

        deadline_kws = ("giờ", "ngày", "tuần", "24h", "48h", "72h", "ngay", "trong vòng")
        default_iid = next(iter(insight_map))
        refined: list[ActionProposal] = []

        for idx, raw_prop in enumerate(batch.proposals[:max_actions]):
            valid_iids = [
                int(i) for i in raw_prop.insight_ids if str(i).isdigit() and int(i) in insight_map
            ]
            if not valid_iids:
                fb_prop = baseline[min(idx, len(baseline) - 1)]
                valid_iids = [
                    int(i)
                    for i in fb_prop.insight_ids
                    if str(i).isdigit() and int(i) in insight_map
                ] or [default_iid]

            ref_ins = insight_map[valid_iids[0]]
            ref_ev = [str(e) for e in (ref_ins.get("evidence_ids") or []) if e]
            ev_ids = [str(e) for e in raw_prop.evidence_review_ids if str(e) in valid_pool]
            for cand in ref_ev + fallback_review_ids:
                if cand not in ev_ids:
                    ev_ids.append(cand)
                if len(ev_ids) >= 2:
                    break
            if len(ev_ids) < 2:
                continue

            nums: dict[str, Any] = {}
            for iid in valid_iids:
                for k, v in (insight_map[iid].get("numbers") or {}).items():
                    nums[f"{iid}_{k}"] = v
                    nums[k] = v
            stmt = str(ref_ins.get("statement") or "")
            why_rat = raw_prop.why_rationale.strip()
            if not why_rat or not verify_numbers_in_statement(why_rat, nums):
                why_rat = f"Căn cứ trực tiếp từ dữ liệu: {stmt}"

            how_when = raw_prop.how_and_when.strip() or "Triển khai trên gian hàng trong vòng 48h."
            if not any(dk in how_when.lower() for dk in deadline_kws):
                how_when = f"{how_when.rstrip('.')} trong vòng 48h."

            act_type = raw_prop.action_type
            is_mkt = act_type in MARKETING_ACTION_TYPES
            eff = str(raw_prop.effort or "LOW").upper()
            if eff not in {"LOW", "MEDIUM", "HIGH"}:
                eff = "LOW"
            imp = str(raw_prop.impact or "HIGH").upper()
            if imp not in {"LOW", "MEDIUM", "HIGH"}:
                imp = "HIGH"

            sev_pct = float(
                nums.get("neg_pct")
                or nums.get("hidden_pct")
                or nums.get("gap_pct")
                or nums.get("pos_pct")
                or 25.0
            )
            conf = str(ref_ins.get("confidence") or "MEDIUM").upper()
            prio_score = compute_priority_score(
                impact=imp, severity_pct=sev_pct, confidence=conf, effort=eff
            )
            prio_label = "HIGH" if prio_score >= 2.5 else ("MEDIUM" if prio_score >= 1.5 else "LOW")
            what_do = (raw_prop.what_to_do or raw_prop.description).strip()
            succ = (raw_prop.success_metric or raw_prop.target_metric).strip()

            refined.append(
                ActionProposal(
                    action_id=f"act_{len(refined) + 1:03d}",
                    action_type=act_type,
                    is_marketing=is_mkt,
                    title=raw_prop.title.strip() or baseline[min(idx, len(baseline) - 1)].title,
                    description=what_do,
                    what_to_do=what_do,
                    why_rationale=why_rat,
                    how_and_when=how_when,
                    success_metric=succ,
                    target_metric=succ,
                    effort=eff,
                    impact=imp,
                    priority=prio_label,
                    priority_score=prio_score,
                    insight_ids=valid_iids,
                    evidence_review_ids=ev_ids[:4],
                )
            )

        if not refined:
            return baseline

        refined.sort(key=lambda p: p.priority_score, reverse=True)
        for idx, prop in enumerate(refined, start=1):
            prop.action_id = f"act_{idx:03d}"
        return refined

    def generate_proposals(
        self,
        insights: list[dict[str, Any]],
        fallback_review_ids: list[str] | None = None,
        critic_feedback: str = "",
        max_actions: int = 5,
    ) -> list[ActionProposal]:
        """Generate grounded ActionProposals from Insights (Playbook + optional LLM refinement)."""
        self.last_used_llm = False
        fallback_ids = list(fallback_review_ids or [])
        baseline = self._generate_playbook_proposals(
            insights=insights,
            fallback_review_ids=fallback_ids,
            critic_feedback=critic_feedback,
            max_actions=max_actions,
        )
        if not self.use_llm or not baseline:
            return baseline

        refined = self._refine_with_llm(
            baseline=baseline,
            insights=insights,
            fallback_review_ids=fallback_ids,
            critic_feedback=critic_feedback,
            max_actions=max_actions,
        )
        self.last_used_llm = refined is not baseline
        return refined


# CreBy: MenBoyBMN
