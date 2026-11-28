"""SaaS subscription plans, usage metering, and soft-quota fallback enforcement."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from ecomreview.db.database import DatabaseManager

logger = logging.getLogger(__name__)

PLAN_CATALOG: dict[str, dict[str, Any]] = {
    "trial": {
        "plan_code": "trial",
        "display_name": "Dùng thử 14 ngày",
        "monthly_llm_review_limit": 500,
        "max_shops": 2,
        "max_users": 2,
        "price_vnd_month": 0,
    },
    "basic": {
        "plan_code": "basic",
        "display_name": "Gói Basic (SME)",
        "monthly_llm_review_limit": 2000,
        "max_shops": 2,
        "max_users": 3,
        "price_vnd_month": 499000,
    },
    "pro": {
        "plan_code": "pro",
        "display_name": "Gói Pro (Tăng trưởng)",
        "monthly_llm_review_limit": 10000,
        "max_shops": 5,
        "max_users": 10,
        "price_vnd_month": 1490000,
    },
    "agency": {
        "plan_code": "agency",
        "display_name": "Gói Agency (Chuỗi đa shop)",
        "monthly_llm_review_limit": 50000,
        "max_shops": 30,
        "max_users": 40,
        "price_vnd_month": 3990000,
    },
}


class QuotaExceededError(Exception):
    """Raised when a tenant hits a hard quota limit (overage_policy='block' or SUSPENDED)."""

    def __init__(self, detail: str, quota_info: dict[str, Any] | None = None):
        super().__init__(detail)
        self.detail = detail
        self.quota_info = quota_info or {}


def current_month_key(now_utc: datetime | None = None) -> str:
    """Return canonical UTC YYYY-MM billing month key."""
    dt = now_utc or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m")


def resolve_subscription(db: DatabaseManager, tenant_keys: Sequence[str]) -> dict[str, Any]:
    """Resolve persisted tenant subscription across priority keys, else default Basic."""
    for key in tenant_keys:
        clean = str(key or "").strip().lower()
        if not clean or clean == "*":
            continue
        sub = db.get_tenant_subscription(clean)
        if sub:
            return {**sub, "persisted": True}

    default_plan = PLAN_CATALOG["basic"]
    return {
        "tenant_key": str(tenant_keys[0]) if tenant_keys else "default",
        "plan_code": "basic",
        "display_name": default_plan["display_name"],
        "status": "ACTIVE",
        "monthly_llm_review_limit": default_plan["monthly_llm_review_limit"],
        "max_shops": default_plan["max_shops"],
        "max_users": default_plan["max_users"],
        "overage_policy": "fallback_b1",
        "trial_ends_at": None,
        "notes": None,
        "persisted": False,
    }


def check_and_resolve_analyzer_for_quota(
    db: DatabaseManager,
    scenario_tag: str,
    requested_method: str,
    batch_size: int = 0,
) -> tuple[str, bool, dict[str, Any]]:
    """Enforce monthly LLM review quota; fallback softly to b1_rule unless policy='block'."""
    if not str(requested_method or "").startswith("a1"):
        return requested_method, False, {"quota_checked": False}

    month_key = current_month_key()
    sub = resolve_subscription(db, [scenario_tag])
    usage = db.get_monthly_usage([scenario_tag], month_key)
    used_llm = int(usage.get("llm_reviews_used") or 0)
    limit = int(sub.get("monthly_llm_review_limit") or 2000)
    sub_status = str(sub.get("status") or "ACTIVE").upper()
    policy = str(sub.get("overage_policy") or "fallback_b1").lower()

    info = {
        "quota_checked": True,
        "month_key": month_key,
        "plan_code": sub["plan_code"],
        "llm_reviews_used": used_llm,
        "monthly_llm_review_limit": limit,
        "overage_policy": policy,
        "status": sub_status,
        "batch_size": batch_size,
    }

    if sub_status == "SUSPENDED":
        if policy == "block":
            raise QuotaExceededError(
                "Gói dịch vụ của gian hàng đang bị tạm ngưng. Vui lòng liên hệ quản trị viên.",
                quota_info=info,
            )
        return "b1_rule", True, info

    if used_llm >= limit:
        if policy == "block":
            raise QuotaExceededError(
                f"Gian hàng '{scenario_tag}' đã hết hạn mức {limit} đánh giá LLM trong tháng "
                f"{month_key}. Vui lòng nâng cấp gói cước để tiếp tục dùng AI.",
                quota_info=info,
            )
        return "b1_rule", True, info

    return requested_method, False, info


def record_batch_usage(
    db: DatabaseManager,
    scenario_tag: str,
    *,
    llm_count: int = 0,
    rule_count: int = 0,
    month_key: str | None = None,
) -> dict[str, Any] | None:
    """Persist review ingestion usage safely without crashing callers if tables lag."""
    if llm_count <= 0 and rule_count <= 0:
        return None
    try:
        return db.increment_monthly_usage(
            scenario_tag=scenario_tag,
            month_key=month_key or current_month_key(),
            llm_reviews=max(0, int(llm_count)),
            rule_reviews=max(0, int(rule_count)),
        )
    except Exception as exc:
        logger.debug("Skipping monthly usage increment for %s: %s", scenario_tag, exc)
        return None


def record_reply_usage(
    db: DatabaseManager,
    scenario_tag: str,
    count: int = 1,
    month_key: str | None = None,
) -> dict[str, Any] | None:
    """Increment monthly CSKH reply draft counter safely."""
    if count <= 0:
        return None
    try:
        return db.increment_monthly_usage(
            scenario_tag=scenario_tag,
            month_key=month_key or current_month_key(),
            replies_generated=int(count),
        )
    except Exception as exc:
        logger.debug("Skipping reply usage increment for %s: %s", scenario_tag, exc)
        return None


# CreBy: MenBoyBMN
