"""Pure Python State-Graph Runner for the EcomReview AI Agent (P1 Proposed System).

Executes the deterministic multi-stage workflow:
`Aggregator (SQL/Wilson CI)` -> `Insight Engine` -> `Action Planner` <-> `Hybrid Critic (R1-R7)`
-> `Auto-Repair Fallback` -> `Human Approval Gate (DB Persistence + Audit Trace)`.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from ecomreview.agent.critic import HybridCritic
from ecomreview.agent.insight_engine import InsightEngine
from ecomreview.agent.planner import ActionPlanner
from ecomreview.agent.playbook_loader import load_shop_playbook, normalize_industry
from ecomreview.db.database import DatabaseManager
from ecomreview.schemas import ActionProposal, CriticReport

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class EcomReviewGraphRunner:
    """Pure Python State-Graph orchestrating InsightEngine, ActionPlanner, and HybridCritic."""

    def __init__(
        self,
        db: DatabaseManager | None = None,
        max_retries: int = 2,
        trace_dir: str | Path = "results/traces",
        use_llm: bool | None = None,
        llm_client: Any | None = None,
    ):
        self.db = db or DatabaseManager()
        self.max_retries = max_retries
        t_path = Path(trace_dir)
        self.trace_dir = t_path if t_path.is_absolute() else (_PROJECT_ROOT / t_path)
        self.trace_dir.mkdir(parents=True, exist_ok=True)

        self.insight_engine = InsightEngine(db=self.db, llm_client=llm_client, use_llm=use_llm)
        self.planner = ActionPlanner(llm_client=llm_client, use_llm=use_llm)
        self.critic = HybridCritic()

    def _get_valid_review_ids(self, scenario_tag: str) -> list[str]:
        """Fetch all review IDs belonging to a scenario_tag using read-only connection."""
        with self.db.get_connection(read_only=True) as conn:
            rows = conn.execute(
                "SELECT review_id FROM reviews WHERE scenario_tag = ? ORDER BY review_id",
                (scenario_tag,),
            ).fetchall()
        return [str(r["review_id"]) for r in rows]

    def run_scenario(
        self,
        scenario_tag: str = "real_shop",
        min_n: int = 5,
        max_actions: int = 5,
        persist_db: bool = True,
    ) -> dict[str, Any]:
        """Run the full P1 State-Graph on a scenario and export trace JSON."""
        run_id = f"run_{int(time.time() * 1000)}"
        t0 = time.perf_counter()
        job_id = self.db.log_job_start(
            job_type=f"graph_run_{scenario_tag}",
            details={
                "scenario_tag": scenario_tag,
                "max_retries": self.max_retries,
                "run_id": run_id,
            },
        )

        try:
            run_planner = self.planner
            run_critic = self.critic
            try:
                shop_pb = load_shop_playbook(db=self.db, scenario_tag=scenario_tag)
            except Exception:
                shop_pb = {}
            shop_prof = shop_pb.get("shop_profile") or {}
            eff_industry = normalize_industry(shop_prof.get("industry"))
            brand_voice = dict(shop_prof.get("brand_voice") or {})
            extra_oc = list(brand_voice.get("custom_overclaim_keywords") or [])
            if eff_industry != "raincoat" or any(
                brand_voice.get(k) for k in ("tone", "cskh_notes", "custom_overclaim_keywords")
            ):
                run_planner = ActionPlanner(
                    llm_client=self.planner._llm_client,
                    use_llm=self.planner.use_llm,
                    industry=eff_industry,
                    brand_voice=brand_voice,
                )
                run_critic = HybridCritic(
                    industry=eff_industry,
                    extra_overclaim_keywords=extra_oc,
                )

            # Node 1 & 2: SQL/Wilson CI Aggregator + Insight Engine
            insights = self.insight_engine.generate_insights(
                scenario_tag=scenario_tag, min_n=min_n, persist=persist_db, run_id=run_id
            )
            valid_rev_ids = self._get_valid_review_ids(scenario_tag)
            valid_rev_set = set(valid_rev_ids)

            trace_steps: list[dict[str, Any]] = []
            feedback_prompt = ""
            proposals: list[ActionProposal] = []
            report: CriticReport | None = None
            retries_used = 0

            # Node 3 <-> Node 4: Planner <-> Hybrid Critic Loop
            for attempt in range(self.max_retries + 1):
                proposals = run_planner.generate_proposals(
                    insights=insights,
                    fallback_review_ids=valid_rev_ids,
                    critic_feedback=feedback_prompt,
                    max_actions=max_actions,
                )

                report = run_critic.evaluate(
                    proposals=proposals,
                    insights=insights,
                    valid_review_ids=valid_rev_set,
                )
                trace_steps.append(
                    {
                        "attempt": attempt,
                        "proposals_count": len(proposals),
                        "critic_passed": report.passed,
                        "critic_score": report.score,
                        "violations": [v.model_dump(mode="json") for v in report.violations],
                    }
                )

                if report.passed:
                    retries_used = attempt
                    break

                retries_used = attempt + 1
                feedback_prompt = report.feedback_prompt

            # Node 5: Deterministic Auto-Repair Fallback if Critic still flags any violation
            auto_repaired = False
            if report is not None and not report.passed:
                proposals = run_critic.auto_repair(
                    proposals=proposals,
                    insights=insights,
                    valid_review_ids=valid_rev_set,
                )
                report = run_critic.evaluate(
                    proposals=proposals,
                    insights=insights,
                    valid_review_ids=valid_rev_set,
                )
                auto_repaired = True
                trace_steps.append(
                    {
                        "attempt": "auto_repair",
                        "proposals_count": len(proposals),
                        "critic_passed": report.passed,
                        "critic_score": report.score,
                        "violations": [v.model_dump(mode="json") for v in report.violations],
                    }
                )

            # Node 6: Persist verified actions for Human Approval Gate (archive prior active ones)
            saved_action_ids: list[int] = []
            if persist_db and report is not None:
                critic_violations_json = [v.model_dump(mode="json") for v in report.violations]
                action_records = [
                    {
                        "action_type": prop.action_type.value,
                        "is_marketing": prop.is_marketing,
                        "title": prop.title,
                        "what_to_do": prop.what_to_do or prop.description,
                        "why_rationale": prop.why_rationale,
                        "how_and_when": prop.how_and_when,
                        "success_metric": prop.success_metric or prop.target_metric,
                        "effort": prop.effort,
                        "impact": prop.impact,
                        "priority_score": prop.priority_score,
                        "insight_ids": [int(i) for i in prop.insight_ids if str(i).isdigit()],
                        "evidence_review_ids": prop.evidence_review_ids,
                        "critic_passed": report.passed,
                        "critic_score": report.score,
                        "critic_violations": critic_violations_json,
                        "retries": retries_used,
                        "status": "PENDING",
                        "run_id": run_id,
                    }
                    for prop in proposals
                ]
                saved_action_ids = self.db.replace_scenario_actions(scenario_tag, action_records)

            planner_mode = (
                "llm"
                if run_planner.last_used_llm
                else ("llm_fallback_playbook" if run_planner.use_llm else "playbook")
            )
            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            trace_payload = {
                "scenario_tag": scenario_tag,
                "industry": eff_industry,
                "run_id": run_id,
                "planner_mode": planner_mode,
                "system": "P1_Evidence_Grounded_Critic_Graph",
                "duration_ms": duration_ms,
                "insights_count": len(insights),
                "actions_count": len(proposals),
                "retries_used": retries_used,
                "auto_repaired": auto_repaired,
                "final_critic_passed": report.passed if report else False,
                "final_critic_score": report.score if report else 0.0,
                "trace_steps": trace_steps,
                "insights": insights,
                "actions": [p.model_dump(mode="json") for p in proposals],
            }

            safe_tag = re.sub(r"[^a-zA-Z0-9_\-]", "_", scenario_tag)[:64]
            trace_file = self.trace_dir / f"trace_{safe_tag}.json"
            tmp_trace_file = trace_file.with_suffix(".json.tmp")
            tmp_trace_file.write_text(
                json.dumps(trace_payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(tmp_trace_file, trace_file)

            self.db.log_job_complete(
                job_id,
                status="completed",
                details={
                    "scenario_tag": scenario_tag,
                    "duration_ms": duration_ms,
                    "actions_saved": len(saved_action_ids),
                    "critic_passed": report.passed if report else False,
                },
            )
            return trace_payload
        except Exception as e:
            self.db.log_job_complete(
                job_id,
                status="failed",
                details={"scenario_tag": scenario_tag, "error": str(e)},
            )
            raise


# CreBy: MenBoyBMN
