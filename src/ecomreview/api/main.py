"""FastAPI Backend Service exposing 10 RESTful Endpoints for EcomReview AI.

Endpoints:
1. GET  /api/v1/health
2. POST /api/v1/reviews/upload
3. POST /api/v1/analyze/run
4. GET  /api/v1/jobs/{job_id}
5. GET  /api/v1/stats/overview
6. GET  /api/v1/insights
7. POST /api/v1/actions/generate
8. GET  /api/v1/actions
9. POST /api/v1/actions/{action_id}/decision
10. GET /api/v1/reviews
"""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ecomreview.agent.graph_runner import EcomReviewGraphRunner
from ecomreview.agent.insight_engine import InsightEngine
from ecomreview.agent.tools_aggregator import (
    get_aspect_sentiment_stats,
    get_hidden_complaints,
    get_platform_gap_stats,
    wilson_ci_pct,
)
from ecomreview.analyze.b1_rule import B1RuleAnalyzer
from ecomreview.db.database import DatabaseManager
from ecomreview.normalize import normalize_social_text
from ecomreview.security import scrub_pii


class ReviewUploadItem(BaseModel):
    """Single review record for batch ingestion."""

    review_id: str
    platform: str = "tiktok"
    shop: str = "shop_a"
    product: str = "ao_mua_da_ca"
    rating: int = Field(default=5, ge=1, le=5)
    text: str
    overall_sentiment: str | None = None
    opinions: list[dict[str, Any]] = Field(default_factory=list)


class ReviewUploadRequest(BaseModel):
    """Batch review upload request payload."""

    scenario_tag: str = "real_shop"
    reviews: list[ReviewUploadItem]


class AnalyzeRunRequest(BaseModel):
    """Request payload to trigger ABSA + InsightEngine on a scenario."""

    scenario_tag: str = "real_shop"
    analyzer_method: str = "b1_rule"
    min_n: int = 5


class ActionGenerateRequest(BaseModel):
    """Request payload to trigger the State-Graph ActionPlanner + HybridCritic."""

    scenario_tag: str = "real_shop"
    min_n: int = 5
    max_actions: int = 5


class ActionDecisionRequest(BaseModel):
    """Human-in-the-loop approval/edit/rejection payload."""

    decision: str = Field(description="APPROVED, EDITED, or REJECTED")
    note: str = ""
    edited_content: str = ""
    reason_category: str = ""


def create_app(db_path: str | None = None) -> FastAPI:
    """Factory creating the FastAPI application with configurable database path."""
    app = FastAPI(
        title="EcomReview AI API",
        description=(
            "Vietnamese Aspect-Based Sentiment Analysis & Evidence-Grounded "
            "Marketing Action Planning API for Raincoat E-Commerce SMEs."
        ),
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _get_db() -> DatabaseManager:
        return DatabaseManager(db_path or os.getenv("ECOMREVIEW_SQLITE_PATH"))

    @app.get("/api/v1/health", tags=["System"])
    def health_check() -> dict[str, Any]:
        """1. Check API and database health status."""
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            rev_count = conn.execute("SELECT COUNT(*) AS cnt FROM reviews").fetchone()["cnt"]
        demo_mode = os.getenv("DEMO_CACHE_MODE", "true").lower() == "true"
        return {
            "status": "healthy",
            "database": "connected",
            "total_reviews_in_db": int(rev_count),
            "demo_cache_mode": demo_mode,
        }

    @app.post("/api/v1/reviews/upload", tags=["Ingestion"])
    def upload_reviews(payload: ReviewUploadRequest) -> dict[str, Any]:
        """2. Upload and sanitize a batch of customer reviews."""
        db = _get_db()
        rule_analyzer = B1RuleAnalyzer(enable_norm=True)
        job_id = db.log_job_start(
            job_type="reviews_upload",
            details={"scenario_tag": payload.scenario_tag, "count": len(payload.reviews)},
        )

        inserted = 0
        for item in payload.reviews:
            clean_raw = scrub_pii(item.text)
            norm_txt = normalize_social_text(clean_raw, enable=True)
            if item.opinions:
                ops = item.opinions
                ov_sent = item.overall_sentiment or ("negative" if item.rating <= 2 else "positive")
                info_flag = True
            else:
                res = rule_analyzer.analyze_review(clean_raw)
                ov_sent = item.overall_sentiment or res.overall_sentiment.value
                info_flag = res.informative
                ops = [
                    {
                        "aspect": op.aspect.value,
                        "polarity": op.polarity.value,
                        "evidence": op.evidence,
                        "evidence_ok": True,
                    }
                    for op in res.opinions
                ]

            db.upsert_review_and_opinions(
                review_id=item.review_id,
                platform=item.platform,
                shop=item.shop,
                product=item.product,
                rating=item.rating,
                text_raw=clean_raw,
                text_norm=norm_txt,
                source="api_upload",
                scenario_tag=payload.scenario_tag,
                overall_sentiment=ov_sent,
                informative=info_flag,
                opinions=ops,
                analyzer_method="api_ingest",
            )
            inserted += 1

        db.log_job_complete(job_id, status="completed", details={"inserted": inserted})
        return {
            "job_id": job_id,
            "scenario_tag": payload.scenario_tag,
            "inserted_count": inserted,
            "status": "completed",
        }

    @app.post("/api/v1/analyze/run", tags=["Analysis"])
    def run_analysis(payload: AnalyzeRunRequest) -> dict[str, Any]:
        """3. Run ABSA analysis and InsightEngine on a scenario."""
        db = _get_db()
        job_id = db.log_job_start(
            job_type="analyze_run",
            details={
                "scenario_tag": payload.scenario_tag,
                "analyzer_method": payload.analyzer_method,
            },
        )
        engine = InsightEngine(db=db)
        insights = engine.generate_insights(
            scenario_tag=payload.scenario_tag, min_n=payload.min_n, persist=True
        )
        db.log_job_complete(
            job_id,
            status="completed",
            details={"insights_generated": len(insights)},
        )
        return {
            "job_id": job_id,
            "scenario_tag": payload.scenario_tag,
            "insights_generated": len(insights),
            "status": "completed",
        }

    @app.get("/api/v1/jobs/{job_id}", tags=["System"])
    def get_job_status(job_id: int) -> dict[str, Any]:
        """4. Query audit status of a background or synchronous job."""
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            row = conn.execute("SELECT * FROM system_jobs_audit WHERE id = ?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return {
            "job_id": int(row["id"]),
            "job_type": str(row["job_type"]),
            "status": str(row["status"]),
            "details": json.loads(row["details"] or "{}"),
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        }

    @app.get("/api/v1/stats/overview", tags=["Analytics"])
    def get_overview_stats(
        scenario_tag: str = Query(default="real_shop"),
        min_n: int = Query(default=3),
    ) -> dict[str, Any]:
        """5. Return executive KPIs, Wilson 95% CI aspect stats, and platform breakdown."""
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            total_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_reviews,
                    AVG(rating) AS avg_rating,
                    SUM(CASE WHEN overall_sentiment = 'positive' THEN 1 ELSE 0 END) AS pos_reviews,
                    SUM(CASE WHEN overall_sentiment = 'negative' THEN 1 ELSE 0 END) AS neg_reviews,
                    SUM(CASE WHEN platform = 'shopee' THEN 1 ELSE 0 END) AS shopee_reviews,
                    SUM(CASE WHEN platform = 'tiktok' THEN 1 ELSE 0 END) AS tiktok_reviews
                FROM reviews
                WHERE scenario_tag = ?
                """,
                (scenario_tag,),
            ).fetchone()

        total_revs = int(total_row["total_reviews"] or 0)
        pos_revs = int(total_row["pos_reviews"] or 0)
        neg_revs = int(total_row["neg_reviews"] or 0)
        avg_rating = round(float(total_row["avg_rating"] or 0.0), 2)
        neg_rate = round((neg_revs / total_revs) * 100.0, 1) if total_revs else 0.0
        neg_ci_low, neg_ci_high = wilson_ci_pct(neg_revs, total_revs)

        aspect_stats = get_aspect_sentiment_stats(scenario_tag=scenario_tag, min_n=min_n, db=db)
        platform_gaps = get_platform_gap_stats(scenario_tag=scenario_tag, min_n=min_n, db=db)
        hidden_summary = get_hidden_complaints(scenario_tag=scenario_tag, db=db)

        return {
            "scenario_tag": scenario_tag,
            "total_reviews": total_revs,
            "avg_rating": avg_rating,
            "positive_reviews": pos_revs,
            "negative_reviews": neg_revs,
            "negative_rate_pct": neg_rate,
            "negative_ci_95": [neg_ci_low, neg_ci_high],
            "platform_counts": {
                "shopee": int(total_row["shopee_reviews"] or 0),
                "tiktok": int(total_row["tiktok_reviews"] or 0),
            },
            "aspect_stats": aspect_stats,
            "platform_gaps": platform_gaps,
            "hidden_complaints": hidden_summary,
        }

    @app.get("/api/v1/insights", tags=["Insights"])
    def list_insights(
        scenario_tag: str = Query(default="real_shop"),
        kind: str | None = Query(default=None),
    ) -> dict[str, Any]:
        """6. Retrieve numerically verified Insights for a scenario."""
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            if kind:
                rows = conn.execute(
                    "SELECT * FROM insights WHERE scenario_tag = ? AND kind = ? ORDER BY id ASC",
                    (scenario_tag, kind),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM insights WHERE scenario_tag = ? ORDER BY id ASC",
                    (scenario_tag,),
                ).fetchall()

        items = [
            {
                "insight_id": int(r["id"]),
                "scenario_tag": str(r["scenario_tag"]),
                "kind": str(r["kind"]),
                "aspect": r["aspect"],
                "statement": str(r["statement"]),
                "numbers": json.loads(r["numbers"] or "{}"),
                "evidence_ids": json.loads(r["evidence_ids"] or "[]"),
                "confidence": str(r["confidence"]),
            }
            for r in rows
        ]
        return {"scenario_tag": scenario_tag, "count": len(items), "insights": items}

    @app.post("/api/v1/actions/generate", tags=["Actions"])
    def generate_actions(payload: ActionGenerateRequest) -> dict[str, Any]:
        """7. Execute the P1 State-Graph (Planner <-> HybridCritic) to generate grounded actions."""
        db = _get_db()
        runner = EcomReviewGraphRunner(db=db, max_retries=2)
        trace = runner.run_scenario(
            scenario_tag=payload.scenario_tag,
            min_n=payload.min_n,
            max_actions=payload.max_actions,
            persist_db=True,
        )
        return trace

    @app.get("/api/v1/actions", tags=["Actions"])
    def list_actions(
        scenario_tag: str = Query(default="real_shop"),
        is_marketing: bool | None = Query(default=None),
        status: str | None = Query(default=None),
    ) -> dict[str, Any]:
        """8. Retrieve persisted ActionProposals and their HybridCritic traces."""
        db = _get_db()
        query = "SELECT * FROM actions WHERE scenario_tag = ?"
        params: list[Any] = [scenario_tag]
        if is_marketing is not None:
            query += " AND is_marketing = ?"
            params.append(1 if is_marketing else 0)
        if status:
            query += " AND UPPER(status) = ?"
            params.append(status.strip().upper())
        query += " ORDER BY priority_score DESC, id ASC"

        with db.get_connection(read_only=True) as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        actions = [
            {
                "id": int(r["id"]),
                "scenario_tag": str(r["scenario_tag"]),
                "action_type": str(r["action_type"]),
                "is_marketing": bool(r["is_marketing"]),
                "title": str(r["title"]),
                "what_to_do": str(r["what_to_do"]),
                "why_rationale": str(r["why_rationale"]),
                "how_and_when": str(r["how_and_when"]),
                "success_metric": str(r["success_metric"]),
                "effort": str(r["effort"]),
                "impact": str(r["impact"]),
                "priority_score": float(r["priority_score"]),
                "insight_ids": json.loads(r["insight_ids"] or "[]"),
                "evidence_review_ids": json.loads(r["evidence_review_ids"] or "[]"),
                "critic_passed": bool(r["critic_passed"]),
                "critic_trace": json.loads(r["critic_trace"] or "{}"),
                "status": str(r["status"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
        return {"scenario_tag": scenario_tag, "count": len(actions), "actions": actions}

    @app.post("/api/v1/actions/{action_id}/decision", tags=["Actions"])
    def submit_action_decision(action_id: int, payload: ActionDecisionRequest) -> dict[str, Any]:
        """9. Record Human Approval Gate decision (APPROVED, EDITED, REJECTED) + edit distance."""
        valid_decisions = {"APPROVED", "EDITED", "REJECTED"}
        if payload.decision.strip().upper() not in valid_decisions:
            raise HTTPException(
                status_code=400,
                detail=f"decision must be one of {sorted(valid_decisions)}",
            )
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            exists = conn.execute("SELECT id FROM actions WHERE id = ?", (action_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Action {action_id} not found")

        result = db.record_action_decision(
            action_id=action_id,
            decision=payload.decision,
            note=payload.note,
            edited_content=payload.edited_content,
            reason_category=payload.reason_category,
        )
        return result

    @app.get("/api/v1/reviews", tags=["Reviews"])
    def query_reviews(
        scenario_tag: str = Query(default="real_shop"),
        platform: str | None = Query(default=None),
        aspect: str | None = Query(default=None),
        polarity: str | None = Query(default=None),
        review_ids: str | None = Query(
            default=None, description="Comma-separated review IDs for evidence drill-down"
        ),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        """10. Query customer reviews and their extracted ABSA opinions."""
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            if review_ids:
                id_list = [i.strip() for i in review_ids.split(",") if i.strip()]
                placeholders = ",".join("?" for _ in id_list)
                rows = conn.execute(
                    f"SELECT * FROM reviews WHERE scenario_tag = ? "
                    f"AND review_id IN ({placeholders})",
                    (scenario_tag, *id_list),
                ).fetchall()
            elif aspect:
                q = """
                    SELECT DISTINCT r.*
                    FROM reviews r
                    JOIN opinions o ON r.review_id = o.review_id AND r.scenario_tag = o.scenario_tag
                    WHERE r.scenario_tag = ? AND o.aspect = ?
                """
                p: list[Any] = [scenario_tag, aspect]
                if polarity:
                    q += " AND o.polarity = ?"
                    p.append(polarity)
                if platform:
                    q += " AND r.platform = ?"
                    p.append(platform)
                q += " ORDER BY r.review_id ASC LIMIT ?"
                p.append(limit)
                rows = conn.execute(q, tuple(p)).fetchall()
            else:
                q = "SELECT * FROM reviews WHERE scenario_tag = ?"
                p = [scenario_tag]
                if platform:
                    q += " AND platform = ?"
                    p.append(platform)
                if polarity:
                    q += " AND overall_sentiment = ?"
                    p.append(polarity)
                q += " ORDER BY review_id ASC LIMIT ?"
                p.append(limit)
                rows = conn.execute(q, tuple(p)).fetchall()

            reviews_out = []
            for r in rows:
                rid = str(r["review_id"])
                ops = conn.execute(
                    "SELECT aspect, polarity, evidence, evidence_ok FROM opinions "
                    "WHERE review_id = ? AND scenario_tag = ?",
                    (rid, scenario_tag),
                ).fetchall()
                reviews_out.append(
                    {
                        "review_id": rid,
                        "platform": str(r["platform"]),
                        "rating": int(r["rating"] or 5),
                        "text_raw": str(r["text_raw"]),
                        "overall_sentiment": str(r["overall_sentiment"] or "neutral"),
                        "opinions": [
                            {
                                "aspect": str(o["aspect"]),
                                "polarity": str(o["polarity"]),
                                "evidence": str(o["evidence"]),
                                "evidence_ok": bool(o["evidence_ok"]),
                            }
                            for o in ops
                        ],
                    }
                )

        return {"scenario_tag": scenario_tag, "count": len(reviews_out), "reviews": reviews_out}

    return app


app = create_app()

# CreBy: MenBoyBMN
