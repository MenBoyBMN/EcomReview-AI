"""FastAPI Backend Service exposing 15 RESTful Endpoints for EcomReview AI.

Endpoints:
1.  GET  /api/v1/health
2.  POST /api/v1/reviews/upload
3.  POST /api/v1/analyze/run
4.  GET  /api/v1/jobs/{job_id}
5.  GET  /api/v1/stats/overview
6.  GET  /api/v1/insights
7.  POST /api/v1/actions/generate
8.  GET  /api/v1/actions
9.  POST /api/v1/actions/{action_id}/decision
10. GET  /api/v1/reviews
11. GET  /api/v1/trends
12. GET  /api/v1/alerts
13. POST /api/v1/reviews/{review_id}/reply-draft
14. GET  /api/v1/actions/{action_id}/impact
15. GET  /api/v1/reports/export
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import AliasChoices, BaseModel, Field

from ecomreview.agent.graph_runner import EcomReviewGraphRunner
from ecomreview.agent.insight_engine import InsightEngine
from ecomreview.agent.reply_assistant import generate_customer_reply
from ecomreview.agent.tools_aggregator import (
    detect_trend_alerts,
    get_action_impact,
    get_aspect_sentiment_stats,
    get_aspect_trend,
    get_hidden_complaints,
    get_platform_comparison,
    get_platform_gap_stats,
    wilson_ci_pct,
)
from ecomreview.analyze.factory import get_analyzer
from ecomreview.api.security_deps import get_current_reviewer, require_api_key
from ecomreview.db.database import DatabaseManager
from ecomreview.ingest_service import ingest_review_batch
from ecomreview.reporting import build_excel_report, build_html_report

logger = logging.getLogger(__name__)


class ReviewUploadItem(BaseModel):
    """Single review record for batch ingestion."""

    review_id: str
    platform: str = "tiktok"
    shop: str = "shop_a"
    product: str = "ao_mua_da_ca"
    rating: int = Field(default=5, ge=1, le=5)
    text: str = Field(validation_alias=AliasChoices("text", "text_raw"))
    overall_sentiment: str | None = None
    created_at: str | None = None
    opinions: list[dict[str, Any]] = Field(default_factory=list)


class ReviewUploadRequest(BaseModel):
    """Batch review upload request payload."""

    scenario_tag: str = "real_shop"
    analyzer_method: str = "a1_gemini_v2"
    reviews: list[ReviewUploadItem]


class AnalyzeRunRequest(BaseModel):
    """Request payload to trigger ABSA + InsightEngine on a scenario."""

    scenario_tag: str = "real_shop"
    analyzer_method: str = "a1_gemini_v2"
    min_n: int = 5
    async_mode: bool = False


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


def _execute_analysis_task(
    job_id: int,
    scenario_tag: str,
    analyzer_method: str,
    min_n: int,
    db: DatabaseManager,
) -> None:
    """Internal task runner for synchronous or background analysis jobs."""
    try:
        with db.get_connection(read_only=True) as conn:
            unparsed = conn.execute(
                """
                SELECT r.* FROM reviews r
                LEFT JOIN opinions o
                  ON r.review_id = o.review_id AND r.scenario_tag = o.scenario_tag
                WHERE r.scenario_tag = ?
                GROUP BY r.review_id, r.scenario_tag
                HAVING COUNT(o.id) = 0
                """,
                (scenario_tag,),
            ).fetchall()

        if unparsed:
            analyzer = get_analyzer(analyzer_method)
            for r in unparsed:
                clean_raw = str(r["text_raw"])
                res = analyzer.analyze_review(clean_raw)
                ops = [
                    {
                        "aspect": op.aspect.value
                        if hasattr(op.aspect, "value")
                        else str(op.aspect),
                        "polarity": op.polarity.value
                        if hasattr(op.polarity, "value")
                        else str(op.polarity),
                        "evidence": op.evidence,
                        "evidence_ok": getattr(op, "evidence_ok", True),
                    }
                    for op in res.opinions
                ]
                db.upsert_review_and_opinions(
                    review_id=str(r["review_id"]),
                    platform=str(r["platform"]),
                    shop=str(r["shop"]),
                    product=str(r["product"]),
                    rating=int(r["rating"] or 5),
                    text_raw=clean_raw,
                    text_norm=str(r["text_norm"]),
                    source=str(r["source"] or "api_upload"),
                    scenario_tag=scenario_tag,
                    overall_sentiment=str(r["overall_sentiment"] or res.overall_sentiment),
                    informative=bool(res.informative),
                    opinions=ops,
                    analyzer_method=analyzer_method,
                    created_at=str(r["created_at"]) if r["created_at"] else None,
                )

        engine = InsightEngine(db=db)
        insights = engine.generate_insights(scenario_tag=scenario_tag, min_n=min_n, persist=True)
        db.log_job_complete(
            job_id,
            status="completed",
            details={
                "scenario_tag": scenario_tag,
                "analyzer_method": analyzer_method,
                "unparsed_count": len(unparsed),
                "insights_generated": len(insights),
            },
        )
    except Exception as e:
        logger.exception("Analysis job %d failed: %s", job_id, e)
        db.log_job_complete(
            job_id,
            status="failed",
            details={"scenario_tag": scenario_tag, "error": str(e)},
        )


def create_app(db_path: str | None = None) -> FastAPI:
    """Factory creating the FastAPI application with configurable database path."""
    app = FastAPI(
        title="EcomReview AI API",
        description=(
            "Vietnamese Aspect-Based Sentiment Analysis & Evidence-Grounded "
            "Marketing Action Planning API for Raincoat E-Commerce SMEs."
        ),
        version="1.1.0",
    )

    cors_origins = [
        o.strip() for o in os.getenv("ECOMREVIEW_CORS_ORIGINS", "*").split(",") if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=False if cors_origins == ["*"] else True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _get_db() -> DatabaseManager:
        return DatabaseManager(db_path=db_path or os.getenv("ECOMREVIEW_SQLITE_PATH"))

    # 1. System Health
    @app.get("/api/v1/health", tags=["System"])
    def health_check() -> dict[str, Any]:
        """1. Check API, database connection, and security configuration status."""
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            rev_count = conn.execute("SELECT COUNT(*) AS cnt FROM reviews").fetchone()["cnt"]
        demo_mode = os.getenv("DEMO_CACHE_MODE", "true").lower() == "true"
        auth_enabled = bool(os.getenv("ECOMREVIEW_API_KEY", "").strip())
        return {
            "status": "healthy",
            "database_backend": db.backend,
            "database_status": "connected",
            "total_reviews_in_db": int(rev_count),
            "demo_cache_mode": demo_mode,
            "auth_enabled": auth_enabled,
            "endpoints_count": 15,
        }

    # 2. Ingestion
    @app.post(
        "/api/v1/reviews/upload",
        tags=["Ingestion"],
        dependencies=[Depends(require_api_key)],
    )
    def upload_reviews(payload: ReviewUploadRequest) -> dict[str, Any]:
        """2. Upload, sanitize, analyze and persist a batch of customer reviews."""
        db = _get_db()
        job_id = db.log_job_start(
            job_type="reviews_upload",
            details={
                "scenario_tag": payload.scenario_tag,
                "count": len(payload.reviews),
                "analyzer_method": payload.analyzer_method,
            },
        )

        review_dicts = [item.model_dump() for item in payload.reviews]
        ingest_res = ingest_review_batch(
            db=db,
            reviews=review_dicts,
            scenario_tag=payload.scenario_tag,
            analyzer_method=payload.analyzer_method,
        )

        db.log_job_complete(job_id, status="completed", details=ingest_res)
        return {
            "job_id": job_id,
            "scenario_tag": payload.scenario_tag,
            "inserted_count": ingest_res["inserted_count"],
            "analyzer_method": ingest_res["analyzer_method"],
            "status": "completed",
        }

    # 3. ABSA & Insight Analysis
    @app.post(
        "/api/v1/analyze/run",
        tags=["Analysis"],
        dependencies=[Depends(require_api_key)],
    )
    def run_analysis(
        payload: AnalyzeRunRequest,
        background_tasks: BackgroundTasks,
    ) -> Any:
        """3. Run ABSA analysis and InsightEngine on a scenario (sync or async)."""
        db = _get_db()
        job_id = db.log_job_start(
            job_type="analyze_run",
            details={
                "scenario_tag": payload.scenario_tag,
                "analyzer_method": payload.analyzer_method,
                "min_n": payload.min_n,
                "async_mode": payload.async_mode,
            },
        )

        if payload.async_mode:
            background_tasks.add_task(
                _execute_analysis_task,
                job_id=job_id,
                scenario_tag=payload.scenario_tag,
                analyzer_method=payload.analyzer_method,
                min_n=payload.min_n,
                db=db,
            )
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "job_id": job_id,
                    "scenario_tag": payload.scenario_tag,
                    "status": "running",
                    "message": (
                        "Analysis started in background. Poll /api/v1/jobs/{job_id} for progress."
                    ),
                },
            )

        _execute_analysis_task(
            job_id=job_id,
            scenario_tag=payload.scenario_tag,
            analyzer_method=payload.analyzer_method,
            min_n=payload.min_n,
            db=db,
        )

        with db.get_connection(read_only=True) as conn:
            job_row = conn.execute(
                "SELECT * FROM system_jobs_audit WHERE id = ?", (job_id,)
            ).fetchone()
        job_details = json.loads(job_row["details"] or "{}") if job_row else {}

        return {
            "job_id": job_id,
            "scenario_tag": payload.scenario_tag,
            "insights_generated": job_details.get("insights_generated", 0),
            "status": "completed",
        }

    # 4. Jobs Audit
    @app.get(
        "/api/v1/jobs/{job_id}",
        tags=["System"],
        dependencies=[Depends(require_api_key)],
    )
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

    # 5. Executive Overview Analytics
    @app.get(
        "/api/v1/stats/overview",
        tags=["Analytics"],
        dependencies=[Depends(require_api_key)],
    )
    def get_overview_stats(
        scenario_tag: str = Query(default="real_shop"),
        min_n: int = Query(default=3),
    ) -> dict[str, Any]:
        """5. Return executive KPIs, Wilson 95% CI aspect stats, and platform comparison."""
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
        platform_comparison = get_platform_comparison(scenario_tag=scenario_tag, min_n=min_n, db=db)
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
            "platform_comparison": platform_comparison,
            "hidden_complaints": hidden_summary,
        }

    # 6. Insights Listing
    @app.get(
        "/api/v1/insights",
        tags=["Insights"],
        dependencies=[Depends(require_api_key)],
    )
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
                "numbers": json.loads(r["numbers"] or "{}")
                if isinstance(r["numbers"], str)
                else r["numbers"],
                "evidence_ids": json.loads(r["evidence_ids"] or "[]")
                if isinstance(r["evidence_ids"], str)
                else r["evidence_ids"],
                "confidence": str(r["confidence"]),
            }
            for r in rows
        ]
        return {"scenario_tag": scenario_tag, "count": len(items), "insights": items}

    # 7. Action Planning
    @app.post(
        "/api/v1/actions/generate",
        tags=["Actions"],
        dependencies=[Depends(require_api_key)],
    )
    def generate_actions(payload: ActionGenerateRequest) -> dict[str, Any]:
        """7. Execute the P1 State-Graph (Planner <-> HybridCritic) to generate grounded actions."""
        db = _get_db()
        trace_dir = os.getenv("ECOMREVIEW_TRACE_DIR", "results/traces")
        runner = EcomReviewGraphRunner(db=db, max_retries=2, trace_dir=trace_dir)
        trace = runner.run_scenario(
            scenario_tag=payload.scenario_tag,
            min_n=payload.min_n,
            max_actions=payload.max_actions,
            persist_db=True,
        )
        return trace

    # 8. Action Listing
    @app.get(
        "/api/v1/actions",
        tags=["Actions"],
        dependencies=[Depends(require_api_key)],
    )
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
                "insight_ids": json.loads(r["insight_ids"] or "[]")
                if isinstance(r["insight_ids"], str)
                else r["insight_ids"],
                "evidence_review_ids": json.loads(r["evidence_review_ids"] or "[]")
                if isinstance(r["evidence_review_ids"], str)
                else r["evidence_review_ids"],
                "critic_passed": bool(r["critic_passed"]),
                "critic_trace": json.loads(r["critic_trace"] or "{}")
                if isinstance(r["critic_trace"], str)
                else r["critic_trace"],
                "status": str(r["status"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
        return {"scenario_tag": scenario_tag, "count": len(actions), "actions": actions}

    # 9. Human Approval Gate
    @app.post(
        "/api/v1/actions/{action_id}/decision",
        tags=["Actions"],
        dependencies=[Depends(require_api_key)],
    )
    def submit_action_decision(
        action_id: int,
        payload: ActionDecisionRequest,
        reviewer: str = Depends(get_current_reviewer),
    ) -> dict[str, Any]:
        """9. Record Human Approval Gate decision with edit distance and reviewer identity."""
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
            decided_by=reviewer,
        )
        return result

    # 10. Reviews Exploration (with batch opinions query - N+1 fix)
    @app.get(
        "/api/v1/reviews",
        tags=["Reviews"],
        dependencies=[Depends(require_api_key)],
    )
    def query_reviews(
        scenario_tag: str = Query(default="real_shop"),
        platform: str | None = Query(default=None),
        aspect: str | None = Query(default=None),
        polarity: str | None = Query(default=None),
        review_ids: str | None = Query(
            default=None, description="Comma-separated review IDs for evidence drill-down"
        ),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> dict[str, Any]:
        """10. Query customer reviews and their extracted ABSA opinions with pagination."""
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            if review_ids:
                id_list = [i.strip() for i in review_ids.split(",") if i.strip()]
                if id_list:
                    placeholders = ",".join("?" for _ in id_list)
                    rows = conn.execute(
                        f"SELECT * FROM reviews WHERE scenario_tag = ? "
                        f"AND review_id IN ({placeholders})",
                        (scenario_tag, *id_list),
                    ).fetchall()
                else:
                    rows = []
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
                q += " ORDER BY r.review_id ASC LIMIT ? OFFSET ?"
                p.extend([limit, offset])
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
                q += " ORDER BY review_id ASC LIMIT ? OFFSET ?"
                p.extend([limit, offset])
                rows = conn.execute(q, tuple(p)).fetchall()

            # Batch fetch opinions to eliminate N+1 queries
            matched_rids = [str(r["review_id"]) for r in rows]
            opinions_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
            if matched_rids:
                ph = ",".join("?" for _ in matched_rids)
                op_rows = conn.execute(
                    f"SELECT review_id, aspect, polarity, evidence, evidence_ok FROM opinions "
                    f"WHERE scenario_tag = ? AND review_id IN ({ph})",
                    (scenario_tag, *matched_rids),
                ).fetchall()
                for op in op_rows:
                    opinions_map[str(op["review_id"])].append(
                        {
                            "aspect": str(op["aspect"]),
                            "polarity": str(op["polarity"]),
                            "evidence": str(op["evidence"]),
                            "evidence_ok": bool(op["evidence_ok"]),
                        }
                    )

            reviews_out = []
            for r in rows:
                rid = str(r["review_id"])
                reviews_out.append(
                    {
                        "review_id": rid,
                        "platform": str(r["platform"]),
                        "rating": int(r["rating"] or 5),
                        "text_raw": str(r["text_raw"]),
                        "created_at": str(r["created_at"]) if r["created_at"] else None,
                        "overall_sentiment": str(r["overall_sentiment"] or "neutral"),
                        "opinions": opinions_map.get(rid, []),
                    }
                )

        return {"scenario_tag": scenario_tag, "count": len(reviews_out), "reviews": reviews_out}

    # 11. Trend Analysis
    @app.get(
        "/api/v1/trends",
        tags=["Analytics"],
        dependencies=[Depends(require_api_key)],
    )
    def get_trends(
        scenario_tag: str = Query(default="real_shop"),
        aspect: str | None = Query(default=None),
        period: str = Query(default="month", description="'month' or 'week'"),
        min_n: int = Query(default=3),
    ) -> dict[str, Any]:
        """11. Query historical sentiment trends grouped by week or month with Wilson 95% CI."""
        db = _get_db()
        trend = get_aspect_trend(
            scenario_tag=scenario_tag,
            aspect=aspect,
            period=period,
            min_n=min_n,
            db=db,
        )
        return {
            "scenario_tag": scenario_tag,
            "aspect": aspect or "ALL",
            "period_type": period,
            "buckets_count": len(trend),
            "trends": trend,
        }

    # 12. Early Warning Alerts
    @app.get(
        "/api/v1/alerts",
        tags=["Analytics"],
        dependencies=[Depends(require_api_key)],
    )
    def get_alerts(
        scenario_tag: str = Query(default="real_shop"),
        period: str = Query(default="month"),
        baseline_periods: int = Query(default=3),
        min_n: int = Query(default=5),
        min_delta_pp: float = Query(default=10.0),
    ) -> dict[str, Any]:
        """12. Detect statistical spike alerts based on two-proportion one-sided z-test."""
        db = _get_db()
        alerts = detect_trend_alerts(
            scenario_tag=scenario_tag,
            period=period,
            baseline_periods=baseline_periods,
            min_n=min_n,
            min_delta_pp=min_delta_pp,
            db=db,
        )
        return {
            "scenario_tag": scenario_tag,
            "alerts_count": len(alerts),
            "alerts": alerts,
        }

    # 13. Customer Reply Assistant
    @app.post(
        "/api/v1/reviews/{review_id}/reply-draft",
        tags=["Customer Care"],
        dependencies=[Depends(require_api_key)],
    )
    def create_reply_draft(
        review_id: str,
        scenario_tag: str = Query(default="real_shop"),
        mode: str = Query(default="template", description="'template' or 'llm'"),
    ) -> dict[str, Any]:
        """13. Generate and verify a policy-compliant customer service reply draft."""
        db = _get_db()
        res = generate_customer_reply(
            review_id=review_id,
            scenario_tag=scenario_tag,
            mode=mode,
            db=db,
        )
        if res.get("status") == "error":
            raise HTTPException(status_code=404, detail=res.get("message"))
        return res

    # 14. Action Intervention Impact
    @app.get(
        "/api/v1/actions/{action_id}/impact",
        tags=["Actions"],
        dependencies=[Depends(require_api_key)],
    )
    def measure_action_impact(
        action_id: int,
        window_days: int = Query(default=30),
        since: str | None = Query(default=None),
        min_n: int = Query(default=3),
    ) -> dict[str, Any]:
        """14. Measure pre vs post intervention sentiment for aspects targeted by action."""
        db = _get_db()
        impact = get_action_impact(
            action_id=action_id,
            window_days=window_days,
            since=since,
            min_n=min_n,
            db=db,
        )
        if impact.get("status") == "action_not_found":
            raise HTTPException(status_code=404, detail=f"Action {action_id} not found.")
        return impact

    # 15. Report Export (Excel / HTML)
    @app.get(
        "/api/v1/reports/export",
        tags=["Reports"],
        dependencies=[Depends(require_api_key)],
    )
    def export_report(
        scenario_tag: str = Query(default="real_shop"),
        format: str = Query(default="xlsx", description="'xlsx' or 'html'"),
    ) -> Response:
        """15. Export executive multi-tab Excel workbook (.xlsx) or printable HTML report."""
        db = _get_db()
        fmt = format.strip().lower()
        if fmt in ("xlsx", "excel"):
            xlsx_bytes = build_excel_report(scenario_tag=scenario_tag, db=db)
            filename = f"EcomReview_Report_{scenario_tag}.xlsx"
            return Response(
                content=xlsx_bytes,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        if fmt in ("html", "htm"):
            html_text = build_html_report(scenario_tag=scenario_tag, db=db)
            return Response(
                content=html_text,
                media_type="text/html; charset=utf-8",
            )
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{format}'. Choose from 'xlsx' or 'html'.",
        )

    return app


app = create_app()

# CreBy: MenBoyBMN
