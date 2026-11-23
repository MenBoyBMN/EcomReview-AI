"""Durable background job execution via Redis + RQ with local fallback."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from fastapi import BackgroundTasks

from ecomreview.agent.insight_engine import InsightEngine
from ecomreview.agent.tools_aggregator import detect_trend_alerts
from ecomreview.alerts.notifier import notify_critical_reviews, notify_trend_alerts
from ecomreview.analyze.factory import get_analyzer
from ecomreview.db.database import DatabaseManager
from ecomreview.ingest_service import ingest_review_batch

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_NAME = "ecomreview_default"


def _get_rq_queue():
    """Return an RQ Queue connected to REDIS_URL if configured and reachable."""
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url or os.getenv("ECOMREVIEW_QUEUE_DISABLE", "false").lower() == "true":
        return None
    try:
        import redis
        from rq import Queue

        conn = redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        conn.ping()
        return Queue(DEFAULT_QUEUE_NAME, connection=conn, default_timeout=900)
    except Exception as exc:
        logger.warning("Redis/RQ unavailable (%s); falling back to FastAPI BackgroundTasks.", exc)
        return None


def task_ingest_review_batch(
    job_id: int,
    scenario_tag: str,
    reviews: list[dict[str, Any]],
    analyzer_method: str,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Worker task: ingest, sanitize, analyze a review batch and dispatch critical alerts."""
    db = DatabaseManager(db_path=db_path or os.getenv("ECOMREVIEW_SQLITE_PATH"))
    total = len(reviews)

    def _on_progress(processed: int, total_items: int) -> None:
        if processed == total_items or processed % 10 == 0:
            db.update_job_progress(
                job_id,
                {
                    "scenario_tag": scenario_tag,
                    "analyzer_method": analyzer_method,
                    "processed_count": processed,
                    "total_count": total_items,
                },
            )

    try:
        ingest_res = ingest_review_batch(
            db=db,
            reviews=reviews,
            scenario_tag=scenario_tag,
            analyzer_method=analyzer_method,
            progress_callback=_on_progress,
        )
        dispatches = notify_critical_reviews(db=db, scenario_tag=scenario_tag, reviews=reviews)
        details = {
            **ingest_res,
            "processed_count": ingest_res["inserted_count"],
            "total_count": total,
            "alerts_dispatched": len([d for d in dispatches if d.get("status") == "SENT"]),
        }
        db.log_job_complete(job_id, status="completed", details=details)
        return details
    except Exception as exc:
        logger.exception("Ingest job %d failed: %s", job_id, exc)
        db.log_job_complete(
            job_id,
            status="failed",
            details={"scenario_tag": scenario_tag, "error": str(exc)},
        )
        raise


def task_run_analysis(
    job_id: int,
    scenario_tag: str,
    analyzer_method: str,
    min_n: int,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Worker task: run ABSA on unparsed reviews, generate insights, and push Z-test alerts."""
    db = DatabaseManager(db_path=db_path or os.getenv("ECOMREVIEW_SQLITE_PATH"))
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

        used_fallback = False
        if unparsed:
            analyzer = get_analyzer(analyzer_method)
            total_unparsed = len(unparsed)
            for idx, r in enumerate(unparsed, start=1):
                clean_raw = str(r["text_raw"])
                res = analyzer.analyze_review(clean_raw)
                if getattr(analyzer, "last_used_fallback", False):
                    used_fallback = True
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
                item_method = f"{analyzer_method}+b1_fallback" if used_fallback else analyzer_method
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
                    overall_sentiment=str(
                        r["overall_sentiment"]
                        or (
                            res.overall_sentiment.value
                            if hasattr(res.overall_sentiment, "value")
                            else str(res.overall_sentiment)
                        )
                    ).lower(),
                    informative=bool(res.informative),
                    opinions=ops,
                    analyzer_method=item_method,
                    created_at=str(r["created_at"]) if r["created_at"] else None,
                )
                if idx == total_unparsed or idx % 10 == 0:
                    db.update_job_progress(
                        job_id,
                        {
                            "scenario_tag": scenario_tag,
                            "processed_count": idx,
                            "total_count": total_unparsed,
                        },
                    )

        effective_method = f"{analyzer_method}+b1_fallback" if used_fallback else analyzer_method
        engine = InsightEngine(db=db)
        insights = engine.generate_insights(scenario_tag=scenario_tag, min_n=min_n, persist=True)
        alerts = detect_trend_alerts(scenario_tag=scenario_tag, min_n=min_n, db=db)
        dispatches = notify_trend_alerts(db=db, scenario_tag=scenario_tag, alerts=alerts)

        details = {
            "scenario_tag": scenario_tag,
            "analyzer_method": effective_method,
            "unparsed_count": len(unparsed),
            "insights_generated": len(insights),
            "alerts_detected": len(alerts),
            "alerts_dispatched": len([d for d in dispatches if d.get("status") == "SENT"]),
        }
        db.log_job_complete(job_id, status="completed", details=details)
        return details
    except Exception as exc:
        logger.exception("Analysis job %d failed: %s", job_id, exc)
        db.log_job_complete(
            job_id,
            status="failed",
            details={"scenario_tag": scenario_tag, "error": str(exc)},
        )
        raise


def enqueue_background_job(
    func: Callable[..., Any],
    background_tasks: BackgroundTasks | None,
    **kwargs: Any,
) -> str:
    """Enqueue a task to Redis/RQ when available, else fallback to FastAPI BackgroundTasks."""
    q = _get_rq_queue()
    if q is not None:
        from rq import Retry

        rq_job = q.enqueue(func, kwargs=kwargs, retry=Retry(max=3, interval=[10, 30, 60]))
        return f"rq:{rq_job.id}"

    if background_tasks is not None:
        background_tasks.add_task(func, **kwargs)
        return "background_tasks"

    func(**kwargs)
    return "inline"


# CreBy: MenBoyBMN
