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

import hashlib
import hmac
import json
import logging
import os
import re
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import AliasChoices, BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from ecomreview.agent.graph_runner import EcomReviewGraphRunner
from ecomreview.agent.insight_engine import InsightEngine
from ecomreview.agent.reply_assistant import check_reply_guardrails, generate_customer_reply
from ecomreview.agent.tools_aggregator import (
    detect_trend_alerts,
    get_action_impact,
    get_aspect_sentiment_stats,
    get_aspect_trend,
    get_hidden_complaints,
    get_platform_comparison,
    wilson_ci_pct,
)
from ecomreview.alerts.notifier import dispatch_alert, notify_critical_reviews, notify_trend_alerts
from ecomreview.analyze.factory import get_analyzer
from ecomreview.api.auth import (
    SESSION_COOKIE_NAME,
    create_access_token,
    get_jwt_secret,
    hash_password,
    is_production_env,
    verify_password,
)
from ecomreview.api.logging_utils import RequestLoggingMiddleware, configure_logging
from ecomreview.api.rate_limit import client_ip_from_request, rate_limiter
from ecomreview.api.security_deps import (
    VALID_ROLES,
    AuthPrincipal,
    assert_shop_access,
    get_current_principal,
    get_current_reviewer,
    require_roles,
)
from ecomreview.db.database import DatabaseManager
from ecomreview.ingest_service import (
    MAX_ASYNC_UPLOAD_ROWS,
    MAX_UPLOAD_FILE_BYTES,
    MAX_UPLOAD_ROWS,
    ingest_review_batch,
    parse_review_file,
)
from ecomreview.jobs.queue_worker import (
    enqueue_background_job,
    task_ingest_review_batch,
    task_run_analysis,
)
from ecomreview.reporting import build_excel_report, build_html_report
from ecomreview.schemas import Aspect, Polarity

logger = logging.getLogger(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _validate_analyzer_method(analyzer_method: str) -> None:
    """Validate analyzer_method early so unknown values fail cleanly with HTTP 400."""
    try:
        get_analyzer(analyzer_method)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


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

    @field_validator("opinions")
    @classmethod
    def _validate_opinions(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        validated: list[dict[str, Any]] = []
        for idx, op in enumerate(value):
            if not isinstance(op, dict):
                raise ValueError(f"opinions[{idx}] must be an object")
            try:
                asp = Aspect(str(op.get("aspect", "")).strip().upper()).value
                pol = Polarity(str(op.get("polarity", "")).strip().lower()).value
            except ValueError as exc:
                raise ValueError(f"opinions[{idx}] has invalid aspect/polarity: {exc}") from exc
            validated.append(
                {
                    **op,
                    "aspect": asp,
                    "polarity": pol,
                    "evidence": str(op.get("evidence") or ""),
                }
            )
        return validated


class ReviewUploadRequest(BaseModel):
    """Batch review upload request payload."""

    scenario_tag: str = "real_shop"
    analyzer_method: str = "a1_gemini_v2"
    reviews: list[ReviewUploadItem] = Field(min_length=1, max_length=1000)


class AnalyzeRunRequest(BaseModel):
    """Request payload to trigger ABSA + InsightEngine on a scenario."""

    scenario_tag: str = "real_shop"
    analyzer_method: str = "a1_gemini_v2"
    min_n: int = Field(default=5, ge=1, le=1000)
    async_mode: bool = False


class ActionGenerateRequest(BaseModel):
    """Request payload to trigger the State-Graph ActionPlanner + HybridCritic."""

    scenario_tag: str = "real_shop"
    min_n: int = Field(default=5, ge=1, le=1000)
    max_actions: int = Field(default=5, ge=1, le=20)


class ActionDecisionRequest(BaseModel):
    """Human-in-the-loop approval/edit/rejection payload."""

    decision: str = Field(description="APPROVED, EDITED, or REJECTED")
    note: str = ""
    edited_content: str = ""
    reason_category: str = ""


class ReviewReplyStatusRequest(BaseModel):
    """Payload for updating a customer care reply status (DRAFT/APPROVED/SENT)."""

    status: str = Field(description="DRAFT, APPROVED, or SENT")
    reply_text: str | None = None


class LoginRequest(BaseModel):
    """User login payload for Pilot JWT/Cookie authentication."""

    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=1, max_length=160)


class CreateShopRequest(BaseModel):
    """Payload to register a Pilot shop (slug maps 1-to-1 to scenario_tag)."""

    slug: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=120)
    industry: str = "raincoat"
    platforms: list[str] = Field(default_factory=lambda: ["shopee", "tiktok"])


class UpdateShopAlertsRequest(BaseModel):
    """Outbound Telegram / Webhook alerting configuration for a Pilot shop."""

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    webhook_url: str | None = None
    min_rating_alert: int = Field(default=2, ge=1, le=5)
    enable_critical_review_alert: bool = True
    enable_ztest_alert: bool = True


class CreateUserRequest(BaseModel):
    """Admin payload to provision an Owner, CSKH, or Admin user."""

    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=6, max_length=160)
    full_name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="owner", description="admin, owner, or cskh")
    allowed_shops: list[str] = Field(default_factory=list)


class ActionImplementedRequest(BaseModel):
    """Payload to record actual implementation date on an approved action."""

    implemented_at: str | None = Field(
        default=None, description="ISO date YYYY-MM-DD; defaults to today UTC"
    )


class AlertStatusUpdateRequest(BaseModel):
    """Payload to acknowledge or resolve an outbound alert dispatch."""

    status: str = Field(description="ACK or RESOLVED")


def _is_sla_overdue(rating: int, reply_status: str, created_at: str | None) -> bool:
    """Flag negative/low-rating reviews (<=3 stars) unanswered for >24 hours."""
    if rating > 3 or reply_status.upper() == "SENT" or not created_at:
        return False
    raw = created_at.strip()[:10]
    try:
        rev_dt = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - rev_dt > timedelta(hours=24)
    except ValueError:
        return False


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

        used_fallback = False
        if unparsed:
            analyzer = get_analyzer(analyzer_method)
            for r in unparsed:
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

        effective_method = f"{analyzer_method}+b1_fallback" if used_fallback else analyzer_method
        engine = InsightEngine(db=db)
        insights = engine.generate_insights(scenario_tag=scenario_tag, min_n=min_n, persist=True)
        alerts = detect_trend_alerts(scenario_tag=scenario_tag, min_n=min_n, db=db)
        dispatches = notify_trend_alerts(db=db, scenario_tag=scenario_tag, alerts=alerts)
        db.log_job_complete(
            job_id,
            status="completed",
            details={
                "scenario_tag": scenario_tag,
                "analyzer_method": effective_method,
                "unparsed_count": len(unparsed),
                "insights_generated": len(insights),
                "alerts_detected": len(alerts),
                "alerts_dispatched": len([d for d in dispatches if d.get("status") == "SENT"]),
            },
        )
    except Exception as e:
        logger.exception("Analysis job %d failed: %s", job_id, e)
        try:
            db.log_job_complete(
                job_id,
                status="failed",
                details={"scenario_tag": scenario_tag, "error": str(e)},
            )
        except Exception:
            logger.exception("Failed to mark analysis job %d as failed", job_id)


def create_app(db_path: str | None = None) -> FastAPI:
    """Factory creating the FastAPI application with configurable database path."""
    resolved_origins = [
        o.strip() for o in os.getenv("ECOMREVIEW_CORS_ORIGINS", "*").split(",") if o.strip()
    ] or ["*"]

    if is_production_env():
        get_jwt_secret()
        if resolved_origins == ["*"]:
            raise RuntimeError(
                "ECOMREVIEW_CORS_ORIGINS cannot be '*' when ECOMREVIEW_ENV=production."
            )

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        configure_logging()
        try:
            yield
        finally:
            DatabaseManager.close_pools()

    app = FastAPI(
        title="EcomReview AI API",
        description=(
            "Vietnamese Aspect-Based Sentiment Analysis & Evidence-Grounded "
            "Marketing Action Planning API for Raincoat E-Commerce SMEs."
        ),
        version="1.2.0",
        lifespan=_lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_origins,
        allow_credentials=(resolved_origins != ["*"]),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    resolved_db_path = db_path or os.getenv("ECOMREVIEW_SQLITE_PATH")
    db_instance = DatabaseManager(db_path=resolved_db_path)

    def _get_db() -> DatabaseManager:
        return db_instance

    # --- Pilot Authentication, Shop Management & Webhook Ingestion ---
    @app.post("/api/v1/auth/login", tags=["Auth"])
    def auth_login(payload: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
        """Authenticate a Pilot user and issue an HttpOnly JWT session cookie."""
        rate_limiter.check(
            f"login:{client_ip_from_request(request)}", max_requests=10, window_seconds=60
        )
        db = _get_db()
        user = db.get_user_by_email(payload.email, include_hash=True)
        if (
            not user
            or not user["is_active"]
            or not verify_password(payload.password, user["password_hash"])
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email hoặc mật khẩu không chính xác.",
            )
        token = create_access_token(user)
        db.update_user_last_login(int(user["id"]))
        raw_secure = os.getenv("ECOMREVIEW_COOKIE_SECURE", "").strip().lower()
        if raw_secure in {"true", "1", "yes"}:
            cookie_secure = True
        elif raw_secure in {"false", "0", "no"}:
            cookie_secure = False
        else:
            cookie_secure = is_production_env()
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
            secure=cookie_secure,
            max_age=12 * 3600,
            path="/",
        )
        public_user = {k: v for k, v in user.items() if k != "password_hash"}
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": public_user,
        }

    @app.post("/api/v1/auth/logout", tags=["Auth"])
    def auth_logout(response: Response) -> dict[str, Any]:
        """Clear the HttpOnly JWT session cookie."""
        response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
        return {"status": "logged_out"}

    @app.get("/api/v1/auth/me", tags=["Auth"])
    def auth_me(principal: AuthPrincipal = Depends(get_current_principal)) -> dict[str, Any]:
        """Return currently authenticated user profile and allowed Pilot shops."""
        return {
            "user": {
                "id": principal.user_id,
                "email": principal.email,
                "full_name": principal.full_name,
                "role": principal.role,
                "allowed_shops": principal.allowed_shops,
                "auth_type": principal.auth_type,
            },
            "env": os.getenv("ECOMREVIEW_ENV", "development").strip().lower(),
        }

    @app.get("/api/v1/shops", tags=["Pilot Management"])
    def list_shops(principal: AuthPrincipal = Depends(get_current_principal)) -> dict[str, Any]:
        """List active Pilot shops accessible to the authenticated user."""
        db = _get_db()
        allowed = None if principal.is_admin else principal.allowed_shops
        shops = db.list_pilot_shops(allowed_slugs=allowed)
        sanitized = []
        for s in shops:
            acfg = dict(s.get("alert_config") or {})
            if acfg.get("telegram_bot_token"):
                acfg["telegram_bot_token_configured"] = True
                acfg["telegram_bot_token"] = ""
            else:
                acfg["telegram_bot_token_configured"] = False
            sanitized.append({**s, "alert_config": acfg})
        return {"count": len(sanitized), "shops": sanitized}

    @app.post("/api/v1/shops", tags=["Pilot Management"])
    def create_shop(
        payload: CreateShopRequest,
        principal: AuthPrincipal = Depends(require_roles("admin")),
    ) -> dict[str, Any]:
        """Register a new Pilot shop workspace (Admin only)."""
        db = _get_db()
        shop = db.create_pilot_shop(
            slug=payload.slug,
            name=payload.name,
            industry=payload.industry,
            platforms=payload.platforms,
        )
        return shop

    @app.patch("/api/v1/shops/{slug}/alerts", tags=["Pilot Management"])
    def update_shop_alerts(
        slug: str,
        payload: UpdateShopAlertsRequest,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """Configure Telegram Bot / Webhook outbound alerting for a Pilot shop."""
        assert_shop_access(principal, slug)
        db = _get_db()
        if not db.get_pilot_shop(slug):
            db.create_pilot_shop(slug=slug, name=slug)
        patch: dict[str, Any] = {
            "min_rating_alert": payload.min_rating_alert,
            "enable_critical_review_alert": payload.enable_critical_review_alert,
            "enable_ztest_alert": payload.enable_ztest_alert,
        }
        if payload.telegram_bot_token is not None and payload.telegram_bot_token.strip():
            patch["telegram_bot_token"] = payload.telegram_bot_token.strip()
        if payload.telegram_chat_id is not None:
            patch["telegram_chat_id"] = payload.telegram_chat_id.strip()
        if payload.webhook_url is not None:
            patch["webhook_url"] = payload.webhook_url.strip()
        updated = db.update_pilot_shop_alerts(slug, patch)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Shop '{slug}' not found.")
        return updated

    @app.post("/api/v1/shops/{slug}/alerts/test", tags=["Pilot Management"])
    def test_shop_alerts(
        slug: str,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """Send a test outbound alert message to verify Telegram / Webhook settings."""
        assert_shop_access(principal, slug)
        db = _get_db()
        results = dispatch_alert(
            db=db,
            scenario_tag=slug,
            dedup_key=f"test:{slug}",
            severity="INFO",
            title="Kiểm tra kết nối cảnh báo EcomReview AI",
            message_text=(
                f"Kênh cảnh báo tự động cho gian hàng '{slug}' đã hoạt động bình thường "
                f"(kích hoạt bởi {principal.email})."
            ),
            payload={"type": "test_alert", "triggered_by": principal.email},
            force=True,
        )
        if not results:
            raise HTTPException(
                status_code=400,
                detail="Chưa cấu hình Telegram Bot Token/Chat ID hoặc Webhook URL cho gian hàng.",
            )
        return {"shop": slug, "results": results}

    @app.get("/api/v1/alerts/history", tags=["Analytics"])
    def get_alert_history(
        scenario_tag: str = Query(default="real_shop"),
        limit: int = Query(default=50, ge=1, le=200),
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """List persisted outbound alert dispatches for a shop."""
        assert_shop_access(principal, scenario_tag)
        db = _get_db()
        items = db.list_alert_dispatches(scenario_tag=scenario_tag, limit=limit)
        return {"scenario_tag": scenario_tag, "count": len(items), "dispatches": items}

    @app.patch("/api/v1/alerts/history/{dispatch_id}", tags=["Analytics"])
    def update_alert_history_status(
        dispatch_id: int,
        payload: AlertStatusUpdateRequest,
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """Acknowledge or resolve a dispatched alert."""
        target = payload.status.strip().upper()
        if target not in {"ACK", "RESOLVED"}:
            raise HTTPException(status_code=400, detail="status must be 'ACK' or 'RESOLVED'")
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            row = conn.execute(
                "SELECT id, scenario_tag FROM alert_dispatches WHERE id = ?", (dispatch_id,)
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Alert dispatch {dispatch_id} not found")
        assert_shop_access(principal, str(row["scenario_tag"]))
        updated = db.update_alert_dispatch_status(dispatch_id, target)
        return updated or {"id": dispatch_id, "status": target}

    @app.get("/api/v1/users", tags=["Pilot Management"])
    def list_users(
        principal: AuthPrincipal = Depends(require_roles("admin")),
    ) -> dict[str, Any]:
        """List Pilot user accounts (Admin only)."""
        db = _get_db()
        users = db.list_users()
        return {"count": len(users), "users": users}

    @app.post("/api/v1/users", tags=["Pilot Management"])
    def create_user(
        payload: CreateUserRequest,
        principal: AuthPrincipal = Depends(require_roles("admin")),
    ) -> dict[str, Any]:
        """Provision a Pilot user account with role and allowed shops (Admin only)."""
        role = payload.role.strip().lower()
        if role not in VALID_ROLES:
            raise HTTPException(
                status_code=400, detail=f"role must be one of {sorted(VALID_ROLES)}"
            )
        db = _get_db()
        return db.upsert_user(
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            role=role,
            allowed_shops=payload.allowed_shops,
        )

    @app.post("/api/v1/integrations/webhook/{shop_slug}", tags=["Integrations"])
    async def webhook_ingest_reviews(
        shop_slug: str,
        request: Request,
        background_tasks: BackgroundTasks,
        x_signature: str | None = Header(default=None, alias="X-EcomReview-Signature"),
    ) -> Any:
        """HMAC-authenticated webhook endpoint for n8n/Sapo/Haravan/Marketplace review pushes."""
        db = _get_db()
        shop = db.get_pilot_shop(shop_slug, include_secret=True)
        if not shop or not shop.get("webhook_secret"):
            raise HTTPException(status_code=404, detail=f"Webhook not enabled for '{shop_slug}'.")
        raw_body = await request.body()
        expected_sig = hmac.new(
            shop["webhook_secret"].encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        if not x_signature or not hmac.compare_digest(x_signature.strip(), expected_sig):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid X-EcomReview-Signature.",
            )
        try:
            body_json = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc

        raw_reviews = body_json.get("reviews") if isinstance(body_json, dict) else body_json
        if not isinstance(raw_reviews, list) or not raw_reviews:
            raise HTTPException(status_code=400, detail="Payload must contain non-empty reviews.")
        analyzer_method = (
            str(body_json.get("analyzer_method", "a1_gemini_v2"))
            if isinstance(body_json, dict)
            else "a1_gemini_v2"
        )
        _validate_analyzer_method(analyzer_method)

        job_id = db.log_job_start(
            job_type="webhook_ingest",
            scenario_tag=shop_slug,
            details={
                "scenario_tag": shop_slug,
                "total_count": len(raw_reviews),
                "processed_count": 0,
                "analyzer_method": analyzer_method,
            },
        )
        dispatch_backend = enqueue_background_job(
            task_ingest_review_batch,
            background_tasks,
            job_id=job_id,
            scenario_tag=shop_slug,
            reviews=raw_reviews[:MAX_ASYNC_UPLOAD_ROWS],
            analyzer_method=analyzer_method,
            db_path=resolved_db_path,
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "job_id": job_id,
                "scenario_tag": shop_slug,
                "queued_count": min(len(raw_reviews), MAX_ASYNC_UPLOAD_ROWS),
                "queue_backend": dispatch_backend,
                "status": "running",
            },
        )

    # 1. System Health
    @app.get("/api/v1/health", tags=["System"])
    def health_check() -> dict[str, Any]:
        """1. Check API, database connection, and security configuration status."""
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            rev_count = conn.execute("SELECT COUNT(*) AS cnt FROM reviews").fetchone()["cnt"]
        demo_mode = os.getenv("DEMO_CACHE_MODE", "true").lower() == "true"
        auth_enabled = bool(os.getenv("ECOMREVIEW_API_KEY", "").strip()) or is_production_env()
        queue_backend = "redis_rq" if os.getenv("REDIS_URL", "").strip() else "in_memory"
        return {
            "status": "healthy",
            "env": os.getenv("ECOMREVIEW_ENV", "development").strip().lower(),
            "database_backend": db.backend,
            "database_status": "connected",
            "queue_backend": queue_backend,
            "total_reviews_in_db": int(rev_count),
            "demo_cache_mode": demo_mode,
            "auth_enabled": auth_enabled,
            "endpoints_count": 15,
            "extended_endpoints_count": 18,
        }

    # 2. Ingestion
    @app.post(
        "/api/v1/reviews/upload",
        tags=["Ingestion"],
    )
    def upload_reviews(
        payload: ReviewUploadRequest,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """2. Upload, sanitize, analyze and persist a batch of customer reviews."""
        assert_shop_access(principal, payload.scenario_tag)
        rate_limiter.check(f"upload:{principal.email}", max_requests=30, window_seconds=60)
        _validate_analyzer_method(payload.analyzer_method)
        db = _get_db()
        job_id = db.log_job_start(
            job_type="reviews_upload",
            scenario_tag=payload.scenario_tag,
            details={
                "scenario_tag": payload.scenario_tag,
                "count": len(payload.reviews),
                "analyzer_method": payload.analyzer_method,
            },
        )

        try:
            review_dicts = [item.model_dump() for item in payload.reviews]
            ingest_res = ingest_review_batch(
                db=db,
                reviews=review_dicts,
                scenario_tag=payload.scenario_tag,
                analyzer_method=payload.analyzer_method,
            )
            notify_critical_reviews(db=db, scenario_tag=payload.scenario_tag, reviews=review_dicts)
            db.log_job_complete(job_id, status="completed", details=ingest_res)
            return {
                "job_id": job_id,
                "scenario_tag": payload.scenario_tag,
                "inserted_count": ingest_res["inserted_count"],
                "analyzer_method": ingest_res["analyzer_method"],
                "status": "completed",
            }
        except Exception as e:
            db.log_job_complete(
                job_id,
                status="failed",
                details={"scenario_tag": payload.scenario_tag, "error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload failed: {e}",
            )

    @app.post(
        "/api/v1/reviews/upload-file",
        tags=["Ingestion"],
    )
    async def upload_reviews_file(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        scenario_tag: str = Form(default="real_shop"),
        analyzer_method: str = Form(default="b1_rule"),
        platform: str = Form(default="shopee"),
        shop: str = Form(default="shop_aomua"),
        product: str = Form(default="ao_mua_da_ca"),
        async_mode: bool = Form(default=False),
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> Any:
        """16. Upload a .csv or .xlsx review file, validate rows, sanitize PII, and ingest."""
        assert_shop_access(principal, scenario_tag)
        rate_limiter.check(f"upload_file:{principal.email}", max_requests=20, window_seconds=60)
        _validate_analyzer_method(analyzer_method)
        content = await file.read()
        if len(content) > MAX_UPLOAD_FILE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Kích thước tệp vượt quá giới hạn 5 MB.",
            )

        max_rows = MAX_ASYNC_UPLOAD_ROWS if async_mode else MAX_UPLOAD_ROWS
        try:
            valid_reviews, skipped_rows = await run_in_threadpool(
                parse_review_file,
                filename=file.filename or "upload.csv",
                content=content,
                default_platform=platform,
                default_shop=shop,
                default_product=product,
                max_rows=max_rows,
            )
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

        db = _get_db()
        job_id = db.log_job_start(
            job_type="reviews_upload_file",
            scenario_tag=scenario_tag,
            details={
                "scenario_tag": scenario_tag,
                "filename": file.filename,
                "valid_count": len(valid_reviews),
                "total_count": len(valid_reviews),
                "processed_count": 0,
                "skipped_count": len(skipped_rows),
                "analyzer_method": analyzer_method,
                "async_mode": async_mode,
            },
        )
        if async_mode:
            queue_backend = enqueue_background_job(
                task_ingest_review_batch,
                background_tasks,
                job_id=job_id,
                scenario_tag=scenario_tag,
                reviews=valid_reviews,
                analyzer_method=analyzer_method,
                db_path=resolved_db_path,
            )
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "job_id": job_id,
                    "scenario_tag": scenario_tag,
                    "valid_count": len(valid_reviews),
                    "inserted_count": 0,
                    "skipped_count": len(skipped_rows),
                    "skipped_rows": skipped_rows[:20],
                    "analyzer_method": analyzer_method,
                    "queue_backend": queue_backend,
                    "status": "running",
                    "message": (
                        "Tệp đang được phân tích nền. Theo dõi tiến độ qua /api/v1/jobs/{job_id}."
                    ),
                },
            )

        try:
            ingest_res = await run_in_threadpool(
                ingest_review_batch,
                db=db,
                reviews=valid_reviews,
                scenario_tag=scenario_tag,
                analyzer_method=analyzer_method,
            )
            await run_in_threadpool(
                notify_critical_reviews, db=db, scenario_tag=scenario_tag, reviews=valid_reviews
            )
            db.log_job_complete(job_id, status="completed", details=ingest_res)
            return {
                "job_id": job_id,
                "scenario_tag": scenario_tag,
                "inserted_count": ingest_res["inserted_count"],
                "skipped_count": len(skipped_rows),
                "skipped_rows": skipped_rows[:20],
                "analyzer_method": ingest_res["analyzer_method"],
                "status": "completed",
            }
        except Exception as e:
            db.log_job_complete(
                job_id,
                status="failed",
                details={"scenario_tag": scenario_tag, "error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"File upload ingestion failed: {e}",
            )

    # 3. ABSA & Insight Analysis
    @app.post(
        "/api/v1/analyze/run",
        tags=["Analysis"],
    )
    def run_analysis(
        payload: AnalyzeRunRequest,
        background_tasks: BackgroundTasks,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> Any:
        """3. Run ABSA analysis and InsightEngine on a scenario (sync or async)."""
        assert_shop_access(principal, payload.scenario_tag)
        rate_limiter.check(f"analyze:{principal.email}", max_requests=20, window_seconds=60)
        _validate_analyzer_method(payload.analyzer_method)
        db = _get_db()
        job_id = db.log_job_start(
            job_type="analyze_run",
            scenario_tag=payload.scenario_tag,
            details={
                "scenario_tag": payload.scenario_tag,
                "analyzer_method": payload.analyzer_method,
                "min_n": payload.min_n,
                "async_mode": payload.async_mode,
            },
        )

        if payload.async_mode:
            queue_backend = enqueue_background_job(
                task_run_analysis,
                background_tasks,
                job_id=job_id,
                scenario_tag=payload.scenario_tag,
                analyzer_method=payload.analyzer_method,
                min_n=payload.min_n,
                db_path=resolved_db_path,
            )
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "job_id": job_id,
                    "scenario_tag": payload.scenario_tag,
                    "queue_backend": queue_backend,
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

        if job_row and str(job_row["status"]).lower() == "failed":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=job_details.get("error", "Analysis job failed"),
            )

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
    )
    def get_job_status(
        job_id: int,
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """4. Query audit status of a background or synchronous job."""
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            row = conn.execute("SELECT * FROM system_jobs_audit WHERE id = ?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        details = json.loads(row["details"] or "{}")
        job_scenario = (
            row["scenario_tag"]
            if "scenario_tag" in row.keys() and row["scenario_tag"]
            else details.get("scenario_tag")
        )
        if job_scenario:
            assert_shop_access(principal, str(job_scenario))
        return {
            "job_id": int(row["id"]),
            "job_type": str(row["job_type"]),
            "scenario_tag": job_scenario,
            "status": str(row["status"]),
            "details": details,
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        }

    # 5. Executive Overview Analytics
    @app.get(
        "/api/v1/stats/overview",
        tags=["Analytics"],
    )
    def get_overview_stats(
        scenario_tag: str = Query(default="real_shop"),
        min_n: int = Query(default=3),
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """5. Return executive KPIs, Wilson 95% CI aspect stats, and platform comparison."""
        assert_shop_access(principal, scenario_tag)
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
                    SUM(CASE WHEN platform = 'tiktok' THEN 1 ELSE 0 END) AS tiktok_reviews,
                    SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) AS high_rating_total
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
        platform_comparison = get_platform_comparison(scenario_tag=scenario_tag, min_n=min_n, db=db)
        platform_gaps = [g for g in platform_comparison if g["gap_pct"] >= 20.0]
        hidden_items = get_hidden_complaints(scenario_tag=scenario_tag, db=db)
        hidden_rids = {h["review_id"] for h in hidden_items}
        aspect_counts: dict[str, int] = defaultdict(int)
        for h in hidden_items:
            aspect_counts[h["aspect"]] += 1
        top_hidden = [
            {"aspect": asp, "count": cnt}
            for asp, cnt in sorted(aspect_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        hidden_summary = {
            "hidden_count": len(hidden_rids),
            "high_rating_total": int(total_row["high_rating_total"] or 0),
            "top_hidden_aspects": top_hidden,
            "items": hidden_items,
        }

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
    )
    def list_insights(
        scenario_tag: str = Query(default="real_shop"),
        kind: str | None = Query(default=None),
        include_archived: bool = Query(default=False),
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """6. Retrieve numerically verified Insights for a scenario."""
        assert_shop_access(principal, scenario_tag)
        db = _get_db()
        arch_clause = "" if include_archived else " AND COALESCE(is_archived, 0) = 0"
        with db.get_connection(read_only=True) as conn:
            if kind:
                rows = conn.execute(
                    f"SELECT * FROM insights WHERE scenario_tag = ? AND kind = ?{arch_clause} "
                    f"ORDER BY id ASC",
                    (scenario_tag, kind),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM insights WHERE scenario_tag = ?{arch_clause} ORDER BY id ASC",
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
                "is_archived": bool(r["is_archived"]) if "is_archived" in r.keys() else False,
            }
            for r in rows
        ]
        return {"scenario_tag": scenario_tag, "count": len(items), "insights": items}

    # 7. Action Planning
    @app.post(
        "/api/v1/actions/generate",
        tags=["Actions"],
    )
    def generate_actions(
        payload: ActionGenerateRequest,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """7. Execute the P1 State-Graph (Planner <-> HybridCritic) to generate grounded actions."""
        assert_shop_access(principal, payload.scenario_tag)
        rate_limiter.check(f"actions_gen:{principal.email}", max_requests=20, window_seconds=60)
        db = _get_db()
        trace_raw = Path(os.getenv("ECOMREVIEW_TRACE_DIR", "results/traces"))
        trace_dir = trace_raw if trace_raw.is_absolute() else (_PROJECT_ROOT / trace_raw)
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
    )
    def list_actions(
        scenario_tag: str = Query(default="real_shop"),
        is_marketing: bool | None = Query(default=None),
        status: str | None = Query(default=None),
        include_archived: bool = Query(default=False),
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """8. Retrieve persisted ActionProposals and their HybridCritic traces."""
        assert_shop_access(principal, scenario_tag)
        db = _get_db()
        query = "SELECT * FROM actions WHERE scenario_tag = ?"
        params: list[Any] = [scenario_tag]
        if not include_archived:
            query += " AND COALESCE(is_archived, 0) = 0"
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
                "is_archived": bool(r["is_archived"]) if "is_archived" in r.keys() else False,
                "implemented_at": (
                    str(r["implemented_at"])
                    if "implemented_at" in r.keys() and r["implemented_at"]
                    else None
                ),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
        return {"scenario_tag": scenario_tag, "count": len(actions), "actions": actions}

    # 9. Human Approval Gate
    @app.post(
        "/api/v1/actions/{action_id}/decision",
        tags=["Actions"],
    )
    def submit_action_decision(
        action_id: int,
        payload: ActionDecisionRequest,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
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
            exists = conn.execute(
                "SELECT id, scenario_tag FROM actions WHERE id = ?", (action_id,)
            ).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Action {action_id} not found")
        assert_shop_access(principal, str(exists["scenario_tag"]))

        result = db.record_action_decision(
            action_id=action_id,
            decision=payload.decision,
            note=payload.note,
            edited_content=payload.edited_content,
            reason_category=payload.reason_category,
            decided_by=reviewer,
        )
        return result

    @app.post(
        "/api/v1/actions/{action_id}/implemented",
        tags=["Actions"],
    )
    def mark_action_implemented(
        action_id: int,
        payload: ActionImplementedRequest,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """Record actual rollout date on an approved action for Pre/Post impact measurement."""
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            exists = conn.execute(
                "SELECT id, scenario_tag FROM actions WHERE id = ?", (action_id,)
            ).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Action {action_id} not found")
        assert_shop_access(principal, str(exists["scenario_tag"]))
        updated = db.mark_action_implemented(
            action_id=action_id,
            implemented_at=payload.implemented_at,
        )
        if not updated:
            raise HTTPException(status_code=404, detail=f"Action {action_id} not found")
        return updated

    # 10. Reviews Exploration (with batch opinions query - N+1 fix)
    @app.get(
        "/api/v1/reviews",
        tags=["Reviews"],
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
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """10. Query customer reviews and their extracted ABSA opinions with pagination."""
        assert_shop_access(principal, scenario_tag)
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            if review_ids:
                id_list = list(
                    dict.fromkeys(i.strip() for i in review_ids.split(",") if i.strip())
                )[:200]
                if id_list:
                    placeholders = ",".join("?" for _ in id_list)
                    where_sql = f" WHERE r.scenario_tag = ? AND r.review_id IN ({placeholders})"
                    p_where = [scenario_tag, *id_list]
                    if platform:
                        where_sql += " AND r.platform = ?"
                        p_where.append(platform)
                    if aspect:
                        if polarity:
                            where_sql += (
                                " AND EXISTS (SELECT 1 FROM opinions o "
                                "WHERE o.review_id = r.review_id "
                                "AND o.scenario_tag = r.scenario_tag "
                                "AND o.aspect = ? AND o.polarity = ?)"
                            )
                            p_where.extend([aspect, polarity])
                        else:
                            where_sql += (
                                " AND EXISTS (SELECT 1 FROM opinions o "
                                "WHERE o.review_id = r.review_id "
                                "AND o.scenario_tag = r.scenario_tag "
                                "AND o.aspect = ?)"
                            )
                            p_where.append(aspect)
                    elif polarity:
                        where_sql += " AND LOWER(r.overall_sentiment) = ?"
                        p_where.append(polarity.strip().lower())
                    cnt_row = conn.execute(
                        f"SELECT COUNT(*) AS cnt FROM reviews r{where_sql}",
                        tuple(p_where),
                    ).fetchone()
                    total_count = int(cnt_row["cnt"] or 0) if cnt_row else 0
                    rows = conn.execute(
                        f"SELECT r.* FROM reviews r{where_sql} "
                        "ORDER BY r.review_id ASC LIMIT ? OFFSET ?",
                        (*p_where, limit, offset),
                    ).fetchall()
                else:
                    rows = []
                    total_count = 0
            elif aspect:
                where_sql = " WHERE r.scenario_tag = ? AND o.aspect = ?"
                p_where: list[Any] = [scenario_tag, aspect]
                if polarity:
                    where_sql += " AND o.polarity = ?"
                    p_where.append(polarity)
                if platform:
                    where_sql += " AND r.platform = ?"
                    p_where.append(platform)
                cnt_row = conn.execute(
                    f"SELECT COUNT(DISTINCT r.review_id) AS cnt "
                    f"FROM reviews r "
                    f"JOIN opinions o ON r.review_id = o.review_id "
                    f"AND r.scenario_tag = o.scenario_tag"
                    f"{where_sql}",
                    tuple(p_where),
                ).fetchone()
                total_count = int(cnt_row["cnt"] or 0) if cnt_row else 0
                rows = conn.execute(
                    f"SELECT DISTINCT r.* "
                    f"FROM reviews r "
                    f"JOIN opinions o ON r.review_id = o.review_id "
                    f"AND r.scenario_tag = o.scenario_tag"
                    f"{where_sql} ORDER BY r.review_id ASC LIMIT ? OFFSET ?",
                    (*p_where, limit, offset),
                ).fetchall()
            else:
                where_sql = " WHERE scenario_tag = ?"
                p_where = [scenario_tag]
                if platform:
                    where_sql += " AND platform = ?"
                    p_where.append(platform)
                if polarity:
                    where_sql += " AND overall_sentiment = ?"
                    p_where.append(polarity)
                cnt_row = conn.execute(
                    f"SELECT COUNT(*) AS cnt FROM reviews{where_sql}",
                    tuple(p_where),
                ).fetchone()
                total_count = int(cnt_row["cnt"] or 0) if cnt_row else 0
                rows = conn.execute(
                    f"SELECT * FROM reviews{where_sql} ORDER BY review_id ASC LIMIT ? OFFSET ?",
                    (*p_where, limit, offset),
                ).fetchall()

            # Batch fetch opinions and latest reply status to eliminate N+1 queries
            matched_rids = [str(r["review_id"]) for r in rows]
            opinions_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
            reply_status_map: dict[str, str] = {}
            latest_reply_map: dict[str, dict[str, Any]] = {}
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
                rep_rows = conn.execute(
                    f"SELECT id, review_id, reply_text, mode_used, guardrail_passed, "
                    f"violations, status, created_by, created_at, sent_at "
                    f"FROM review_replies "
                    f"WHERE scenario_tag = ? AND review_id IN ({ph}) ORDER BY id ASC",
                    (scenario_tag, *matched_rids),
                ).fetchall()
                for rep in rep_rows:
                    rid_key = str(rep["review_id"])
                    raw_v = rep["violations"]
                    viol_list = (
                        json.loads(raw_v or "[]") if isinstance(raw_v, str) else list(raw_v or [])
                    )
                    reply_status_map[rid_key] = str(rep["status"])
                    latest_reply_map[rid_key] = {
                        "reply_id": int(rep["id"]),
                        "reply_text": str(rep["reply_text"]),
                        "mode_used": str(rep["mode_used"]),
                        "guardrail_report": {
                            "passed": bool(rep["guardrail_passed"]),
                            "violations": viol_list,
                        },
                        "status": str(rep["status"]),
                        "created_by": str(rep["created_by"] or ""),
                        "created_at": str(rep["created_at"] or ""),
                        "sent_at": str(rep["sent_at"]) if rep["sent_at"] else None,
                    }

            reviews_out = []
            for r in rows:
                rid = str(r["review_id"])
                rep_st = reply_status_map.get(rid, "NONE")
                rating_val = int(r["rating"] or 5)
                created_val = str(r["created_at"]) if r["created_at"] else None
                reviews_out.append(
                    {
                        "review_id": rid,
                        "platform": str(r["platform"]),
                        "rating": rating_val,
                        "text_raw": str(r["text_raw"]),
                        "created_at": created_val,
                        "overall_sentiment": str(r["overall_sentiment"] or "neutral"),
                        "reply_status": rep_st,
                        "sla_overdue": _is_sla_overdue(rating_val, rep_st, created_val),
                        "latest_reply": latest_reply_map.get(rid),
                        "opinions": opinions_map.get(rid, []),
                    }
                )

        return {
            "scenario_tag": scenario_tag,
            "count": len(reviews_out),
            "total_count": total_count,
            "reviews": reviews_out,
        }

    # 11. Trend Analysis
    @app.get(
        "/api/v1/trends",
        tags=["Analytics"],
    )
    def get_trends(
        scenario_tag: str = Query(default="real_shop"),
        aspect: str | None = Query(default=None),
        period: str = Query(default="month", description="'month' or 'week'"),
        min_n: int = Query(default=3),
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """11. Query historical sentiment trends grouped by week or month with Wilson 95% CI."""
        assert_shop_access(principal, scenario_tag)
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
    )
    def get_alerts(
        scenario_tag: str = Query(default="real_shop"),
        period: str = Query(default="month"),
        baseline_periods: int = Query(default=3),
        min_n: int = Query(default=5),
        min_delta_pp: float = Query(default=10.0),
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """12. Detect statistical spike alerts based on two-proportion one-sided z-test."""
        assert_shop_access(principal, scenario_tag)
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
    )
    def create_reply_draft(
        review_id: str,
        scenario_tag: str = Query(default="real_shop"),
        mode: str = Query(default="template", description="'template' or 'llm'"),
        principal: AuthPrincipal = Depends(get_current_principal),
        reviewer: str = Depends(get_current_reviewer),
    ) -> dict[str, Any]:
        """13. Generate, verify, and persist a policy-compliant customer service reply draft."""
        assert_shop_access(principal, scenario_tag)
        norm_mode = mode.strip().lower()
        if norm_mode not in {"template", "llm"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="mode must be 'template' or 'llm'",
            )
        db = _get_db()
        res = generate_customer_reply(
            review_id=review_id,
            scenario_tag=scenario_tag,
            mode=norm_mode,
            db=db,
        )
        if res.get("status") == "error":
            raise HTTPException(status_code=404, detail=res.get("message"))
        gr = res.get("guardrail_report") or {}
        reply_id = db.insert_review_reply(
            review_id=review_id,
            scenario_tag=scenario_tag,
            reply_text=str(res["reply_text"]),
            mode_used=str(res.get("mode_used", mode)),
            guardrail_passed=bool(gr.get("passed", res.get("guardrail_passed", True))),
            violations=list(gr.get("violations") or res.get("violations") or []),
            status="DRAFT",
            created_by=reviewer,
        )
        res["reply_id"] = reply_id
        res["status"] = "DRAFT"
        return res

    @app.get(
        "/api/v1/reviews/{review_id}/replies",
        tags=["Customer Care"],
    )
    def get_review_replies(
        review_id: str,
        scenario_tag: str = Query(default="real_shop"),
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """17. Retrieve persisted customer service reply drafts for a review."""
        assert_shop_access(principal, scenario_tag)
        db = _get_db()
        replies = db.list_review_replies(review_id=review_id, scenario_tag=scenario_tag)
        return {
            "review_id": review_id,
            "scenario_tag": scenario_tag,
            "count": len(replies),
            "replies": replies,
        }

    @app.post(
        "/api/v1/reviews/replies/{reply_id}/status",
        tags=["Customer Care"],
    )
    def update_reply_status(
        reply_id: int,
        payload: ReviewReplyStatusRequest,
        principal: AuthPrincipal = Depends(get_current_principal),
        reviewer: str = Depends(get_current_reviewer),
    ) -> dict[str, Any]:
        """18. Transition a customer reply draft status (DRAFT -> APPROVED -> SENT)."""
        valid_statuses = {"DRAFT", "APPROVED", "SENT"}
        target_status = payload.status.strip().upper()
        if target_status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"status must be one of {sorted(valid_statuses)}",
            )
        logger.info("Reply %s status transition -> %s by %s", reply_id, target_status, reviewer)

        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            existing = conn.execute(
                "SELECT review_id, scenario_tag, reply_text, guardrail_passed, violations "
                "FROM review_replies WHERE id = ?",
                (reply_id,),
            ).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail=f"Reply {reply_id} not found")
            assert_shop_access(principal, str(existing["scenario_tag"]))
            neg_rows = conn.execute(
                "SELECT DISTINCT aspect FROM opinions "
                "WHERE review_id = ? AND scenario_tag = ? AND polarity = 'negative'",
                (existing["review_id"], existing["scenario_tag"]),
            ).fetchall()
            neg_aspects = [str(r["aspect"]) for r in neg_rows]

        guardrail_passed: bool | None = None
        violations: list[str] | None = None
        if payload.reply_text is not None and payload.reply_text.strip():
            report = check_reply_guardrails(
                reply_text=payload.reply_text.strip(),
                negative_aspects=neg_aspects,
            )
            guardrail_passed = report.passed
            violations = report.violations
            if not report.passed and target_status in {"APPROVED", "SENT"}:
                joined_viols = "; ".join(report.violations)
                raise HTTPException(
                    status_code=400,
                    detail=f"Nội dung phản hồi vi phạm quy tắc an toàn G1-G6: {joined_viols}",
                )
        elif target_status in {"APPROVED", "SENT"}:
            stored_passed = bool(existing["guardrail_passed"])
            recheck = check_reply_guardrails(
                reply_text=str(existing["reply_text"] or ""),
                negative_aspects=neg_aspects,
            )
            if not stored_passed or not recheck.passed:
                existing_viols = existing["violations"]
                if isinstance(existing_viols, str):
                    try:
                        existing_viols = json.loads(existing_viols)
                    except Exception:
                        existing_viols = [existing_viols] if existing_viols else []
                viols = recheck.violations or (existing_viols or ["Chưa đạt quy tắc an toàn G1-G6"])
                raise HTTPException(
                    status_code=400,
                    detail=f"Nội dung phản hồi vi phạm quy tắc an toàn G1-G6: {'; '.join(viols)}",
                )

        updated = db.update_review_reply_status(
            reply_id=reply_id,
            status=target_status,
            reply_text=payload.reply_text,
            guardrail_passed=guardrail_passed,
            violations=violations,
        )
        if not updated:
            raise HTTPException(status_code=404, detail=f"Reply {reply_id} not found")
        return updated

    # 14. Action Intervention Impact
    @app.get(
        "/api/v1/actions/{action_id}/impact",
        tags=["Actions"],
    )
    def measure_action_impact(
        action_id: int,
        window_days: int = Query(default=30, ge=1, le=365),
        since: str | None = Query(default=None),
        min_n: int = Query(default=3, ge=1, le=1000),
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """14. Measure pre vs post intervention sentiment for aspects targeted by action."""
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            act_row = conn.execute(
                "SELECT scenario_tag FROM actions WHERE id = ?", (action_id,)
            ).fetchone()
        if not act_row:
            raise HTTPException(status_code=404, detail=f"Action {action_id} not found.")
        assert_shop_access(principal, str(act_row["scenario_tag"]))
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
    )
    def export_report(
        scenario_tag: str = Query(default="real_shop"),
        format: str = Query(default="xlsx", description="'xlsx' or 'html'"),
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> Response:
        """15. Export executive multi-tab Excel workbook (.xlsx) or printable HTML report."""
        assert_shop_access(principal, scenario_tag)
        db = _get_db()
        fmt = format.strip().lower()
        safe_tag = re.sub(r"[^a-zA-Z0-9_\-]", "_", scenario_tag)[:64]
        if fmt in ("xlsx", "excel"):
            xlsx_bytes = build_excel_report(scenario_tag=scenario_tag, db=db)
            filename = f"EcomReview_Report_{safe_tag}.xlsx"
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
