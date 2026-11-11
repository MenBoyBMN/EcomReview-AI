"""Hybrid Critic (7 Deterministic Rules R1-R7 + Rubric Scoring & Auto-Repair).

Enforces the 7 domain guardrails on ActionProposals before presenting to the
Human-in-the-Loop Approval Gate:
- R1: Evidence Existence (valid insight_ids & >= 2 valid evidence_review_ids)
- R2: Numeric Grounding (verify_numbers_in_statement against referenced insights)
- R3: Action Completeness (4 fields non-empty & explicit deadline keyword in how_and_when)
- R4: No Overclaiming on WATERPROOF ("chống thấm 100%", "chống nước tuyệt đối", etc.)
- R5: Marketing Flag Sync (is_marketing matches MARKETING_ACTION_TYPES)
- R6: Anti-Duplication (pairwise word-level Jaccard similarity <= 0.80)
- R7: Platform Policy Safety (no review bribery/manipulation like "tặng tiền đổi 5 sao")
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from ecomreview.agent.insight_engine import verify_numbers_in_statement
from ecomreview.schemas import (
    MARKETING_ACTION_TYPES,
    ActionProposal,
    CriticReport,
    CriticViolation,
)


def _tokenize_words(text: str) -> set[str]:
    """Tokenize Vietnamese text into normalized word set."""
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) > 1}


def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Compute word-level Jaccard similarity between two token sets."""
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


DEFAULT_OVERCLAIM_KEYWORDS = [
    "chống thấm 100%",
    "chống nước tuyệt đối",
    "không bao giờ thấm",
    "vĩnh viễn không rách",
    "bảo hành trọn đời",
]

DEFAULT_PROHIBITED_POLICY_KEYWORDS = [
    "tặng tiền đổi 5 sao",
    "hoàn tiền nếu đánh giá 5 sao",
    "xóa đánh giá 1 sao",
    "mua hộ đánh giá ảo",
    "chuyển khoản ngoài sàn",
    "zalo cá nhân để nhận hoàn tiền",
]

DEFAULT_DEADLINE_KEYWORDS = [
    "giờ",
    "ngày",
    "tuần",
    "24h",
    "48h",
    "72h",
    "ngay",
    "trong vòng",
]


class HybridCritic:
    """Deterministic R1-R7 Rule Engine + Quality Rubric Evaluator for ActionProposals."""

    def __init__(self, playbook_path: str | Path = "knowledge/playbook_aomua.yaml"):
        self.playbook_path = Path(playbook_path)
        guardrails: dict[str, Any] = {}
        if self.playbook_path.exists():
            data = yaml.safe_load(self.playbook_path.read_text(encoding="utf-8")) or {}
            guardrails = data.get("guardrails", {})

        self.overclaim_keywords: list[str] = [
            k.lower() for k in guardrails.get("overclaim_keywords", DEFAULT_OVERCLAIM_KEYWORDS)
        ]
        self.prohibited_policy_keywords: list[str] = [
            k.lower()
            for k in guardrails.get(
                "prohibited_policy_keywords", DEFAULT_PROHIBITED_POLICY_KEYWORDS
            )
        ]
        self.deadline_keywords: list[str] = [
            k.lower() for k in guardrails.get("deadline_keywords", DEFAULT_DEADLINE_KEYWORDS)
        ]

    def evaluate(
        self,
        proposals: list[ActionProposal],
        insights: list[dict[str, Any]],
        valid_review_ids: set[str] | None = None,
    ) -> CriticReport:
        """Evaluate a list of ActionProposals against deterministic rules R1-R7 and rubric."""
        violations: list[CriticViolation] = []
        insight_map: dict[str, dict[str, Any]] = {}
        all_known_review_ids: set[str] = set(valid_review_ids or set())

        for idx, ins in enumerate(insights, start=1):
            iid = str(ins.get("insight_id", idx))
            insight_map[iid] = ins
            for eid in ins.get("evidence_ids") or []:
                all_known_review_ids.add(str(eid))

        if not proposals:
            violations.append(
                CriticViolation(
                    rule_id="R3",
                    action_id="NONE",
                    message="Danh sách hành động rỗng (không có đề xuất nào được sinh ra).",
                    auto_fixable=False,
                )
            )
            return CriticReport(
                passed=False,
                score=1.0,
                violations=violations,
                feedback_prompt="Cần sinh ít nhất 1 đề xuất hành động hợp lệ từ Insights.",
            )

        # Evaluate R1 - R5 and R7 per proposal
        for prop in proposals:
            aid = prop.action_id

            # R1: Evidence Existence
            ref_inss = [str(i) for i in prop.insight_ids]
            missing_inss = [i for i in ref_inss if i not in insight_map]
            if not ref_inss or missing_inss:
                violations.append(
                    CriticViolation(
                        rule_id="R1",
                        action_id=aid,
                        message=(
                            f"Vi phạm R1 (Evidence Existence): insight_ids {prop.insight_ids} "
                            f"không tồn tại trong tập Insights hợp lệ {list(insight_map.keys())}."
                        ),
                        auto_fixable=True,
                    )
                )

            ev_ids = [str(e) for e in prop.evidence_review_ids if str(e).strip()]
            if len(ev_ids) < 2:
                violations.append(
                    CriticViolation(
                        rule_id="R1",
                        action_id=aid,
                        message=(
                            f"Vi phạm R1 (Evidence Existence): Cần >= 2 evidence_review_ids, "
                            f"hiện chỉ có {len(ev_ids)}."
                        ),
                        auto_fixable=True,
                    )
                )
            elif all_known_review_ids:
                unknown_revs = [e for e in ev_ids if e not in all_known_review_ids]
                if unknown_revs:
                    violations.append(
                        CriticViolation(
                            rule_id="R1",
                            action_id=aid,
                            message=(
                                f"Vi phạm R1 (Evidence Existence): Mã review {unknown_revs} "
                                f"không tồn tại trong cơ sở dữ liệu kịch bản."
                            ),
                            auto_fixable=True,
                        )
                    )

            # R2: Numeric Grounding
            merged_numbers: dict[str, Any] = {}
            for i_str in ref_inss:
                if i_str in insight_map:
                    ins_nums = insight_map[i_str].get("numbers") or {}
                    for k, v in ins_nums.items():
                        merged_numbers[f"{i_str}_{k}"] = v
                        merged_numbers[k] = v

            if merged_numbers and prop.why_rationale:
                if not verify_numbers_in_statement(prop.why_rationale, merged_numbers):
                    violations.append(
                        CriticViolation(
                            rule_id="R2",
                            action_id=aid,
                            message=(
                                f"Vi phạm R2 (Numeric Grounding): Số liệu trong why_rationale "
                                f"('{prop.why_rationale}') không khớp với số liệu SQL của Insight."
                            ),
                            auto_fixable=True,
                        )
                    )

            # R3: Action Completeness & Deadline Keyword
            wtd = (prop.what_to_do or prop.description or "").strip()
            why = (prop.why_rationale or "").strip()
            how = (prop.how_and_when or "").strip()
            met = (prop.success_metric or prop.target_metric or "").strip()

            if len(wtd) < 10 or len(why) < 10 or len(how) < 5 or len(met) < 5:
                violations.append(
                    CriticViolation(
                        rule_id="R3",
                        action_id=aid,
                        message=(
                            "Vi phạm R3 (Action Completeness): Thiếu thông tin ở 1 trong 4 trường "
                            "(what_to_do, why_rationale, how_and_when, success_metric)."
                        ),
                        auto_fixable=True,
                    )
                )
            else:
                how_lower = how.lower()
                if not any(dk in how_lower for dk in self.deadline_keywords):
                    violations.append(
                        CriticViolation(
                            rule_id="R3",
                            action_id=aid,
                            message=(
                                f"Vi phạm R3 (Deadline Missing): Trường how_and_when ('{how}') "
                                f"thiếu mốc thời gian cụ thể (24h, 48h, ngày, tuần)."
                            ),
                            auto_fixable=True,
                        )
                    )

            # R4: No Overclaiming on Waterproof / Durability
            combined_text = f"{prop.title} {wtd} {why} {how}".lower()
            for over_kw in self.overclaim_keywords:
                if over_kw in combined_text:
                    violations.append(
                        CriticViolation(
                            rule_id="R4",
                            action_id=aid,
                            message=(
                                f"Vi phạm R4 (No Overclaiming): Phát hiện cụm từ cam kết quá mức "
                                f"'{over_kw}' trong đề xuất hành động."
                            ),
                            auto_fixable=True,
                        )
                    )
                    break

            # R5: Marketing Flag Sync
            expected_mkt = prop.action_type in MARKETING_ACTION_TYPES
            if prop.is_marketing != expected_mkt:
                violations.append(
                    CriticViolation(
                        rule_id="R5",
                        action_id=aid,
                        message=(
                            f"Vi phạm R5 (Marketing Flag): action_type={prop.action_type.value} "
                            f"nhưng is_marketing={prop.is_marketing} (kỳ vọng {expected_mkt})."
                        ),
                        auto_fixable=True,
                    )
                )

            # R7: Platform Policy Safety
            for pol_kw in self.prohibited_policy_keywords:
                if pol_kw in combined_text:
                    violations.append(
                        CriticViolation(
                            rule_id="R7",
                            action_id=aid,
                            message=(
                                f"Vi phạm R7 (Platform Policy Safety): Đề xuất chứa hành vi cấm "
                                f"trên sàn TMĐT ('{pol_kw}')."
                            ),
                            auto_fixable=True,
                        )
                    )
                    break

        # R6: Anti-Duplication (pairwise Jaccard similarity <= 0.80)
        token_sets = [
            _tokenize_words(f"{p.title} {p.what_to_do or p.description}") for p in proposals
        ]
        for i in range(len(proposals)):
            for j in range(i + 1, len(proposals)):
                sim = _jaccard_similarity(token_sets[i], token_sets[j])
                if sim > 0.80:
                    violations.append(
                        CriticViolation(
                            rule_id="R6",
                            action_id=proposals[j].action_id,
                            message=(
                                f"Vi phạm R6 (Anti-Duplication): Đề xuất {proposals[j].action_id} "
                                f"trùng lặp ngữ nghĩa với {proposals[i].action_id} "
                                f"(Jaccard={sim:.2f} > 0.80)."
                            ),
                            auto_fixable=True,
                        )
                    )

        # Rubric Score calculation (5.0 base, minus penalty per violation)
        distinct_rules = {v.rule_id for v in violations}
        score = max(1.0, round(5.0 - 0.85 * len(distinct_rules) - 0.15 * len(violations), 2))
        passed = len(violations) == 0 and score >= 3.5

        feedback_lines = [f"- [{v.rule_id}] ({v.action_id}): {v.message}" for v in violations]
        return CriticReport(
            passed=passed,
            score=score,
            violations=violations,
            feedback_prompt="\n".join(feedback_lines),
        )

    def auto_repair(
        self,
        proposals: list[ActionProposal],
        insights: list[dict[str, Any]],
        valid_review_ids: set[str] | None = None,
    ) -> list[ActionProposal]:
        """Deterministically repair R1-R7 violations on ActionProposals."""
        if not insights:
            return proposals

        insight_map = {str(ins.get("insight_id", i + 1)): ins for i, ins in enumerate(insights)}
        default_ins = insights[0]
        default_iid = default_ins.get("insight_id", 1)
        all_valid_revs = list(valid_review_ids or [])
        for ins in insights:
            for eid in ins.get("evidence_ids") or []:
                if str(eid) not in all_valid_revs:
                    all_valid_revs.append(str(eid))

        repaired: list[ActionProposal] = []
        kept_tokens: list[set[str]] = []

        for prop in proposals:
            p = prop.model_copy(deep=True)

            # Fix R5: Sync is_marketing
            p.is_marketing = p.action_type in MARKETING_ACTION_TYPES

            # Fix R1: Ensure valid insight_ids and >= 2 valid evidence_review_ids
            valid_iids = [i for i in p.insight_ids if str(i) in insight_map]
            if not valid_iids:
                valid_iids = [default_iid]
            p.insight_ids = valid_iids

            ref_ins = insight_map[str(valid_iids[0])]
            ins_ev = [str(e) for e in (ref_ins.get("evidence_ids") or []) if e]
            valid_evs = [
                str(e)
                for e in p.evidence_review_ids
                if (not all_valid_revs or str(e) in all_valid_revs)
            ]
            for cand_e in ins_ev + all_valid_revs:
                if len(valid_evs) >= 2:
                    break
                if cand_e not in valid_evs:
                    valid_evs.append(cand_e)
            p.evidence_review_ids = valid_evs[:4]

            # Fix R2: Ground why_rationale in referenced insight statement
            if not p.why_rationale or not verify_numbers_in_statement(
                p.why_rationale, ref_ins.get("numbers") or {}
            ):
                p.why_rationale = f"Căn cứ trực tiếp từ dữ liệu: {ref_ins.get('statement', '')}"

            # Fix R3: Ensure non-empty fields & deadline keyword
            if len((p.what_to_do or "").strip()) < 10:
                p.what_to_do = (
                    "Kiểm tra chất lượng lô hàng áo mưa và cập nhật thông tin hướng dẫn "
                    "chi tiết trên trang sản phẩm Shopee/TikTok."
                )
                p.description = p.what_to_do
            if len((p.success_metric or "").strip()) < 5:
                p.success_metric = "Giảm 25% tỷ lệ phản hồi tiêu cực trong 14 ngày tới."
                p.target_metric = p.success_metric
            how_clean = (p.how_and_when or "").strip()
            if len(how_clean) < 5 or not any(
                dk in how_clean.lower() for dk in self.deadline_keywords
            ):
                p.how_and_when = f"{how_clean.rstrip('.')} trong vòng 48h.".strip()

            # Fix R4 & R7: Sanitize overclaiming and prohibited policy keywords
            for kw in self.overclaim_keywords:
                p.title = re.sub(
                    re.escape(kw), "cải thiện khả năng chống thấm", p.title, flags=re.IGNORECASE
                )
                p.what_to_do = re.sub(
                    re.escape(kw),
                    "cải thiện khả năng chống thấm",
                    p.what_to_do,
                    flags=re.IGNORECASE,
                )
                p.description = p.what_to_do
            for kw in self.prohibited_policy_keywords:
                p.title = re.sub(
                    re.escape(kw),
                    "hỗ trợ đổi trả chính hãng qua hệ thống sàn",
                    p.title,
                    flags=re.IGNORECASE,
                )
                p.what_to_do = re.sub(
                    re.escape(kw),
                    "hỗ trợ bảo hành đổi mới 1-1 qua cổng CSKH chính thức của sàn",
                    p.what_to_do,
                    flags=re.IGNORECASE,
                )
                p.description = p.what_to_do

            # Fix R6: Deduplicate actions with Jaccard > 0.80
            toks = _tokenize_words(f"{p.title} {p.what_to_do}")
            if any(_jaccard_similarity(toks, prev) > 0.80 for prev in kept_tokens):
                continue
            kept_tokens.append(toks)
            repaired.append(p)

        return repaired


# CreBy: MenBoyBMN
