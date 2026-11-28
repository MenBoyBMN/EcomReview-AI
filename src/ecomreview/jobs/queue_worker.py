"""Durable background job execution via Redis + RQ with local fallback."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import BackgroundTasks

from ecomreview.agent.insight_engine import InsightEngine
from ecomreview.agent.reply_assistant import auto_reply_eligible_five_star_reviews
from ecomreview.agent.tools_aggregator import detect_trend_alerts
from ecomreview.alerts.notifier import notify_critical_reviews, notify_trend_alerts
from ecomreview.analyze.factory import get_analyzer
from ecomreview.connectors.factory import ensure_fresh_connector
from ecomreview.db.database import DatabaseManager
from ecomreview.ingest_service import ingest_review_batch

logger = logging.getLogger(__name__)

QUEUE_CRITICAL = "ecomreview_critical"
QUEUE_DEFAULT = "ecomreview_default"
QUEUE_LOW = "ecomreview_low"
PRIORITY_QUEUES: tuple[str, ...] = (QUEUE_CRITICAL, QUEUE_DEFAULT, QUEUE_LOW)
DEFAULT_QUEUE_NAME = QUEUE_DEFAULT
DLQ_REDIS_KEY = "ecomreview:dlq"


def resolve_queue_name(priority: str = "default") -> str:
    """Map logical priority ('critical'|'high'|'default'|'low') to an RQ queue name."""
    norm = (priority or "default").strip().lower()
    if norm in {"critical", "high"}:
        return QUEUE_CRITICAL
    if norm == "low":
        return QUEUE_LOW
    return QUEUE_DEFAULT


def _get_redis_client():
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url or os.getenv("ECOMREVIEW_QUEUE_DISABLE", "false").lower() == "true":
        return None
    try:
        import redis

        conn = redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        conn.ping()
        return conn
    except Exception as exc:
        logger.warning("Redis/RQ unavailable (%s); falling back to FastAPI BackgroundTasks.", exc)
        return None


def _get_rq_queue(queue_name: str = DEFAULT_QUEUE_NAME):
    """Return an RQ Queue connected to REDIS_URL if configured and reachable."""
    conn = _get_redis_client()
    if conn is None:
        return None
    try:
        from rq import Queue

        return Queue(queue_name, connection=conn, default_timeout=900)
    except Exception as exc:
        logger.warning("RQ Queue init failed (%s); falling back to FastAPI BackgroundTasks.", exc)
        return None


def record_dlq_failure(
    job: Any,
    connection: Any,
    exc_type: Any,
    exc_value: Any,
    traceback_obj: Any,
) -> None:
    """RQ failure callback persisting terminal job failures to Redis Dead-Letter Queue."""
    try:
        kwargs = getattr(job, "kwargs", {}) or {}
        entry = {
            "rq_job_id": str(getattr(job, "id", "")),
            "func": str(getattr(job, "func_name", "")),
            "queue": str(getattr(job, "origin", DEFAULT_QUEUE_NAME)),
            "scenario_tag": kwargs.get("scenario_tag"),
            "job_id": kwargs.get("job_id"),
            "error_type": getattr(exc_type, "__name__", str(exc_type)),
            "error": str(exc_value)[:500],
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        if connection is not None:
            connection.lpush(DLQ_REDIS_KEY, json.dumps(entry, ensure_ascii=False))
            connection.ltrim(DLQ_REDIS_KEY, 0, 499)
    except Exception as exc:
        logger.debug("DLQ callback failed: %s", exc)


def list_dlq_entries(db: DatabaseManager, limit: int = 50) -> list[dict[str, Any]]:
    """Return recent failed jobs from Redis DLQ combined with failed system_jobs_audit rows."""
    safe_limit = max(1, min(200, limit))
    entries: list[dict[str, Any]] = []
    seen_job_ids: set[int] = set()

    conn = _get_redis_client()
    if conn is not None:
        try:
            raw_items = conn.lrange(DLQ_REDIS_KEY, 0, safe_limit - 1)
            for raw in raw_items:
                txt = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
                parsed = json.loads(txt)
                parsed["source"] = "redis_dlq"
                entries.append(parsed)
                if parsed.get("job_id") is not None:
                    seen_job_ids.add(int(parsed["job_id"]))
        except Exception as exc:
            logger.debug("Failed reading Redis DLQ: %s", exc)

    with db.get_connection(read_only=True) as db_conn:
        rows = db_conn.execute(
            """
            SELECT id, job_type, scenario_tag, status, details, created_at, completed_at
            FROM system_jobs_audit
            WHERE LOWER(status) = 'failed'
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    for r in rows:
        jid = int(r["id"])
        if jid in seen_job_ids:
            continue
        raw_d = r["details"]
        details = json.loads(raw_d or "{}") if isinstance(raw_d, str) else (raw_d or {})
        entries.append(
            {
                "source": "jobs_audit",
                "job_id": jid,
                "job_type": str(r["job_type"]),
                "scenario_tag": r["scenario_tag"],
                "error": details.get("error", ""),
                "failed_at": str(r["completed_at"] or r["created_at"] or ""),
            }
        )
    return entries[:safe_limit]


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
            raw_workers = os.getenv("ECOMREVIEW_ANALYSIS_WORKERS", "").strip()
            cfg_workers = int(raw_workers) if raw_workers.isdigit() else 6
            eff_workers = max(1, min(16, cfg_workers, total_unparsed))

            def _analyze_unparsed(row: Any) -> dict[str, Any]:
                clean_raw = str(row["text_raw"])
                res = analyzer.analyze_review(clean_raw)
                fb = bool(getattr(analyzer, "last_used_fallback", False))
                item_method = f"{analyzer_method}+b1_fallback" if fb else analyzer_method
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
                ov = str(
                    row["overall_sentiment"]
                    or (
                        res.overall_sentiment.value
                        if hasattr(res.overall_sentiment, "value")
                        else str(res.overall_sentiment)
                    )
                ).lower()
                return {
                    "record": {
                        "review_id": str(row["review_id"]),
                        "scenario_tag": scenario_tag,
                        "platform": str(row["platform"]),
                        "shop": str(row["shop"]),
                        "product": str(row["product"]),
                        "rating": int(row["rating"] or 5),
                        "text_raw": clean_raw,
                        "text_norm": str(row["text_norm"]),
                        "source": str(row["source"] or "api_upload"),
                        "overall_sentiment": ov,
                        "informative": bool(res.informative),
                        "opinions": ops,
                        "analyzer_method": item_method,
                        "created_at": str(row["created_at"]) if row["created_at"] else None,
                    },
                    "used_fallback": fb,
                }

            if eff_workers > 1 and total_unparsed > 1:
                with ThreadPoolExecutor(max_workers=eff_workers) as pool:
                    analyzed_items = list(pool.map(_analyze_unparsed, unparsed))
            else:
                analyzed_items = [_analyze_unparsed(r) for r in unparsed]

            used_fallback = any(item["used_fallback"] for item in analyzed_items)
            records = [item["record"] for item in analyzed_items]
            raw_bs = os.getenv("ECOMREVIEW_DB_BATCH_SIZE", "").strip()
            batch_size = max(10, min(500, int(raw_bs))) if raw_bs.isdigit() else 100
            processed = 0
            for start in range(0, len(records), batch_size):
                chunk = records[start : start + batch_size]
                processed += db.bulk_upsert_reviews_and_opinions(chunk, chunk_size=batch_size)
                db.update_job_progress(
                    job_id,
                    {
                        "scenario_tag": scenario_tag,
                        "processed_count": processed,
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
    *,
    priority: str = "default",
    max_retries: int = 3,
    **kwargs: Any,
) -> str:
    """Enqueue a task to a priority Redis/RQ queue when available, else local fallback."""
    queue_name = resolve_queue_name(priority)
    q = _get_rq_queue(queue_name=queue_name)
    if q is not None:
        from rq import Callback, Retry

        rq_job = q.enqueue(
            func,
            kwargs=kwargs,
            retry=Retry(max=max_retries, interval=[10, 30, 60]),
            on_failure=Callback(record_dlq_failure),
        )
        return f"rq:{queue_name}:{rq_job.id}"

    if background_tasks is not None:
        background_tasks.add_task(func, **kwargs)
        return "background_tasks"

    func(**kwargs)
    return "inline"


def _parse_iso_dt(raw: str | None) -> datetime | None:
    if not raw or not str(raw).strip():
        return None
    try:
        dt = datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def task_sync_marketplace_reviews(
    job_id: int,
    scenario_tag: str,
    platform: str,
    analyzer_method: str = "a1_gemini_v2",
    limit: int = 100,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Worker task: pull new reviews from connected Shopee/TikTok shop, analyze & alert."""
    db = DatabaseManager(db_path=db_path or os.getenv("ECOMREVIEW_SQLITE_PATH"))
    clean_plat = platform.strip().lower()
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        conn = db.get_marketplace_connection(scenario_tag, clean_plat, include_tokens=True)
        if not conn:
            raise RuntimeError(
                f"Không tìm thấy kết nối {clean_plat} đang hoạt động cho shop '{scenario_tag}'."
            )

        connector = ensure_fresh_connector(db, conn)
        since_dt = _parse_iso_dt(conn.get("last_synced_at"))
        fetched = connector.fetch_reviews(since=since_dt, limit=limit)

        inserted_count = 0
        alerts_sent = 0
        auto_replied_count = 0
        if fetched:
            ingest_res = ingest_review_batch(
                db=db,
                reviews=fetched,
                scenario_tag=scenario_tag,
                analyzer_method=analyzer_method,
            )
            inserted_count = int(ingest_res.get("inserted_count", 0))
            dispatches = notify_critical_reviews(db=db, scenario_tag=scenario_tag, reviews=fetched)
            alerts_sent = len([d for d in dispatches if d.get("status") == "SENT"])

            shop_info = db.get_pilot_shop(scenario_tag, include_secret=False)
            if shop_info and (shop_info.get("alert_config") or {}).get("auto_reply_5star_enabled"):
                fetched_ids = [str(item.get("review_id") or "") for item in fetched]
                auto_res = auto_reply_eligible_five_star_reviews(
                    db=db,
                    scenario_tag=scenario_tag,
                    review_ids=fetched_ids,
                )
                auto_replied_count = int(auto_res.get("replied_count", 0))
                for rid_reply in auto_res.get("created_reply_ids") or []:
                    db.update_review_reply_external_sync(int(rid_reply), "QUEUED", None)
                    enqueue_background_job(
                        task_push_marketplace_reply,
                        None,
                        priority="critical",
                        reply_id=int(rid_reply),
                        scenario_tag=scenario_tag,
                        db_path=db_path,
                    )

        db.record_marketplace_sync_result(
            scenario_tag=scenario_tag,
            platform=clean_plat,
            status="OK",
            synced_at=now_iso,
            error_message=None,
        )
        details = {
            "scenario_tag": scenario_tag,
            "platform": clean_plat,
            "fetched_count": len(fetched),
            "inserted_count": inserted_count,
            "alerts_dispatched": alerts_sent,
            "auto_replied_5star": auto_replied_count,
            "synced_at": now_iso,
        }
        db.log_job_complete(job_id, status="completed", details=details)
        return details
    except Exception as exc:
        logger.exception(
            "Marketplace sync job %d failed (%s/%s): %s", job_id, scenario_tag, clean_plat, exc
        )
        db.record_marketplace_sync_result(
            scenario_tag=scenario_tag,
            platform=clean_plat,
            status="FAILED",
            synced_at=None,
            error_message=str(exc)[:300],
        )
        db.log_job_complete(
            job_id,
            status="failed",
            details={"scenario_tag": scenario_tag, "platform": clean_plat, "error": str(exc)},
        )
        raise


def task_push_marketplace_reply(
    reply_id: int,
    scenario_tag: str,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Worker task: push a G1-G6 verified CSKH reply directly to Shopee or TikTok Shop."""
    db = DatabaseManager(db_path=db_path or os.getenv("ECOMREVIEW_SQLITE_PATH"))
    with db.get_connection(read_only=True) as conn:
        row = conn.execute(
            """
            SELECT rr.id, rr.review_id, rr.scenario_tag, rr.reply_text,
                   rr.guardrail_passed, rr.external_sync_status, r.platform
            FROM review_replies rr
            JOIN reviews r
              ON r.review_id = rr.review_id AND r.scenario_tag = rr.scenario_tag
            WHERE rr.id = ? AND rr.scenario_tag = ?
            """,
            (reply_id, scenario_tag),
        ).fetchone()

    if not row:
        return {"reply_id": reply_id, "status": "not_found"}

    if str(row["external_sync_status"] or "") == "PUSHED":
        return {"reply_id": reply_id, "status": "already_pushed"}

    if not bool(row["guardrail_passed"]):
        db.update_review_reply_external_sync(
            reply_id, "FAILED", "Nội dung chưa vượt qua kiểm duyệt an toàn G1-G6."
        )
        return {"reply_id": reply_id, "status": "blocked_guardrail"}

    platform = str(row["platform"] or "").strip().lower()
    mp_conn = db.get_marketplace_connection(scenario_tag, platform, include_tokens=True)
    if not mp_conn:
        db.update_review_reply_external_sync(reply_id, "LOCAL_ONLY", None)
        return {"reply_id": reply_id, "status": "local_only"}

    try:
        connector = ensure_fresh_connector(db, mp_conn)
        resp = connector.post_reply(str(row["review_id"]), str(row["reply_text"]))
        db.update_review_reply_external_sync(reply_id, "PUSHED", None)
        return {"reply_id": reply_id, "status": "pushed", "platform": platform, "response": resp}
    except Exception as exc:
        logger.warning(
            "Push marketplace reply %d (%s/%s) failed: %s",
            reply_id,
            scenario_tag,
            platform,
            exc,
        )
        db.update_review_reply_external_sync(reply_id, "FAILED", str(exc)[:300])
        return {"reply_id": reply_id, "status": "failed", "error": str(exc)[:300]}


def run_scheduled_marketplace_sync(
    analyzer_method: str = "a1_gemini_v2",
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """Scan active auto-sync shop connections and enqueue due marketplace sync jobs."""
    db = DatabaseManager(db_path=db_path or os.getenv("ECOMREVIEW_SQLITE_PATH"))
    connections = db.list_marketplace_connections(only_auto_sync=True, include_tokens=False)
    now_dt = datetime.now(timezone.utc)
    triggered: list[dict[str, Any]] = []

    for mp in connections:
        last_dt = _parse_iso_dt(mp.get("last_synced_at"))
        interval_min = max(5, int(mp.get("sync_interval_minutes") or 30))
        if last_dt is not None and (now_dt - last_dt) < timedelta(minutes=interval_min):
            continue

        scenario_tag = str(mp["scenario_tag"])
        platform = str(mp["platform"])
        job_id = db.log_job_start(
            job_type="marketplace_sync",
            scenario_tag=scenario_tag,
            details={"scenario_tag": scenario_tag, "platform": platform, "scheduled": True},
        )
        backend = enqueue_background_job(
            task_sync_marketplace_reviews,
            None,
            job_id=job_id,
            scenario_tag=scenario_tag,
            platform=platform,
            analyzer_method=analyzer_method,
            db_path=db_path,
        )
        triggered.append(
            {
                "job_id": job_id,
                "scenario_tag": scenario_tag,
                "platform": platform,
                "queue_backend": backend,
            }
        )
    return triggered


def task_send_weekly_digest(
    scenario_tag: str,
    force: bool = False,
    as_of: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Worker task: compile deterministic weekly digest and dispatch to configured channels."""
    from ecomreview.alerts.notifier import dispatch_alert
    from ecomreview.reporting import build_weekly_digest

    db = DatabaseManager(db_path=db_path or os.getenv("ECOMREVIEW_SQLITE_PATH"))
    digest = build_weekly_digest(scenario_tag=scenario_tag, db=db, as_of=as_of)
    dedup_key = f"weekly_digest:{scenario_tag}:{digest['week_key']}"
    dispatches = dispatch_alert(
        db=db,
        scenario_tag=scenario_tag,
        dedup_key=dedup_key,
        severity="INFO",
        title=digest["title"],
        message_text=digest["message_text"],
        payload={"type": "weekly_digest", "week_key": digest["week_key"], **digest["metrics"]},
        force=force,
    )
    return {"digest": digest, "dispatches": dispatches}


def run_scheduled_weekly_digests(
    db_path: str | None = None,
    now_utc: datetime | None = None,
) -> list[dict[str, Any]]:
    """Trigger Monday morning ICT weekly digests for opted-in shops with per-week dedup."""
    ref_utc = now_utc or datetime.now(timezone.utc)
    if ref_utc.tzinfo is None:
        ref_utc = ref_utc.replace(tzinfo=timezone.utc)
    ict_now = ref_utc.astimezone(timezone(timedelta(hours=7)))
    if ict_now.weekday() != 0 or ict_now.hour < 8:
        return []

    iso_cal = ict_now.isocalendar()
    week_key = f"{iso_cal.year}-W{iso_cal.week:02d}"
    db = DatabaseManager(db_path=db_path or os.getenv("ECOMREVIEW_SQLITE_PATH"))
    shops = db.list_pilot_shops()
    triggered: list[dict[str, Any]] = []

    for shop in shops:
        cfg = dict(shop.get("alert_config") or {})
        if not cfg.get("weekly_digest_enabled"):
            continue
        stag = str(shop["slug"])
        has_tg = bool(
            (cfg.get("telegram_bot_token_configured") or cfg.get("telegram_bot_token"))
            and cfg.get("telegram_chat_id")
        )
        has_wh = bool(cfg.get("webhook_url"))
        if not has_tg and not has_wh:
            continue

        dedup_base = f"weekly_digest:{stag}:{week_key}"
        pending_channel = (has_tg and not db.has_alert_dispatch(f"{dedup_base}:telegram")) or (
            has_wh and not db.has_alert_dispatch(f"{dedup_base}:webhook")
        )
        if not pending_channel:
            continue

        backend = enqueue_background_job(
            task_send_weekly_digest,
            None,
            priority="low",
            scenario_tag=stag,
            force=False,
            as_of=ict_now.strftime("%Y-%m-%d"),
            db_path=db_path,
        )
        triggered.append({"scenario_tag": stag, "week_key": week_key, "queue_backend": backend})
    return triggered


# CreBy: MenBoyBMN
