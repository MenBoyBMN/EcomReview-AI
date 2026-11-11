"""Automated Groundedness, Completeness, and Safety Evaluation for RQ3 (Task 8.1).

Evaluates three agent configurations across the 10 raincoat business scenarios (S1..S10):
1. `P0 (Single-Prompt Baseline)`: Direct LLM prompt without SQL Aggregator or Critic loop.
2. `P1-no-Critic (Iteration 0)`: SQL Aggregator + InsightEngine + ActionPlanner BEFORE HybridCritic.
3. `P1-Full (Proposed State-Graph)`: Full pipeline after HybridCritic R1-R7 & Auto-Repair.

Five Quantitative Metrics (0-100%):
- `evidence_validity_pct`: Actions citing >= 2 real review_ids belonging to valid insights in DB.
- `numeric_consistency_pct`: Actions whose `why_rationale` numbers match 100% with SQL Insight.
- `quote_fidelity_pct`: Referenced evidence reviews whose extracted quotes match verbatim raw text.
- `structural_completeness_pct`: Actions containing 4 required fields + explicit deadline keyword.
- `policy_claim_safety_pct`: Actions free of overclaiming (R4), policy violations (R7), and R5.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from ecomreview.agent.critic import HybridCritic
from ecomreview.agent.insight_engine import verify_numbers_in_statement
from ecomreview.agent.planner import ActionPlanner
from ecomreview.db.database import DatabaseManager
from ecomreview.schemas import MARKETING_ACTION_TYPES, ActionProposal


def bootstrap_mean_ci(
    values: list[float],
    n_boot: int = 2000,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Compute sample mean and 95% percentile bootstrap confidence interval."""
    if not values:
        return 0.0, 0.0, 0.0
    arr = np.asarray(values, dtype=float)
    mean_val = float(np.mean(arr))
    if len(arr) <= 1 or np.allclose(arr, arr[0]):
        return round(mean_val, 2), round(mean_val, 2), round(mean_val, 2)

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(arr), size=(n_boot, len(arr)))
    boot_means = np.mean(arr[idx], axis=1)
    ci_low = float(np.percentile(boot_means, 2.5))
    ci_high = float(np.percentile(boot_means, 97.5))
    return round(mean_val, 2), round(ci_low, 2), round(ci_high, 2)


class GroundednessEvaluator:
    """Quantitative evaluator for RQ3 Action Proposals across P0, P1-no-Critic, and P1-Full."""

    def __init__(
        self,
        db_path: str | Path = "data/ecomreview.db",
        playbook_path: str | Path = "knowledge/playbook_aomua.yaml",
    ):
        self.db = DatabaseManager(db_path)
        self.critic = HybridCritic(playbook_path=playbook_path)
        self.planner = ActionPlanner(playbook_path=playbook_path)

    def _fetch_scenario_review_quotes(self, scenario_tag: str) -> dict[str, dict[str, Any]]:
        """Fetch all reviews and their opinion evidence quotes for a scenario from DB."""
        review_map: dict[str, dict[str, Any]] = {}
        with self.db.get_connection(read_only=True) as conn:
            rev_rows = conn.execute(
                "SELECT review_id, text_raw, text_norm FROM reviews WHERE scenario_tag = ?",
                (scenario_tag,),
            ).fetchall()
            for r in rev_rows:
                rid = str(r["review_id"])
                review_map[rid] = {
                    "text_raw": str(r["text_raw"] or ""),
                    "text_norm": str(r["text_norm"] or ""),
                    "quotes": [],
                }

            op_rows = conn.execute(
                """
                SELECT o.review_id, o.evidence, o.evidence_ok
                FROM opinions o
                JOIN reviews r ON o.review_id = r.review_id AND o.scenario_tag = r.scenario_tag
                WHERE r.scenario_tag = ?
                """,
                (scenario_tag,),
            ).fetchall()
            for op in op_rows:
                rid = str(op["review_id"])
                if rid in review_map:
                    review_map[rid]["quotes"].append(
                        {
                            "evidence": str(op["evidence"] or ""),
                            "evidence_ok": bool(op["evidence_ok"]),
                        }
                    )
        return review_map

    def evaluate_proposals(
        self,
        proposals: list[ActionProposal],
        insights: list[dict[str, Any]],
        scenario_tag: str,
    ) -> dict[str, float]:
        """Compute the 5 groundedness/completeness/safety metrics + Critic score on proposals."""
        if not proposals:
            return {
                "actions_count": 0.0,
                "evidence_validity_pct": 0.0,
                "numeric_consistency_pct": 0.0,
                "quote_fidelity_pct": 0.0,
                "structural_completeness_pct": 0.0,
                "policy_claim_safety_pct": 0.0,
                "critic_score": 1.0,
                "critic_passed": 0.0,
            }

        review_map = self._fetch_scenario_review_quotes(scenario_tag)
        valid_rev_ids = set(review_map.keys())

        insight_map: dict[str, dict[str, Any]] = {}
        for idx, ins in enumerate(insights, start=1):
            iid = str(ins.get("insight_id", idx))
            insight_map[iid] = ins
            for eid in ins.get("evidence_ids") or []:
                valid_rev_ids.add(str(eid))

        ev_valid_flags: list[float] = []
        num_cons_flags: list[float] = []
        quote_fid_flags: list[float] = []
        struct_comp_flags: list[float] = []
        safety_flags: list[float] = []

        for prop in proposals:
            # 1. Evidence Validity: valid insight_ids AND >= 2 valid review_ids in DB
            ref_inss = [str(i) for i in prop.insight_ids]
            inss_ok = bool(ref_inss) and all(i in insight_map for i in ref_inss)
            ev_ids = [str(e) for e in prop.evidence_review_ids if str(e).strip()]
            revs_ok = len(ev_ids) >= 2 and all(e in valid_rev_ids for e in ev_ids)
            ev_valid_flags.append(100.0 if (inss_ok and revs_ok) else 0.0)

            # 2. Numeric Consistency: numbers in why_rationale match referenced insight SQL stats
            merged_numbers: dict[str, Any] = {}
            for i_key in ref_inss:
                if i_key in insight_map:
                    merged_numbers.update(insight_map[i_key].get("numbers") or {})
            if not merged_numbers and insights:
                for ins in insights:
                    merged_numbers.update(ins.get("numbers") or {})
            num_ok = bool(ref_inss and inss_ok) and verify_numbers_in_statement(
                prop.why_rationale, merged_numbers
            )
            num_cons_flags.append(100.0 if num_ok else 0.0)

            # 3. Quote Fidelity: cited evidence_review_ids exist in DB and have verbatim quotes
            if not ev_ids:
                quote_fid_flags.append(0.0)
            else:
                matched_quotes = 0
                for eid in ev_ids:
                    rev_info = review_map.get(eid)
                    if not rev_info:
                        continue
                    raw_low = rev_info["text_raw"].lower()
                    norm_low = rev_info["text_norm"].lower()
                    quotes = rev_info["quotes"]
                    if quotes and all(
                        q["evidence"].lower() in raw_low or q["evidence"].lower() in norm_low
                        for q in quotes
                        if q["evidence"]
                    ):
                        matched_quotes += 1
                    elif not quotes and raw_low:
                        matched_quotes += 1
                quote_fid_flags.append(100.0 * (matched_quotes / len(ev_ids)))

            # 4. Structural Completeness: 4 non-empty fields + explicit deadline keyword
            wtd = (prop.what_to_do or prop.description or "").strip()
            why = (prop.why_rationale or "").strip()
            how = (prop.how_and_when or "").strip()
            kpi = (prop.success_metric or prop.target_metric or "").strip()
            has_four = len(wtd) >= 10 and len(why) >= 10 and len(how) >= 5 and len(kpi) >= 5
            has_deadline = any(kw in how.lower() for kw in self.critic.deadline_keywords)
            struct_comp_flags.append(100.0 if (has_four and has_deadline) else 0.0)

            # 5. Policy & Claim Safety: no R4 overclaiming, no R7 prohibited policy, R5 flag sync
            combined_low = f"{prop.title} {wtd} {why} {how}".lower()
            has_overclaim = any(kw in combined_low for kw in self.critic.overclaim_keywords)
            has_policy_viol = any(
                kw in combined_low for kw in self.critic.prohibited_policy_keywords
            )
            expected_mkt = prop.action_type in MARKETING_ACTION_TYPES
            mkt_sync = prop.is_marketing == expected_mkt
            safety_flags.append(
                100.0 if (not has_overclaim and not has_policy_viol and mkt_sync) else 0.0
            )

        critic_rep = self.critic.evaluate(
            proposals=proposals,
            insights=insights,
            valid_review_ids=valid_rev_ids,
        )

        return {
            "actions_count": float(len(proposals)),
            "evidence_validity_pct": round(float(np.mean(ev_valid_flags)), 2),
            "numeric_consistency_pct": round(float(np.mean(num_cons_flags)), 2),
            "quote_fidelity_pct": round(float(np.mean(quote_fid_flags)), 2),
            "structural_completeness_pct": round(float(np.mean(struct_comp_flags)), 2),
            "policy_claim_safety_pct": round(float(np.mean(safety_flags)), 2),
            "critic_score": float(critic_rep.score),
            "critic_passed": 100.0 if critic_rep.passed else 0.0,
        }

    def run_rq3_automated_benchmark(
        self,
        candidates_path: str | Path = "results/rq3_candidates.json",
        traces_dir: str | Path = "results/traces",
        output_csv: str | Path = "results/rq3_automated.csv",
    ) -> dict[str, Any]:
        """Run full automated comparison across S1..S10 for P0, P1-no-Critic, and P1-Full."""
        cand_file = Path(candidates_path)
        t_dir = Path(traces_dir)
        candidates = json.loads(cand_file.read_text(encoding="utf-8"))

        per_system_rows: dict[str, list[dict[str, float]]] = {
            "P0_Single_Prompt": [],
            "P1_No_Critic": [],
            "P1_Full_Proposed": [],
        }
        scenario_details: list[dict[str, Any]] = []

        for item in candidates:
            stag = str(item["scenario_tag"])
            trace_path = t_dir / f"trace_{stag}.json"
            trace_data = json.loads(trace_path.read_text(encoding="utf-8"))
            insights = trace_data.get("insights", [])

            valid_revs = list(self._fetch_scenario_review_quotes(stag).keys())

            # 1. P0 Baseline
            p0_props = [ActionProposal.model_validate(a) for a in item["P0_Baseline"]["actions"]]
            p0_metrics = self.evaluate_proposals(p0_props, insights, stag)
            per_system_rows["P0_Single_Prompt"].append(p0_metrics)

            # 2. P1-no-Critic (Iteration 0 before HybridCritic & Auto-Repair)
            p1_init_props = self.planner.generate_proposals(
                insights=insights,
                fallback_review_ids=valid_revs,
                critic_feedback="",
                max_actions=4,
            )
            p1_nc_metrics = self.evaluate_proposals(p1_init_props, insights, stag)
            per_system_rows["P1_No_Critic"].append(p1_nc_metrics)

            # 3. P1-Full (After HybridCritic & Auto-Repair)
            p1_full_props = [
                ActionProposal.model_validate(a) for a in item["P1_Proposed"]["actions"]
            ]
            p1_full_metrics = self.evaluate_proposals(p1_full_props, insights, stag)
            per_system_rows["P1_Full_Proposed"].append(p1_full_metrics)

            scenario_details.append(
                {
                    "scenario_tag": stag,
                    "P0": p0_metrics,
                    "P1_No_Critic": p1_nc_metrics,
                    "P1_Full": p1_full_metrics,
                }
            )

        metric_keys = [
            "evidence_validity_pct",
            "numeric_consistency_pct",
            "quote_fidelity_pct",
            "structural_completeness_pct",
            "policy_claim_safety_pct",
            "critic_score",
            "critic_passed",
        ]

        summary_rows: list[dict[str, Any]] = []
        for sys_name, rows in per_system_rows.items():
            row_out: dict[str, Any] = {
                "system": sys_name,
                "scenarios_count": len(rows),
            }
            for mk in metric_keys:
                vals = [r[mk] for r in rows]
                mean_v, ci_l, ci_h = bootstrap_mean_ci(vals, n_boot=2000, seed=42)
                row_out[mk] = mean_v
                row_out[f"{mk}_ci_low"] = ci_l
                row_out[f"{mk}_ci_high"] = ci_h
                row_out[f"{mk}_formatted"] = f"{mean_v:.2f} [{ci_l:.2f} - {ci_h:.2f}]"
            summary_rows.append(row_out)

        out_path = Path(output_csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if summary_rows:
            fieldnames = list(summary_rows[0].keys())
            with out_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(summary_rows)

        return {
            "summary": summary_rows,
            "scenario_details": scenario_details,
            "output_csv": str(out_path),
        }


if __name__ == "__main__":
    evaluator = GroundednessEvaluator()
    res = evaluator.run_rq3_automated_benchmark()
    for s in res["summary"]:
        print(
            f"{s['system']}: EvValid={s['evidence_validity_pct']}%, "
            f"NumCons={s['numeric_consistency_pct']}%, "
            f"QuoteFid={s['quote_fidelity_pct']}%, "
            f"StructComp={s['structural_completeness_pct']}%, "
            f"Safety={s['policy_claim_safety_pct']}%, "
            f"CriticScore={s['critic_score']}, PassRate={s['critic_passed']}%"
        )

# CreBy: MenBoyBMN
