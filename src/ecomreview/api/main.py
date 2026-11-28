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
import ipaddress
import json
import logging
import os
import re
import secrets
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
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
from ecomreview.agent.playbook_loader import list_industry_templates, normalize_industry
from ecomreview.agent.reply_assistant import (
    auto_reply_eligible_five_star_reviews,
    check_reply_guardrails,
    generate_customer_reply,
)
from ecomreview.agent.tools_aggregator import (
    detect_trend_alerts,
    get_action_impact,
    get_aspect_sentiment_stats,
    get_aspect_trend,
    get_executive_multi_shop_summary,
    get_hidden_complaints,
    get_platform_comparison,
    get_sku_variation_stats,
    wilson_ci_pct,
)
from ecomreview.alerts.notifier import (
    VALID_WEBHOOK_FORMATS,
    dispatch_alert,
    notify_critical_reviews,
    notify_trend_alerts,
)
from ecomreview.analyze.factory import get_analyzer
from ecomreview.api.auth import (
    REFRESH_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    create_access_token,
    generate_refresh_token,
    get_jwt_secret,
    hash_password,
    hash_token,
    is_production_env,
    refresh_token_expiry_iso,
    verify_password,
)
from ecomreview.api.logging_utils import RequestLoggingMiddleware, configure_logging
from ecomreview.api.metrics import init_sentry_if_configured, metrics_registry
from ecomreview.api.rate_limit import (
    account_lockout,
    client_ip_from_request,
    rate_limiter,
    tenant_job_quota,
    webhook_replay_guard,
)
from ecomreview.api.security_deps import (
    VALID_ROLES,
    AuthPrincipal,
    assert_shop_access,
    get_current_principal,
    get_current_reviewer,
    require_roles,
)
from ecomreview.billing.quota_service import (
    PLAN_CATALOG,
    QuotaExceededError,
    current_month_key,
    record_reply_usage,
    resolve_subscription,
)
from ecomreview.connectors.factory import SUPPORTED_PLATFORMS, get_connector_class
from ecomreview.crypto import get_encryption_keys
from ecomreview.db.database import DatabaseManager
from ecomreview.ingest_service import (
    MAX_ASYNC_UPLOAD_ROWS,
    MAX_UPLOAD_FILE_BYTES,
    MAX_UPLOAD_ROWS,
    ingest_review_batch,
    parse_review_file,
)
from ecomreview.jobs.queue_worker import (
    PRIORITY_QUEUES,
    _get_redis_client,
    enqueue_background_job,
    list_dlq_entries,
    task_ingest_review_batch,
    task_push_marketplace_reply,
    task_run_analysis,
    task_sync_marketplace_reviews,
)
from ecomreview.reporting import build_excel_report, build_html_report, build_weekly_digest
from ecomreview.schemas import Aspect, Polarity
from ecomreview.security import scrub_pii, validate_webhook_url

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
    variation: str = ""
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
    push_to_marketplace: bool = True


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
    webhook_format: str | None = None
    zalo_oa_recipient_id: str | None = None
    weekly_digest_enabled: bool | None = None
    min_rating_alert: int = Field(default=2, ge=1, le=5)
    enable_critical_review_alert: bool = True
    enable_ztest_alert: bool = True
    auto_reply_5star_enabled: bool | None = None


class UpdateShopProfileRequest(BaseModel):
    """Industry template and per-shop CSKH/Planner Brand Voice configuration."""

    industry: str | None = None
    tone: str | None = Field(default=None, max_length=200)
    shop_signature: str | None = Field(default=None, max_length=120)
    return_policy: str | None = Field(default=None, max_length=200)
    cskh_notes: str | None = Field(default=None, max_length=400)
    custom_overclaim_keywords: list[str] | None = None


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


class ChangePasswordRequest(BaseModel):
    """Payload to change the authenticated user's password."""

    current_password: str = Field(min_length=1, max_length=160)
    new_password: str = Field(min_length=8, max_length=160)


class UpdateUserStatusRequest(BaseModel):
    """Admin payload to activate or suspend a user account."""

    is_active: bool


class CreateShopApiKeyRequest(BaseModel):
    """Payload to mint a scoped API key restricted to a single shop."""

    name: str = Field(min_length=2, max_length=120)
    role: str = Field(default="owner", description="'owner' or 'cskh'")
    scopes: list[str] = Field(default_factory=lambda: ["read", "write"])


class RefreshTokenRequest(BaseModel):
    """Optional JSON body for refresh token rotation when not using cookies."""

    refresh_token: str | None = None


class AuthorizeConnectorRequest(BaseModel):
    """Payload to generate an OAuth authorization URL for Shopee or TikTok Shop."""

    redirect_url: str = Field(min_length=8, max_length=500)


class ManualConnectorRequest(BaseModel):
    """Payload to save or update a shop marketplace connection directly."""

    external_shop_id: str = Field(min_length=1, max_length=120)
    access_token: str = Field(min_length=4, max_length=1000)
    refresh_token: str | None = None
    expires_in_seconds: int = Field(default=14400, ge=60, le=31536000)
    shop_name: str | None = None
    auto_sync_enabled: bool = True
    sync_interval_minutes: int = Field(default=30, ge=5, le=1440)


class SyncConnectorRequest(BaseModel):
    """Payload to trigger an on-demand marketplace review sync."""

    analyzer_method: str = "a1_gemini_v2"
    limit: int = Field(default=100, ge=1, le=500)


class BulkReplyDraftRequest(BaseModel):
    """Payload to generate G1-G6 CSKH reply drafts for up to 50 reviews."""

    scenario_tag: str = "real_shop"
    review_ids: list[str] = Field(min_length=1, max_length=50)
    mode: str = "template"


class BulkReplyStatusRequest(BaseModel):
    """Payload to approve or send up to 50 CSKH reply drafts in one batch."""

    scenario_tag: str = "real_shop"
    reply_ids: list[int] = Field(min_length=1, max_length=50)
    status: str = Field(description="APPROVED or SENT")
    push_to_marketplace: bool = True


class AutoReply5StarRequest(BaseModel):
    """Payload to trigger G1-G6 compliant auto-reply for clean 5-star reviews."""

    scenario_tag: str = "real_shop"
    review_ids: list[str] | None = None
    limit: int = Field(default=50, ge=1, le=100)
    push_to_marketplace: bool = True


class RegisterTrialRequest(BaseModel):
    """Self-service 14-day trial workspace signup payload."""

    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=6, max_length=160)
    full_name: str = Field(min_length=1, max_length=120)
    shop_name: str = Field(min_length=2, max_length=120)
    shop_slug: str | None = Field(default=None, max_length=64)
    industry: str = "raincoat"
    seed_sample_data: bool = True


class AdminUpdateSubscriptionRequest(BaseModel):
    """Admin payload to assign or upgrade a tenant SaaS subscription package."""

    plan_code: str = Field(default="basic")
    status: str = Field(default="ACTIVE")
    monthly_llm_review_limit: int | None = Field(default=None, ge=0, le=5000000)
    max_shops: int | None = Field(default=None, ge=1, le=1000)
    max_users: int | None = Field(default=None, ge=1, le=1000)
    overage_policy: str = Field(default="fallback_b1")
    notes: str | None = Field(default=None, max_length=500)


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
        get_encryption_keys()
        if resolved_origins == ["*"]:
            raise RuntimeError(
                "ECOMREVIEW_CORS_ORIGINS cannot be '*' when ECOMREVIEW_ENV=production."
            )

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        configure_logging()
        init_sentry_if_configured()
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
    app.state.db = db_instance

    def _get_db() -> DatabaseManager:
        return db_instance

    def _resolve_cookie_secure() -> bool:
        raw_secure = os.getenv("ECOMREVIEW_COOKIE_SECURE", "").strip().lower()
        if raw_secure in {"true", "1", "yes"}:
            return True
        if raw_secure in {"false", "0", "no"}:
            return False
        return is_production_env()

    def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
        cookie_secure = _resolve_cookie_secure()
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=access_token,
            httponly=True,
            samesite="lax",
            secure=cookie_secure,
            max_age=12 * 3600,
            path="/",
        )
        response.set_cookie(
            key=REFRESH_COOKIE_NAME,
            value=refresh_token,
            httponly=True,
            samesite="lax",
            secure=cookie_secure,
            max_age=14 * 24 * 3600,
            path="/api/v1/auth",
        )

    def _clear_auth_cookies(response: Response) -> None:
        response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
        response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/api/v1/auth")

    def _record_audit(
        request: Request,
        actor: str,
        actor_role: str,
        action: str,
        scenario_tag: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        try:
            db_instance.record_audit_log(
                actor=actor,
                actor_role=actor_role,
                action=action,
                scenario_tag=scenario_tag,
                target_type=target_type,
                target_id=target_id,
                ip_address=client_ip_from_request(request),
                request_id=getattr(request.state, "request_id", None),
                details=details,
            )
        except Exception as exc:
            logger.warning("Failed to record audit log (%s): %s", action, exc)

    # --- Pilot Authentication, Shop Management & Webhook Ingestion ---
    @app.post("/api/v1/auth/login", tags=["Auth"])
    def auth_login(payload: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
        """Authenticate a Pilot user and issue HttpOnly JWT + Refresh cookies."""
        rate_limiter.check(
            f"login:{client_ip_from_request(request)}", max_requests=20, window_seconds=60
        )
        locked_sec = account_lockout.is_locked(payload.email)
        if locked_sec > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Tài khoản tạm thời bị khóa do đăng nhập sai nhiều lần. "
                    f"Vui lòng thử lại sau {locked_sec} giây."
                ),
            )
        db = _get_db()
        user = db.get_user_by_email(payload.email, include_hash=True)
        if (
            not user
            or not user["is_active"]
            or not verify_password(payload.password, user["password_hash"])
        ):
            account_lockout.record_failure(payload.email)
            _record_audit(
                request,
                actor=payload.email.strip().lower()[:160] or "anonymous",
                actor_role="anonymous",
                action="auth.login_failed",
                target_type="user",
                target_id=payload.email.strip().lower(),
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email hoặc mật khẩu không chính xác.",
            )

        account_lockout.clear(payload.email)
        token = create_access_token(user)
        raw_refresh, refresh_hash = generate_refresh_token()
        family_id = secrets.token_hex(16)
        db.create_refresh_token(
            user_id=int(user["id"]),
            token_hash=refresh_hash,
            family_id=family_id,
            expires_at=refresh_token_expiry_iso(),
        )
        db.update_user_last_login(int(user["id"]))
        _set_auth_cookies(response, token, raw_refresh)
        _record_audit(
            request,
            actor=str(user["email"]),
            actor_role=str(user["role"]),
            action="auth.login",
            target_type="user",
            target_id=str(user["id"]),
        )
        public_user = {k: v for k, v in user.items() if k != "password_hash"}
        return {
            "access_token": token,
            "refresh_token": raw_refresh,
            "token_type": "bearer",
            "user": public_user,
        }

    @app.post("/api/v1/auth/refresh", tags=["Auth"])
    def auth_refresh(
        request: Request,
        response: Response,
        payload: RefreshTokenRequest | None = None,
    ) -> dict[str, Any]:
        """Rotate refresh token and issue a fresh JWT access token."""
        raw_rt = (payload.refresh_token or "").strip() if payload and payload.refresh_token else ""
        if not raw_rt:
            raw_rt = (request.cookies.get(REFRESH_COOKIE_NAME) or "").strip()
        if not raw_rt:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Thiếu refresh token.",
            )

        db = _get_db()
        new_raw_rt, new_rt_hash = generate_refresh_token()
        rot = db.rotate_refresh_token(
            old_token_hash=hash_token(raw_rt),
            new_token_hash=new_rt_hash,
            new_expires_at=refresh_token_expiry_iso(),
        )
        if rot.get("status") != "ok":
            _clear_auth_cookies(response)
            _record_audit(
                request,
                actor=f"user:{rot.get('user_id', 'unknown')}",
                actor_role="anonymous",
                action="auth.refresh_rejected",
                target_type="refresh_token",
                details={"reason": rot.get("status")},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Phiên làm mới không hợp lệ hoặc đã bị thu hồi.",
            )

        user = db.get_user_by_id(int(rot["user_id"]))
        if not user or not user.get("is_active"):
            _clear_auth_cookies(response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tài khoản đã bị vô hiệu hóa.",
            )

        new_access = create_access_token(user)
        _set_auth_cookies(response, new_access, new_raw_rt)
        _record_audit(
            request,
            actor=str(user["email"]),
            actor_role=str(user["role"]),
            action="auth.refresh",
            target_type="user",
            target_id=str(user["id"]),
        )
        return {
            "access_token": new_access,
            "refresh_token": new_raw_rt,
            "token_type": "bearer",
            "user": user,
        }

    @app.post("/api/v1/auth/logout", tags=["Auth"])
    def auth_logout(request: Request, response: Response) -> dict[str, Any]:
        """Revoke refresh token and clear HttpOnly session cookies."""
        raw_rt = (request.cookies.get(REFRESH_COOKIE_NAME) or "").strip()
        if raw_rt:
            _get_db().revoke_refresh_token(hash_token(raw_rt))
        _clear_auth_cookies(response)
        _record_audit(
            request,
            actor="session_cookie",
            actor_role="user",
            action="auth.logout",
        )
        return {"status": "logged_out"}

    @app.post("/api/v1/auth/register-trial", tags=["Auth"])
    def auth_register_trial(
        payload: RegisterTrialRequest,
        request: Request,
        response: Response,
    ) -> dict[str, Any]:
        """Self-service 14-day trial signup creating an Owner, first shop, and trial quota."""
        if os.getenv("ECOMREVIEW_ALLOW_SELF_SIGNUP", "true").strip().lower() not in {
            "true",
            "1",
            "yes",
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tính năng tự đăng ký dùng thử hiện đang tạm khóa.",
            )
        rate_limiter.check(
            f"register_trial:{client_ip_from_request(request)}", max_requests=10, window_seconds=300
        )

        clean_email = payload.email.strip().lower()
        raw_slug = (payload.shop_slug or payload.shop_name).strip().lower()
        clean_slug = re.sub(r"[^a-zA-Z0-9_\-]+", "_", raw_slug).strip("_")[:64]
        if len(clean_slug) < 2:
            clean_slug = f"shop_{secrets.token_hex(4)}"

        db = _get_db()
        if db.get_user_by_email(clean_email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email này đã được đăng ký tài khoản.",
            )
        if db.get_pilot_shop(clean_slug):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Mã gian hàng '{clean_slug}' đã tồn tại. Vui lòng chọn mã khác.",
            )

        norm_ind = normalize_industry(payload.industry)
        shop = db.create_pilot_shop(
            slug=clean_slug,
            name=payload.shop_name.strip(),
            industry=norm_ind,
            platforms=["shopee", "tiktok"],
        )
        user = db.upsert_user(
            email=clean_email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name.strip(),
            role="owner",
            allowed_shops=[clean_slug],
        )
        trial_plan = PLAN_CATALOG["trial"]
        trial_end = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
        subscription = db.upsert_tenant_subscription(
            tenant_key=clean_slug,
            plan_code="trial",
            status="TRIAL",
            monthly_llm_review_limit=trial_plan["monthly_llm_review_limit"],
            max_shops=trial_plan["max_shops"],
            max_users=trial_plan["max_users"],
            overage_policy="fallback_b1",
            trial_ends_at=trial_end,
            notes="Self-service 14-day trial",
            updated_by=clean_email,
        )

        if payload.seed_sample_data:
            today_s = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            starter_reviews = [
                {
                    "review_id": f"{clean_slug}_demo_1",
                    "platform": "shopee",
                    "shop": clean_slug,
                    "product": "san_pham_chu_luc",
                    "rating": 2,
                    "text": "Đóng gói hơi móp hộp, giao hàng chậm hơn dự kiến nhưng chất liệu ổn.",
                    "created_at": today_s,
                },
                {
                    "review_id": f"{clean_slug}_demo_2",
                    "platform": "tiktok",
                    "shop": clean_slug,
                    "product": "san_pham_chu_luc",
                    "rating": 5,
                    "text": "Kiểu dáng màu sắc đẹp y hình, giá cả hợp lý đáng tiền lắm ạ.",
                    "created_at": today_s,
                },
                {
                    "review_id": f"{clean_slug}_demo_3",
                    "platform": "shopee",
                    "shop": clean_slug,
                    "product": "san_pham_chu_luc",
                    "rating": 5,
                    "text": "Shop tư vấn nhiệt tình, sản phẩm dùng tiện lợi rất hài lòng.",
                    "created_at": today_s,
                },
            ]
            ingest_review_batch(
                db=db,
                reviews=starter_reviews,
                scenario_tag=clean_slug,
                analyzer_method="b1_rule",
            )

        token = create_access_token(user)
        raw_refresh, refresh_hash = generate_refresh_token()
        db.create_refresh_token(
            user_id=int(user["id"]),
            token_hash=refresh_hash,
            family_id=secrets.token_hex(16),
            expires_at=refresh_token_expiry_iso(),
        )
        _set_auth_cookies(response, token, raw_refresh)
        _record_audit(
            request,
            actor=clean_email,
            actor_role="owner",
            action="auth.register_trial",
            scenario_tag=clean_slug,
            target_type="pilot_shop",
            target_id=clean_slug,
            details={"industry": norm_ind, "plan_code": "trial"},
        )
        return {
            "status": "registered",
            "user": {
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role"],
                "allowed_shops": user["allowed_shops"],
            },
            "shop": {
                "slug": shop["slug"],
                "name": shop["name"],
                "industry": shop["industry"],
            },
            "subscription": subscription,
        }

    @app.post("/api/v1/auth/change-password", tags=["Auth"])
    def auth_change_password(
        payload: ChangePasswordRequest,
        request: Request,
        response: Response,
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """Change password for current user and revoke all previously issued sessions."""
        if principal.user_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ tài khoản người dùng mới hỗ trợ đổi mật khẩu.",
            )
        db = _get_db()
        user = db.get_user_by_id(principal.user_id, include_hash=True)
        if not user or not verify_password(payload.current_password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu hiện tại không chính xác.",
            )
        db.update_user_password(principal.user_id, hash_password(payload.new_password))
        _clear_auth_cookies(response)
        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="auth.change_password",
            target_type="user",
            target_id=str(principal.user_id),
        )
        return {"status": "password_changed"}

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

    @app.get("/api/v1/industries", tags=["Pilot Management"])
    def get_industry_templates(
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """List supported multi-industry Playbook templates and aspect labels."""
        return {"industries": list_industry_templates()}

    @app.get("/api/v1/shops", tags=["Pilot Management"])
    def list_shops(principal: AuthPrincipal = Depends(get_current_principal)) -> dict[str, Any]:
        """List active Pilot shops accessible to the authenticated user."""
        db = _get_db()
        allowed = None if principal.is_admin else principal.allowed_shops
        shops = db.list_pilot_shops(allowed_slugs=allowed)
        sanitized = []
        for s in shops:
            acfg = dict(s.get("alert_config") or {})
            has_tg = bool(
                acfg.get("telegram_bot_token_configured") or acfg.get("telegram_bot_token")
            )
            acfg["telegram_bot_token_configured"] = has_tg
            acfg["telegram_bot_token"] = ""
            sanitized.append({**s, "alert_config": acfg})
        return {"count": len(sanitized), "shops": sanitized}

    @app.post("/api/v1/shops", tags=["Pilot Management"])
    def create_shop(
        payload: CreateShopRequest,
        request: Request,
        principal: AuthPrincipal = Depends(require_roles("admin")),
    ) -> dict[str, Any]:
        """Register a new Pilot shop workspace (Admin only)."""
        db = _get_db()
        shop = db.create_pilot_shop(
            slug=payload.slug,
            name=payload.name,
            industry=normalize_industry(payload.industry),
            platforms=payload.platforms,
        )
        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="shop.create",
            scenario_tag=shop["slug"],
            target_type="pilot_shop",
            target_id=shop["slug"],
        )
        return shop

    @app.patch("/api/v1/shops/{slug}/alerts", tags=["Pilot Management"])
    def update_shop_alerts(
        slug: str,
        payload: UpdateShopAlertsRequest,
        request: Request,
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
        if payload.auto_reply_5star_enabled is not None:
            patch["auto_reply_5star_enabled"] = bool(payload.auto_reply_5star_enabled)
        if payload.webhook_format is not None:
            fmt = payload.webhook_format.strip().lower()
            if fmt not in VALID_WEBHOOK_FORMATS:
                raise HTTPException(
                    status_code=400,
                    detail=f"webhook_format must be one of {sorted(VALID_WEBHOOK_FORMATS)}",
                )
            patch["webhook_format"] = fmt
        if payload.zalo_oa_recipient_id is not None:
            patch["zalo_oa_recipient_id"] = payload.zalo_oa_recipient_id.strip()[:120]
        if payload.weekly_digest_enabled is not None:
            patch["weekly_digest_enabled"] = bool(payload.weekly_digest_enabled)
        if payload.webhook_url is not None:
            raw_wh = payload.webhook_url.strip()
            if raw_wh:
                try:
                    patch["webhook_url"] = validate_webhook_url(raw_wh)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
            else:
                patch["webhook_url"] = ""
        updated = db.update_pilot_shop_alerts(slug, patch)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Shop '{slug}' not found.")
        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="shop.alerts_update",
            scenario_tag=slug,
            target_type="pilot_shop",
            target_id=slug,
            details={"min_rating_alert": payload.min_rating_alert},
        )
        return updated

    @app.patch("/api/v1/shops/{slug}/profile", tags=["Pilot Management"])
    def update_shop_profile(
        slug: str,
        payload: UpdateShopProfileRequest,
        request: Request,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """Update shop industry Playbook template and Brand Voice profile."""
        assert_shop_access(principal, slug)
        db = _get_db()
        if not db.get_pilot_shop(slug):
            db.create_pilot_shop(slug=slug, name=slug)

        norm_ind = normalize_industry(payload.industry) if payload.industry is not None else None
        bv_patch: dict[str, Any] = {}
        if payload.tone is not None:
            bv_patch["tone"] = scrub_pii(payload.tone.strip())
        if payload.shop_signature is not None:
            bv_patch["shop_signature"] = scrub_pii(payload.shop_signature.strip())
        if payload.return_policy is not None:
            bv_patch["return_policy"] = scrub_pii(payload.return_policy.strip())
        if payload.cskh_notes is not None:
            bv_patch["cskh_notes"] = scrub_pii(payload.cskh_notes.strip())
        if payload.custom_overclaim_keywords is not None:
            bv_patch["custom_overclaim_keywords"] = [
                scrub_pii(str(k).strip())[:80]
                for k in payload.custom_overclaim_keywords[:30]
                if str(k).strip()
            ]

        updated = db.update_pilot_shop_profile(
            slug,
            industry=norm_ind,
            brand_voice=bv_patch if bv_patch else None,
        )
        if not updated:
            raise HTTPException(status_code=404, detail=f"Shop '{slug}' not found.")
        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="shop.profile_update",
            scenario_tag=slug,
            target_type="pilot_shop",
            target_id=slug,
            details={"industry": updated.get("industry")},
        )
        return updated

    @app.post("/api/v1/shops/{slug}/digest/send", tags=["Pilot Management"])
    def send_shop_weekly_digest(
        slug: str,
        request: Request,
        force: bool = Query(default=False),
        preview_only: bool = Query(default=False),
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """Compile verified weekly KPI digest and optionally dispatch to Telegram/Webhook."""
        assert_shop_access(principal, slug)
        db = _get_db()
        digest = build_weekly_digest(scenario_tag=slug, db=db)
        dispatches: list[dict[str, Any]] = []
        if not preview_only:
            dedup_key = f"weekly_digest:{slug}:{digest['week_key']}"
            dispatches = dispatch_alert(
                db=db,
                scenario_tag=slug,
                dedup_key=dedup_key,
                severity="INFO",
                title=digest["title"],
                message_text=digest["message_text"],
                payload={
                    "type": "weekly_digest",
                    "week_key": digest["week_key"],
                    **digest["metrics"],
                },
                force=force,
            )
            _record_audit(
                request,
                actor=principal.email,
                actor_role=principal.role,
                action="shop.weekly_digest_send",
                scenario_tag=slug,
                target_type="pilot_shop",
                target_id=slug,
                details={"week_key": digest["week_key"], "force": force},
            )
        return {"shop": slug, "digest": digest, "dispatches": dispatches}

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
        request: Request,
        principal: AuthPrincipal = Depends(require_roles("admin")),
    ) -> dict[str, Any]:
        """Provision a Pilot user account with role and allowed shops (Admin only)."""
        role = payload.role.strip().lower()
        if role not in VALID_ROLES:
            raise HTTPException(
                status_code=400, detail=f"role must be one of {sorted(VALID_ROLES)}"
            )
        db = _get_db()
        created = db.upsert_user(
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            role=role,
            allowed_shops=payload.allowed_shops,
        )
        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="user.upsert",
            target_type="user",
            target_id=str(created["id"]),
            details={"email": created["email"], "role": role},
        )
        return created

    @app.patch("/api/v1/users/{user_id}/status", tags=["Pilot Management"])
    def update_user_status(
        user_id: int,
        payload: UpdateUserStatusRequest,
        request: Request,
        principal: AuthPrincipal = Depends(require_roles("admin")),
    ) -> dict[str, Any]:
        """Activate or suspend a user; suspending immediately invalidates existing tokens."""
        db = _get_db()
        updated = db.set_user_active(user_id=user_id, is_active=payload.is_active)
        if not updated:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="user.status_update",
            target_type="user",
            target_id=str(user_id),
            details={"is_active": payload.is_active},
        )
        return updated

    @app.get("/api/v1/team/users", tags=["Pilot Management"])
    def list_team_users(
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """List CSKH team members scoped cleanly to the Owner's authorized shops."""
        db = _get_db()
        all_users = db.list_users()
        if principal.is_admin:
            return {"count": len(all_users), "users": all_users}

        owner_shops = set(principal.allowed_shops)
        scoped = []
        for u in all_users:
            u_shops = set(u.get("allowed_shops") or [])
            if str(u["email"]).lower() == principal.email.lower():
                scoped.append(u)
            elif str(u["role"]).lower() == "cskh" and u_shops and u_shops.issubset(owner_shops):
                scoped.append(u)
        return {"count": len(scoped), "users": scoped}

    @app.post("/api/v1/team/users", tags=["Pilot Management"])
    def create_team_user(
        payload: CreateUserRequest,
        request: Request,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """Allow an Owner to provision CSKH staff strictly within their allowed shops."""
        db = _get_db()
        req_role = payload.role.strip().lower()
        clean_email = payload.email.strip().lower()
        target_shops = [str(s).strip() for s in payload.allowed_shops if str(s).strip()]

        if not principal.is_admin:
            if req_role != "cskh":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Chủ shop chỉ được phép tạo tài khoản nhân viên CSKH.",
                )
            if not target_shops or not set(target_shops).issubset(set(principal.allowed_shops)):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Chỉ được phân quyền nhân viên cho các gian hàng thuộc sở hữu của bạn.",
                )
            existing_u = db.get_user_by_email(clean_email, include_hash=False)
            if existing_u is not None:
                ex_shops = set(existing_u.get("allowed_shops") or [])
                if str(existing_u["role"]).lower() != "cskh" or not ex_shops.issubset(
                    set(principal.allowed_shops)
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Email này thuộc quyền quản lý khác hoặc có vai trò cao hơn CSKH.",
                    )
            else:
                sub = resolve_subscription(db, [*principal.allowed_shops, principal.email])
                owner_shops = set(principal.allowed_shops)
                cur_team = [
                    u
                    for u in db.list_users()
                    if str(u["email"]).lower() == principal.email.lower()
                    or (
                        str(u["role"]).lower() == "cskh"
                        and set(u.get("allowed_shops") or []).issubset(owner_shops)
                    )
                ]
                if len(cur_team) >= int(sub.get("max_users") or 3):
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail=(
                            f"Đã đạt giới hạn {sub['max_users']} tài khoản của gói "
                            f"{sub['plan_code'].upper()}. Vui lòng nâng cấp gói để thêm nhân sự."
                        ),
                    )
        else:
            if req_role not in VALID_ROLES:
                raise HTTPException(
                    status_code=400, detail=f"role must be one of {sorted(VALID_ROLES)}"
                )

        created = db.upsert_user(
            email=clean_email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            role=req_role,
            allowed_shops=target_shops,
        )
        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="team.user_create",
            target_type="user",
            target_id=str(created["id"]),
            details={"email": created["email"], "role": req_role, "allowed_shops": target_shops},
        )
        return created

    @app.patch("/api/v1/team/users/{user_id}/status", tags=["Pilot Management"])
    def update_team_user_status(
        user_id: int,
        payload: UpdateUserStatusRequest,
        request: Request,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """Allow an Owner to activate/suspend their own CSKH staff (revoking tokens)."""
        db = _get_db()
        target_user = db.get_user_by_id(user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

        if not principal.is_admin:
            t_shops = set(target_user.get("allowed_shops") or [])
            if (
                str(target_user["role"]).lower() != "cskh"
                or not t_shops
                or not t_shops.issubset(set(principal.allowed_shops))
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền thay đổi trạng thái tài khoản này.",
                )

        updated = db.set_user_active(user_id=user_id, is_active=payload.is_active)
        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="team.user_status_update",
            target_type="user",
            target_id=str(user_id),
            details={"is_active": payload.is_active},
        )
        return updated

    @app.post("/api/v1/workspace/shops", tags=["Pilot Management"])
    def create_workspace_shop(
        payload: CreateShopRequest,
        request: Request,
        response: Response,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """Create a new shop within the Owner/Agency workspace plan limits."""
        db = _get_db()
        clean_slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", payload.slug.strip().lower())[:64]
        if len(clean_slug) < 2:
            raise HTTPException(status_code=400, detail="Mã gian hàng phải có ít nhất 2 ký tự.")
        if db.get_pilot_shop(clean_slug):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Mã gian hàng '{clean_slug}' đã tồn tại.",
            )

        if not principal.is_admin:
            sub = resolve_subscription(db, [*principal.allowed_shops, principal.email])
            current_shops = db.list_pilot_shops(allowed_slugs=principal.allowed_shops)
            if len(current_shops) >= int(sub.get("max_shops") or 2):
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=(
                        f"Đã đạt giới hạn {sub['max_shops']} gian hàng của gói "
                        f"{sub['plan_code'].upper()}. Vui lòng nâng cấp lên Pro hoặc Agency."
                    ),
                )

        norm_ind = normalize_industry(payload.industry)
        shop = db.create_pilot_shop(
            slug=clean_slug,
            name=payload.name,
            industry=norm_ind,
            platforms=payload.platforms,
        )

        if not principal.is_admin:
            user_rec = db.get_user_by_email(principal.email, include_hash=False)
            if user_rec:
                new_allowed = [*user_rec["allowed_shops"], clean_slug]
                updated_user = db.update_user_allowed_shops(int(user_rec["id"]), new_allowed)
                if updated_user:
                    new_token = create_access_token(updated_user)
                    response.set_cookie(
                        key=SESSION_COOKIE_NAME,
                        value=new_token,
                        httponly=True,
                        samesite="lax",
                        secure=_resolve_cookie_secure(),
                        max_age=12 * 3600,
                        path="/",
                    )

        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="workspace.shop_create",
            scenario_tag=clean_slug,
            target_type="pilot_shop",
            target_id=clean_slug,
            details={"industry": norm_ind},
        )
        return shop

    @app.get("/api/v1/shops/{slug}/api-keys", tags=["Pilot Management"])
    def list_shop_api_keys(
        slug: str,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """List scoped API keys for a shop (hashes are never returned)."""
        assert_shop_access(principal, slug)
        items = _get_db().list_shop_api_keys(slug)
        return {"scenario_tag": slug, "count": len(items), "api_keys": items}

    @app.post("/api/v1/shops/{slug}/api-keys", tags=["Pilot Management"])
    def create_shop_api_key_endpoint(
        slug: str,
        payload: CreateShopApiKeyRequest,
        request: Request,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """Mint a new API key restricted strictly to one shop."""
        assert_shop_access(principal, slug)
        db = _get_db()
        try:
            created = db.create_shop_api_key(
                scenario_tag=slug,
                name=payload.name,
                role=payload.role,
                scopes=payload.scopes,
                created_by=principal.email,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="shop.api_key_create",
            scenario_tag=slug,
            target_type="shop_api_key",
            target_id=str(created["id"]),
            details={"key_prefix": created["key_prefix"], "role": created["role"]},
        )
        return created

    @app.delete("/api/v1/shops/{slug}/api-keys/{key_id}", tags=["Pilot Management"])
    def revoke_shop_api_key_endpoint(
        slug: str,
        key_id: int,
        request: Request,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """Revoke a scoped shop API key immediately."""
        assert_shop_access(principal, slug)
        revoked = _get_db().revoke_shop_api_key(key_id=key_id, scenario_tag=slug)
        if not revoked:
            raise HTTPException(status_code=404, detail=f"API key {key_id} not found")
        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="shop.api_key_revoke",
            scenario_tag=slug,
            target_type="shop_api_key",
            target_id=str(key_id),
        )
        return revoked

    @app.get("/api/v1/audit-logs", tags=["Pilot Management"])
    def get_audit_logs(
        scenario_tag: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """Query immutable audit log entries scoped to authorized shops."""
        if scenario_tag:
            assert_shop_access(principal, scenario_tag)
            allowed = None
        else:
            allowed = None if principal.is_admin else principal.allowed_shops
        logs = _get_db().list_audit_logs(
            scenario_tag=scenario_tag,
            allowed_shops=allowed,
            limit=limit,
        )
        return {"count": len(logs), "logs": logs}

    def _create_oauth_state(scenario_tag: str, platform: str, actor: str) -> str:
        now_dt = datetime.now(timezone.utc)
        payload = {
            "purpose": "marketplace_oauth",
            "scenario_tag": scenario_tag,
            "platform": platform,
            "actor": actor,
            "iat": int(now_dt.timestamp()),
            "exp": int((now_dt + timedelta(minutes=15)).timestamp()),
        }
        return jwt.encode(payload, get_jwt_secret(), algorithm="HS256")

    def _decode_oauth_state(state_token: str, expected_platform: str) -> dict[str, Any]:
        try:
            claims = jwt.decode(
                state_token,
                get_jwt_secret(),
                algorithms=["HS256"],
                options={"require": ["purpose", "scenario_tag", "platform", "exp"]},
            )
        except jwt.InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OAuth state không hợp lệ hoặc đã hết hạn.",
            ) from exc
        if (
            claims.get("purpose") != "marketplace_oauth"
            or str(claims.get("platform", "")).lower() != expected_platform
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OAuth state không khớp nền tảng.",
            )
        return claims

    @app.get("/api/v1/shops/{slug}/connectors", tags=["Integrations"])
    def list_shop_connectors(
        slug: str,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """List active two-way Shopee / TikTok Shop OAuth connections for a shop."""
        assert_shop_access(principal, slug)
        items = _get_db().list_marketplace_connections(scenario_tag=slug, include_tokens=False)
        by_plat = {c["platform"]: c for c in items}
        return {
            "scenario_tag": slug,
            "supported_platforms": list(SUPPORTED_PLATFORMS),
            "connections": items,
            "platforms": {p: by_plat.get(p) for p in SUPPORTED_PLATFORMS},
        }

    @app.post("/api/v1/shops/{slug}/connectors/{platform}/authorize", tags=["Integrations"])
    def authorize_shop_connector(
        slug: str,
        platform: str,
        payload: AuthorizeConnectorRequest,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """Generate a signed OAuth 2.0 authorization URL for Shopee or TikTok Shop."""
        assert_shop_access(principal, slug)
        clean_plat = platform.strip().lower()
        try:
            conn_cls = get_connector_class(clean_plat)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state = _create_oauth_state(slug, clean_plat, principal.email)
        try:
            auth_url = conn_cls().build_auth_url(redirect_url=payload.redirect_url, state=state)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "scenario_tag": slug,
            "platform": clean_plat,
            "auth_url": auth_url,
            "state": state,
        }

    @app.get("/api/v1/integrations/oauth/{platform}/callback", tags=["Integrations"])
    def marketplace_oauth_callback(
        platform: str,
        request: Request,
        code: str = Query(min_length=1),
        state: str = Query(min_length=8),
        shop_id: str | None = Query(default=None),
        shop_cipher: str | None = Query(default=None),
    ) -> dict[str, Any]:
        """Handle Shopee / TikTok OAuth callback, exchange code, and store encrypted tokens."""
        clean_plat = platform.strip().lower()
        if clean_plat not in SUPPORTED_PLATFORMS:
            raise HTTPException(status_code=400, detail=f"Unsupported platform '{platform}'.")
        claims = _decode_oauth_state(state, clean_plat)
        slug = str(claims["scenario_tag"])

        conn_cls = get_connector_class(clean_plat)
        connector = conn_cls()
        try:
            if clean_plat == "shopee":
                if not shop_id:
                    raise HTTPException(status_code=400, detail="Thiếu shop_id từ Shopee callback.")
                tok_data = connector.exchange_code_for_token(code=code, shop_id=shop_id)
            else:
                tok_data = connector.exchange_code_for_token(
                    code=code, shop_cipher=(shop_cipher or "")
                )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"OAuth token exchange failed: {exc}")

        expires_in = int(tok_data.get("expires_in") or 14400)
        now_dt = datetime.now(timezone.utc)
        exp_iso = (now_dt + timedelta(seconds=max(60, expires_in))).isoformat()
        ref_exp_in = tok_data.get("refresh_expires_in")
        ref_exp_iso = (
            (now_dt + timedelta(seconds=max(60, int(ref_exp_in)))).isoformat()
            if ref_exp_in
            else None
        )

        db = _get_db()
        if not db.get_pilot_shop(slug):
            db.create_pilot_shop(slug=slug, name=slug)
        saved = db.upsert_marketplace_connection(
            scenario_tag=slug,
            platform=clean_plat,
            external_shop_id=str(tok_data.get("external_shop_id") or shop_id or shop_cipher or ""),
            access_token=str(tok_data.get("access_token") or ""),
            refresh_token=str(tok_data.get("refresh_token") or ""),
            token_expires_at=exp_iso,
            refresh_expires_at=ref_exp_iso,
            shop_name=str(tok_data.get("shop_name") or ""),
        )
        _record_audit(
            request,
            actor=str(claims.get("actor") or "oauth_callback"),
            actor_role="owner",
            action="connector.oauth_connected",
            scenario_tag=slug,
            target_type="marketplace_connection",
            target_id=f"{slug}:{clean_plat}",
            details={"external_shop_id": saved["external_shop_id"]},
        )
        return {"status": "connected", "connection": saved}

    @app.post("/api/v1/shops/{slug}/connectors/{platform}/manual", tags=["Integrations"])
    def save_manual_shop_connector(
        slug: str,
        platform: str,
        payload: ManualConnectorRequest,
        request: Request,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """Connect or update Shopee / TikTok credentials manually for a shop."""
        assert_shop_access(principal, slug)
        clean_plat = platform.strip().lower()
        if clean_plat not in SUPPORTED_PLATFORMS:
            raise HTTPException(status_code=400, detail=f"Unsupported platform '{platform}'.")
        db = _get_db()
        if not db.get_pilot_shop(slug):
            db.create_pilot_shop(slug=slug, name=slug)
        exp_iso = (
            datetime.now(timezone.utc) + timedelta(seconds=payload.expires_in_seconds)
        ).isoformat()
        saved = db.upsert_marketplace_connection(
            scenario_tag=slug,
            platform=clean_plat,
            external_shop_id=payload.external_shop_id,
            access_token=payload.access_token,
            refresh_token=payload.refresh_token,
            token_expires_at=exp_iso,
            shop_name=payload.shop_name,
            auto_sync_enabled=payload.auto_sync_enabled,
            sync_interval_minutes=payload.sync_interval_minutes,
        )
        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="connector.manual_connected",
            scenario_tag=slug,
            target_type="marketplace_connection",
            target_id=f"{slug}:{clean_plat}",
            details={"external_shop_id": saved["external_shop_id"]},
        )
        return {"status": "connected", "connection": saved}

    @app.delete("/api/v1/shops/{slug}/connectors/{platform}", tags=["Integrations"])
    def disconnect_shop_connector(
        slug: str,
        platform: str,
        request: Request,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """Disconnect Shopee / TikTok Shop integration and wipe stored tokens."""
        assert_shop_access(principal, slug)
        clean_plat = platform.strip().lower()
        deleted = _get_db().delete_marketplace_connection(slug, clean_plat)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Không tìm thấy kết nối '{clean_plat}' cho gian hàng '{slug}'.",
            )
        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="connector.disconnected",
            scenario_tag=slug,
            target_type="marketplace_connection",
            target_id=f"{slug}:{clean_plat}",
        )
        return {"status": "disconnected", "scenario_tag": slug, "platform": clean_plat}

    @app.post("/api/v1/shops/{slug}/connectors/{platform}/sync", tags=["Integrations"])
    def sync_shop_connector_now(
        slug: str,
        platform: str,
        request: Request,
        background_tasks: BackgroundTasks,
        payload: SyncConnectorRequest | None = None,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> JSONResponse:
        """Trigger an immediate background review sync from Shopee or TikTok Shop."""
        assert_shop_access(principal, slug)
        rate_limiter.check(f"mp_sync:{slug}:{principal.email}", max_requests=10, window_seconds=60)
        clean_plat = platform.strip().lower()
        if clean_plat not in SUPPORTED_PLATFORMS:
            raise HTTPException(status_code=400, detail=f"Unsupported platform '{platform}'.")
        req = payload or SyncConnectorRequest()
        _validate_analyzer_method(req.analyzer_method)

        db = _get_db()
        if not db.get_marketplace_connection(slug, clean_plat, include_tokens=False):
            raise HTTPException(
                status_code=404,
                detail=f"Gian hàng '{slug}' chưa kết nối '{clean_plat}'.",
            )
        job_id = db.log_job_start(
            job_type="marketplace_sync",
            scenario_tag=slug,
            details={"scenario_tag": slug, "platform": clean_plat, "limit": req.limit},
        )
        backend = enqueue_background_job(
            task_sync_marketplace_reviews,
            background_tasks,
            priority="critical",
            job_id=job_id,
            scenario_tag=slug,
            platform=clean_plat,
            analyzer_method=req.analyzer_method,
            limit=req.limit,
            db_path=resolved_db_path,
        )
        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="connector.manual_sync",
            scenario_tag=slug,
            target_type="marketplace_connection",
            target_id=f"{slug}:{clean_plat}",
            details={"job_id": job_id},
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "job_id": job_id,
                "scenario_tag": slug,
                "platform": clean_plat,
                "queue_backend": backend,
                "status": "running",
            },
        )

    @app.post("/api/v1/integrations/webhook/{shop_slug}", tags=["Integrations"])
    async def webhook_ingest_reviews(
        shop_slug: str,
        request: Request,
        background_tasks: BackgroundTasks,
        x_signature: str | None = Header(default=None, alias="X-EcomReview-Signature"),
        x_timestamp: str | None = Header(default=None, alias="X-EcomReview-Timestamp"),
        x_nonce: str | None = Header(default=None, alias="X-EcomReview-Nonce"),
    ) -> Any:
        """HMAC-authenticated webhook endpoint for n8n/Sapo/Haravan/Marketplace review pushes."""
        rate_limiter.check(
            f"webhook:{shop_slug}:{client_ip_from_request(request)}",
            max_requests=60,
            window_seconds=60,
        )
        db = _get_db()
        shop = db.get_pilot_shop(shop_slug, include_secret=True)
        if not shop or not shop.get("webhook_secret"):
            raise HTTPException(status_code=404, detail=f"Webhook not enabled for '{shop_slug}'.")
        raw_body = await request.body()

        if x_timestamp is not None and x_timestamp.strip():
            try:
                ts_val = int(x_timestamp.strip())
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="X-EcomReview-Timestamp không hợp lệ.",
                ) from exc
            if abs(int(time.time()) - ts_val) > 300:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Webhook timestamp đã hết hạn (vượt quá cửa sổ 5 phút).",
                )
            signed_payload = f"{ts_val}.".encode("utf-8") + raw_body
            expected_sig = hmac.new(
                shop["webhook_secret"].encode("utf-8"), signed_payload, hashlib.sha256
            ).hexdigest()
            if not x_signature or not hmac.compare_digest(x_signature.strip(), expected_sig):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid X-EcomReview-Signature.",
                )
            nonce_part = (x_nonce or expected_sig).strip()
            replay_key = f"{shop_slug}:{ts_val}:{nonce_part}"
            if not webhook_replay_guard.check_and_mark(replay_key, ttl_seconds=600):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Yêu cầu webhook bị trùng lặp (replay detected).",
                )
        else:
            if is_production_env():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=(
                        "Thiếu header X-EcomReview-Timestamp bắt buộc trong môi trường production."
                    ),
                )
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
            priority="critical",
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

    # 1. System Health & Prometheus Metrics
    @app.get("/metrics", tags=["System"])
    def prometheus_metrics(
        request: Request,
        x_metrics_token: str | None = Header(default=None, alias="X-Metrics-Token"),
    ) -> Response:
        """Expose Prometheus text exposition metrics protected by token or internal network."""
        expected_tok = os.getenv("ECOMREVIEW_METRICS_TOKEN", "").strip()
        if expected_tok:
            auth_h = request.headers.get("authorization", "").strip()
            bearer = auth_h[7:].strip() if auth_h.lower().startswith("bearer ") else ""
            cand = (x_metrics_token or bearer or "").strip()
            if not cand or not secrets.compare_digest(cand, expected_tok):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid metrics token.",
                )
        elif is_production_env():
            ip_str = client_ip_from_request(request).split("%", 1)[0]
            allowed_internal = ip_str in {"127.0.0.1", "::1", "testclient"}
            if not allowed_internal:
                try:
                    addr = ipaddress.ip_address(ip_str)
                    allowed_internal = bool(addr.is_loopback or addr.is_private)
                except ValueError:
                    allowed_internal = False
            if not allowed_internal:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Metrics endpoint restricted to internal network.",
                )

        redis_conn = _get_redis_client()
        body = metrics_registry.render_prometheus(redis_client=redis_conn)
        return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")

    @app.get("/api/v1/health", tags=["System"])
    def health_check() -> dict[str, Any]:
        """1. Check API, database connection, Redis/RQ queues, and security configuration."""
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            rev_count = conn.execute("SELECT COUNT(*) AS cnt FROM reviews").fetchone()["cnt"]
        demo_mode = os.getenv("DEMO_CACHE_MODE", "true").lower() == "true"
        auth_enabled = bool(os.getenv("ECOMREVIEW_API_KEY", "").strip()) or is_production_env()
        redis_url = os.getenv("REDIS_URL", "").strip()
        redis_conn = _get_redis_client()
        rq_depths: dict[str, int] = {}
        if redis_conn is not None:
            for qname in PRIORITY_QUEUES:
                try:
                    rq_depths[qname] = int(redis_conn.llen(f"rq:queue:{qname}") or 0)
                except Exception:
                    rq_depths[qname] = -1
        queue_backend = "redis_rq" if redis_url else "in_memory"
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
            "components": {
                "database": {"status": "up", "backend": db.backend},
                "redis": {
                    "status": "up"
                    if redis_conn is not None
                    else ("disabled" if not redis_url else "down")
                },
                "rq_queues": rq_depths,
            },
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
        except QuotaExceededError as qe:
            db.log_job_complete(
                job_id,
                status="failed",
                details={"scenario_tag": payload.scenario_tag, "error": qe.detail},
            )
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=qe.detail,
            ) from qe
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

        if async_mode:
            tenant_job_quota.check(scenario_tag)
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
                priority="low" if len(valid_reviews) > 500 else "default",
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
        except QuotaExceededError as qe:
            db.log_job_complete(
                job_id,
                status="failed",
                details={"scenario_tag": scenario_tag, "error": qe.detail},
            )
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=qe.detail,
            ) from qe
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
        if payload.async_mode:
            tenant_job_quota.check(payload.scenario_tag)
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
                priority="default",
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

    # 4. Jobs Audit & Dead-Letter Queue
    @app.get(
        "/api/v1/admin/jobs/dlq",
        tags=["System"],
    )
    def get_admin_jobs_dlq(
        limit: int = Query(default=50, ge=1, le=200),
        principal: AuthPrincipal = Depends(require_roles("admin")),
    ) -> dict[str, Any]:
        """Return recent failed background jobs and Redis Dead-Letter Queue entries."""
        items = list_dlq_entries(db=_get_db(), limit=limit)
        return {"count": len(items), "entries": items}

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

        sku_breakdown = get_sku_variation_stats(scenario_tag=scenario_tag, min_n=1, limit=8, db=db)

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
            "sku_breakdown": sku_breakdown,
        }

    @app.get(
        "/api/v1/stats/sku-breakdown",
        tags=["Analytics"],
    )
    def get_sku_breakdown(
        scenario_tag: str = Query(default="real_shop"),
        platform: str | None = Query(default=None),
        min_n: int = Query(default=2, ge=1, le=1000),
        limit: int = Query(default=20, ge=1, le=100),
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """Return deterministic complaint statistics & Wilson 95% CI grouped by SKU/variation."""
        assert_shop_access(principal, scenario_tag)
        items = get_sku_variation_stats(
            scenario_tag=scenario_tag,
            platform=platform,
            min_n=min_n,
            limit=limit,
            db=_get_db(),
        )
        return {"scenario_tag": scenario_tag, "count": len(items), "items": items}

    @app.get(
        "/api/v1/executive/summary",
        tags=["Agency Executive"],
    )
    def get_executive_summary(
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """Return cross-shop agency command summary strictly scoped to allowed_shops."""
        db = _get_db()
        allowed = None if principal.is_admin else principal.allowed_shops
        shops = db.list_pilot_shops(allowed_slugs=allowed)
        shop_meta = {s["slug"]: {"name": s["name"], "industry": s["industry"]} for s in shops}
        target_slugs = [s["slug"] for s in shops]

        if not target_slugs and principal.is_admin:
            with db.get_connection(read_only=True) as conn:
                rows = conn.execute(
                    "SELECT DISTINCT scenario_tag FROM reviews ORDER BY scenario_tag"
                ).fetchall()
            target_slugs = [str(r["scenario_tag"]) for r in rows]

        for slug in target_slugs:
            assert_shop_access(principal, slug)

        return get_executive_multi_shop_summary(
            shop_slugs=target_slugs,
            shop_meta=shop_meta,
            db=db,
        )

    @app.get("/api/v1/billing/usage", tags=["Billing & Quota"])
    def get_billing_usage(
        scenario_tag: str | None = Query(default=None),
        month_key: str | None = Query(default=None),
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """Return SaaS subscription limits and monthly review/reply usage metering."""
        db = _get_db()
        eff_month = (month_key or current_month_key()).strip()[:7]
        if scenario_tag:
            assert_shop_access(principal, scenario_tag)
            target_slugs = [scenario_tag]
        elif principal.is_admin:
            all_shops = db.list_pilot_shops()
            target_slugs = [s["slug"] for s in all_shops] or ["real_shop"]
        else:
            target_slugs = list(principal.allowed_shops)

        sub = resolve_subscription(db, [*target_slugs, principal.email])
        usage = db.get_monthly_usage(target_slugs, eff_month)
        shops_used = len(
            db.list_pilot_shops(
                allowed_slugs=None if principal.is_admin else principal.allowed_shops
            )
        )
        owner_shops = set(principal.allowed_shops)
        all_users = db.list_users()
        if principal.is_admin:
            users_used = len(all_users)
        else:
            users_used = len(
                [
                    u
                    for u in all_users
                    if str(u["email"]).lower() == principal.email.lower()
                    or (
                        str(u["role"]).lower() == "cskh"
                        and set(u.get("allowed_shops") or []).issubset(owner_shops)
                    )
                ]
            )

        llm_used = int(usage.get("llm_reviews_used") or 0)
        llm_limit = int(sub.get("monthly_llm_review_limit") or 2000)
        llm_pct = round((llm_used / llm_limit) * 100.0, 1) if llm_limit > 0 else 100.0
        return {
            "month_key": eff_month,
            "scoped_shops": target_slugs,
            "subscription": sub,
            "usage": {
                **usage,
                "llm_usage_pct": llm_pct,
                "shops_used": shops_used,
                "users_used": users_used,
                "is_near_limit": llm_pct >= 80.0 and llm_used < llm_limit,
                "is_over_limit": llm_used >= llm_limit,
            },
            "plans": list(PLAN_CATALOG.values()),
        }

    @app.patch("/api/v1/admin/subscriptions/{tenant_key}", tags=["Billing & Quota"])
    def admin_update_subscription(
        tenant_key: str,
        payload: AdminUpdateSubscriptionRequest,
        request: Request,
        principal: AuthPrincipal = Depends(require_roles("admin")),
    ) -> dict[str, Any]:
        """Admin manual plan/quota upgrade endpoint for B2B contracts."""
        plan_code = payload.plan_code.strip().lower()
        if plan_code not in PLAN_CATALOG:
            raise HTTPException(
                status_code=400, detail=f"plan_code must be one of {sorted(PLAN_CATALOG.keys())}"
            )
        sub_status = payload.status.strip().upper()
        if sub_status not in {"TRIAL", "ACTIVE", "SUSPENDED"}:
            raise HTTPException(
                status_code=400, detail="status must be TRIAL, ACTIVE, or SUSPENDED"
            )
        policy = payload.overage_policy.strip().lower()
        if policy not in {"fallback_b1", "block"}:
            raise HTTPException(
                status_code=400, detail="overage_policy must be 'fallback_b1' or 'block'"
            )

        plan_def = PLAN_CATALOG[plan_code]
        db = _get_db()
        updated = db.upsert_tenant_subscription(
            tenant_key=tenant_key,
            plan_code=plan_code,
            status=sub_status,
            monthly_llm_review_limit=(
                payload.monthly_llm_review_limit
                if payload.monthly_llm_review_limit is not None
                else plan_def["monthly_llm_review_limit"]
            ),
            max_shops=(
                payload.max_shops if payload.max_shops is not None else plan_def["max_shops"]
            ),
            max_users=(
                payload.max_users if payload.max_users is not None else plan_def["max_users"]
            ),
            overage_policy=policy,
            notes=payload.notes,
            updated_by=principal.email,
        )
        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="billing.subscription_update",
            scenario_tag=tenant_key,
            target_type="tenant_subscription",
            target_id=tenant_key,
            details={"plan_code": plan_code, "status": sub_status},
        )
        return updated

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
        anomaly_only: bool = Query(default=False),
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
                    if anomaly_only:
                        where_sql += " AND COALESCE(r.anomaly_flags, '[]') NOT IN ('', '[]')"
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
                if anomaly_only:
                    where_sql += " AND COALESCE(r.anomaly_flags, '[]') NOT IN ('', '[]')"
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
                if anomaly_only:
                    where_sql += " AND COALESCE(anomaly_flags, '[]') NOT IN ('', '[]')"
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
                    f"violations, status, created_by, created_at, sent_at, "
                    f"external_sync_status, external_sync_error, external_synced_at "
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
                        "external_sync_status": str(rep["external_sync_status"] or "LOCAL_ONLY"),
                        "external_sync_error": rep["external_sync_error"],
                        "external_synced_at": (
                            str(rep["external_synced_at"]) if rep["external_synced_at"] else None
                        ),
                    }

            reviews_out = []
            for r in rows:
                rid = str(r["review_id"])
                rep_st = reply_status_map.get(rid, "NONE")
                rating_val = int(r["rating"] or 5)
                created_val = str(r["created_at"]) if r["created_at"] else None
                raw_af = r["anomaly_flags"] if "anomaly_flags" in r.keys() else "[]"
                try:
                    af_list = (
                        json.loads(raw_af or "[]") if isinstance(raw_af, str) else list(raw_af)
                    )
                except Exception:
                    af_list = []
                reviews_out.append(
                    {
                        "review_id": rid,
                        "platform": str(r["platform"]),
                        "product": str(r["product"]),
                        "variation": str(r["variation"] or "") if "variation" in r.keys() else "",
                        "anomaly_flags": af_list,
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
        record_reply_usage(db, scenario_tag, count=1)
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
        request: Request,
        background_tasks: BackgroundTasks,
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

        if target_status == "SENT" and payload.push_to_marketplace:
            with db.get_connection(read_only=True) as conn:
                rev_row = conn.execute(
                    "SELECT platform FROM reviews WHERE review_id = ? AND scenario_tag = ?",
                    (existing["review_id"], existing["scenario_tag"]),
                ).fetchone()
            rev_plat = str(rev_row["platform"]).lower() if rev_row else ""
            has_conn = bool(
                rev_plat
                and db.get_marketplace_connection(
                    str(existing["scenario_tag"]), rev_plat, include_tokens=False
                )
            )
            if has_conn and updated.get("external_sync_status") != "PUSHED":
                queued_state = db.update_review_reply_external_sync(reply_id, "QUEUED", None)
                if queued_state:
                    updated["external_sync_status"] = queued_state["external_sync_status"]
                enqueue_background_job(
                    task_push_marketplace_reply,
                    background_tasks,
                    priority="critical",
                    reply_id=reply_id,
                    scenario_tag=str(existing["scenario_tag"]),
                    db_path=resolved_db_path,
                )
                refreshed = db.list_review_replies(
                    str(existing["review_id"]), str(existing["scenario_tag"])
                )
                matched_rep = next((x for x in refreshed if int(x["id"]) == reply_id), None)
                if matched_rep:
                    updated = matched_rep

        if target_status in {"APPROVED", "SENT"}:
            _record_audit(
                request,
                actor=principal.email,
                actor_role=principal.role,
                action=f"reply.{target_status.lower()}",
                scenario_tag=str(existing["scenario_tag"]),
                target_type="review_reply",
                target_id=str(reply_id),
                details={
                    "review_id": str(existing["review_id"]),
                    "external_sync_status": updated.get("external_sync_status", "LOCAL_ONLY"),
                },
            )
        return updated

    @app.post(
        "/api/v1/reviews/replies/{reply_id}/retry-push",
        tags=["Customer Care"],
    )
    def retry_push_reply_to_marketplace(
        reply_id: int,
        request: Request,
        background_tasks: BackgroundTasks,
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """Retry pushing an already approved/sent G1-G6 reply to Shopee or TikTok Shop."""
        db = _get_db()
        with db.get_connection(read_only=True) as conn:
            row = conn.execute(
                """
                SELECT rr.id, rr.review_id, rr.scenario_tag, rr.guardrail_passed,
                       rr.status, rr.external_sync_status, r.platform
                FROM review_replies rr
                JOIN reviews r
                  ON r.review_id = rr.review_id AND r.scenario_tag = rr.scenario_tag
                WHERE rr.id = ?
                """,
                (reply_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Reply {reply_id} not found")
        slug = str(row["scenario_tag"])
        assert_shop_access(principal, slug)
        if not bool(row["guardrail_passed"]):
            raise HTTPException(
                status_code=400,
                detail="Phản hồi chưa đạt quy tắc an toàn G1-G6 nên không thể đẩy lên sàn.",
            )
        plat = str(row["platform"] or "").lower()
        if not db.get_marketplace_connection(slug, plat, include_tokens=False):
            raise HTTPException(
                status_code=400,
                detail=f"Gian hàng '{slug}' chưa kết nối tài khoản '{plat}'.",
            )
        if str(row["external_sync_status"] or "") == "PUSHED":
            return {"id": reply_id, "scenario_tag": slug, "external_sync_status": "PUSHED"}

        db.update_review_reply_external_sync(reply_id, "QUEUED", None)
        enqueue_background_job(
            task_push_marketplace_reply,
            background_tasks,
            priority="critical",
            reply_id=reply_id,
            scenario_tag=slug,
            db_path=resolved_db_path,
        )
        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="reply.retry_push",
            scenario_tag=slug,
            target_type="review_reply",
            target_id=str(reply_id),
        )
        replies = db.list_review_replies(str(row["review_id"]), slug)
        matched = next((x for x in replies if int(x["id"]) == reply_id), None)
        return matched or {"id": reply_id, "scenario_tag": slug, "external_sync_status": "QUEUED"}

    @app.post("/api/v1/reviews/bulk-reply-draft", tags=["Customer Care"])
    def bulk_create_reply_drafts(
        payload: BulkReplyDraftRequest,
        principal: AuthPrincipal = Depends(get_current_principal),
        reviewer: str = Depends(get_current_reviewer),
    ) -> dict[str, Any]:
        """Generate and persist G1-G6 CSKH reply drafts for up to 50 reviews in one call."""
        assert_shop_access(principal, payload.scenario_tag)
        norm_mode = payload.mode.strip().lower()
        if norm_mode not in {"template", "llm"}:
            raise HTTPException(status_code=400, detail="mode must be 'template' or 'llm'")
        db = _get_db()
        results: list[dict[str, Any]] = []
        failed_ids: list[str] = []
        for rid in dict.fromkeys(r.strip() for r in payload.review_ids if r.strip()):
            res = generate_customer_reply(
                review_id=rid,
                scenario_tag=payload.scenario_tag,
                mode=norm_mode,
                db=db,
            )
            if res.get("status") == "error":
                failed_ids.append(rid)
                continue
            gr = res.get("guardrail_report") or {}
            reply_id = db.insert_review_reply(
                review_id=rid,
                scenario_tag=payload.scenario_tag,
                reply_text=str(res["reply_text"]),
                mode_used=str(res.get("mode_used", norm_mode)),
                guardrail_passed=bool(gr.get("passed", True)),
                violations=list(gr.get("violations") or []),
                status="DRAFT",
                created_by=reviewer,
            )
            res["reply_id"] = reply_id
            res["status"] = "DRAFT"
            results.append(res)
        return {
            "scenario_tag": payload.scenario_tag,
            "created_count": len(results),
            "failed_ids": failed_ids,
            "drafts": results,
        }

    @app.post("/api/v1/reviews/replies/bulk-status", tags=["Customer Care"])
    def bulk_update_reply_status(
        payload: BulkReplyStatusRequest,
        request: Request,
        background_tasks: BackgroundTasks,
        principal: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, Any]:
        """Approve or send up to 50 G1-G6 compliant CSKH replies in one batch."""
        assert_shop_access(principal, payload.scenario_tag)
        target_status = payload.status.strip().upper()
        if target_status not in {"APPROVED", "SENT"}:
            raise HTTPException(status_code=400, detail="status must be 'APPROVED' or 'SENT'")

        db = _get_db()
        updated_items: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        unique_ids = list(dict.fromkeys(payload.reply_ids))

        for rid_num in unique_ids:
            with db.get_connection(read_only=True) as conn:
                existing = conn.execute(
                    "SELECT rr.id, rr.review_id, rr.scenario_tag, rr.reply_text, "
                    "rr.guardrail_passed, rr.external_sync_status, r.platform "
                    "FROM review_replies rr "
                    "JOIN reviews r "
                    "ON r.review_id = rr.review_id AND r.scenario_tag = rr.scenario_tag "
                    "WHERE rr.id = ?",
                    (rid_num,),
                ).fetchone()
                if not existing:
                    rejected.append({"reply_id": rid_num, "reason": "not_found"})
                    continue
                if str(existing["scenario_tag"]) != payload.scenario_tag:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Reply {rid_num} does not belong to shop '{payload.scenario_tag}'.",
                    )
                neg_rows = conn.execute(
                    "SELECT DISTINCT aspect FROM opinions "
                    "WHERE review_id = ? AND scenario_tag = ? AND polarity = 'negative'",
                    (existing["review_id"], existing["scenario_tag"]),
                ).fetchall()
                neg_aspects = [str(r["aspect"]) for r in neg_rows]

            recheck = check_reply_guardrails(
                reply_text=str(existing["reply_text"] or ""),
                negative_aspects=neg_aspects,
            )
            if not bool(existing["guardrail_passed"]) or not recheck.passed:
                rejected.append(
                    {
                        "reply_id": rid_num,
                        "reason": "; ".join(recheck.violations) or "G1-G6 failed",
                    }
                )
                continue

            upd = db.update_review_reply_status(reply_id=rid_num, status=target_status)
            if not upd:
                rejected.append({"reply_id": rid_num, "reason": "update_failed"})
                continue

            if target_status == "SENT" and payload.push_to_marketplace:
                rev_plat = str(existing["platform"] or "").lower()
                has_conn = bool(
                    rev_plat
                    and db.get_marketplace_connection(
                        payload.scenario_tag, rev_plat, include_tokens=False
                    )
                )
                if has_conn and upd.get("external_sync_status") != "PUSHED":
                    db.update_review_reply_external_sync(rid_num, "QUEUED", None)
                    upd["external_sync_status"] = "QUEUED"
                    enqueue_background_job(
                        task_push_marketplace_reply,
                        background_tasks,
                        priority="critical",
                        reply_id=rid_num,
                        scenario_tag=payload.scenario_tag,
                        db_path=resolved_db_path,
                    )
            updated_items.append(upd)

        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action=f"reply.bulk_{target_status.lower()}",
            scenario_tag=payload.scenario_tag,
            target_type="review_reply",
            details={"updated_count": len(updated_items), "rejected_count": len(rejected)},
        )
        return {
            "scenario_tag": payload.scenario_tag,
            "updated_count": len(updated_items),
            "rejected_count": len(rejected),
            "updated": updated_items,
            "rejected": rejected,
        }

    @app.post("/api/v1/reviews/auto-reply-5star", tags=["Customer Care"])
    def trigger_auto_reply_5star(
        payload: AutoReply5StarRequest,
        request: Request,
        background_tasks: BackgroundTasks,
        principal: AuthPrincipal = Depends(require_roles("admin", "owner")),
    ) -> dict[str, Any]:
        """Auto-reply clean 5-star reviews passing G1-G6 and optionally push to marketplace."""
        assert_shop_access(principal, payload.scenario_tag)
        db = _get_db()
        res = auto_reply_eligible_five_star_reviews(
            db=db,
            scenario_tag=payload.scenario_tag,
            review_ids=payload.review_ids,
            limit=payload.limit,
            actor=principal.email,
        )
        queued_push = 0
        if payload.push_to_marketplace and res.get("created_reply_ids"):
            conns = db.list_marketplace_connections(
                scenario_tag=payload.scenario_tag, include_tokens=False
            )
            connected_plats = {c["platform"] for c in conns}
            if connected_plats:
                for rep_id in res["created_reply_ids"]:
                    with db.get_connection(read_only=True) as conn:
                        rrow = conn.execute(
                            "SELECT r.platform FROM review_replies rr "
                            "JOIN reviews r "
                            "ON r.review_id = rr.review_id AND r.scenario_tag = rr.scenario_tag "
                            "WHERE rr.id = ?",
                            (rep_id,),
                        ).fetchone()
                    if rrow and str(rrow["platform"]).lower() in connected_plats:
                        db.update_review_reply_external_sync(rep_id, "QUEUED", None)
                        enqueue_background_job(
                            task_push_marketplace_reply,
                            background_tasks,
                            priority="critical",
                            reply_id=rep_id,
                            scenario_tag=payload.scenario_tag,
                            db_path=resolved_db_path,
                        )
                        queued_push += 1

        _record_audit(
            request,
            actor=principal.email,
            actor_role=principal.role,
            action="reply.auto_5star",
            scenario_tag=payload.scenario_tag,
            target_type="review_reply",
            details={
                "replied_count": res["replied_count"],
                "skipped_count": res["skipped_count"],
                "queued_push": queued_push,
            },
        )
        return {**res, "queued_push_count": queued_push}

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
        request: Request,
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
            _record_audit(
                request,
                actor=principal.email,
                actor_role=principal.role,
                action="report.export",
                scenario_tag=scenario_tag,
                target_type="report",
                target_id=fmt,
            )
            filename = f"EcomReview_Report_{safe_tag}.xlsx"
            return Response(
                content=xlsx_bytes,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        if fmt in ("html", "htm"):
            html_text = build_html_report(scenario_tag=scenario_tag, db=db)
            _record_audit(
                request,
                actor=principal.email,
                actor_role=principal.role,
                action="report.export",
                scenario_tag=scenario_tag,
                target_type="report",
                target_id=fmt,
            )
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
