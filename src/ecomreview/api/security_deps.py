"""API Security, JWT/Cookie Authentication, RBAC, and Shop Isolation dependencies."""

from __future__ import annotations

import logging
import os
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field

import jwt
from fastapi import Depends, Header, HTTPException, Request, status

from ecomreview.api.auth import (
    SESSION_COOKIE_NAME,
    decode_access_token,
    is_production_env,
)

logger = logging.getLogger(__name__)

VALID_ROLES = {"admin", "owner", "cskh"}


@dataclass(frozen=True)
class AuthPrincipal:
    """Represents the authenticated caller (human user via JWT or machine via API key)."""

    user_id: int | None
    email: str
    full_name: str
    role: str
    allowed_shops: list[str] = field(default_factory=list)
    auth_type: str = "dev_bypass"  # 'jwt' | 'api_key' | 'dev_bypass'

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def can_access_shop(self, scenario_tag: str) -> bool:
        if self.is_admin or "*" in self.allowed_shops:
            return True
        return scenario_tag in self.allowed_shops


def _sanitize_reviewer_name(raw_name: str | None) -> str:
    """Strip control chars and spreadsheet formula prefixes from reviewer names."""
    if raw_name and raw_name.strip():
        clean = "".join(c for c in raw_name.strip() if c.isprintable() and c not in "\r\n\t")
        clean = clean.lstrip("=+@-")
        return (clean or "shop_owner")[:64]
    return "shop_owner"


def _extract_bearer_or_cookie_token(request: Request) -> str | None:
    """Extract JWT token from Authorization Bearer header or HttpOnly session cookie."""
    auth_header = request.headers.get("authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        tok = auth_header[7:].strip()
        if tok:
            return tok
    cookie_tok = request.cookies.get(SESSION_COOKIE_NAME, "").strip()
    return cookie_tok or None


def get_current_principal(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_reviewer: str | None = Header(default=None, alias="X-Reviewer"),
) -> AuthPrincipal:
    """Authenticate caller via JWT (Bearer/Cookie) or X-API-Key.

    In production (ECOMREVIEW_ENV=production), authentication is strictly fail-closed.
    In development/testing when ECOMREVIEW_API_KEY is unset and no JWT is provided,
    dev bypass preserves backward compatibility with existing unit/API tests.
    """
    cached = getattr(request.state, "principal", None)
    if isinstance(cached, AuthPrincipal):
        return cached

    # 1. Try JWT from Bearer header or HttpOnly Cookie
    token = _extract_bearer_or_cookie_token(request)
    if token:
        try:
            claims = decode_access_token(token)
        except jwt.ExpiredSignatureError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.",
            ) from exc
        except jwt.InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token xác thực không hợp lệ.",
            ) from exc

        role = str(claims.get("role", "cskh")).lower()
        if role not in VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Vai trò tài khoản không hợp lệ.",
            )
        principal = AuthPrincipal(
            user_id=int(claims["sub"]) if str(claims.get("sub", "")).isdigit() else None,
            email=str(claims["email"]),
            full_name=str(claims.get("name") or claims["email"]),
            role=role,
            allowed_shops=[str(s) for s in (claims.get("allowed_shops") or [])],
            auth_type="jwt",
        )
        request.state.principal = principal
        return principal

    # 2. Try X-API-Key (machine-to-machine, scripts, or legacy client)
    expected_key = os.getenv("ECOMREVIEW_API_KEY", "").strip()
    if expected_key:
        if x_api_key and secrets.compare_digest(x_api_key.strip(), expected_key):
            reviewer = _sanitize_reviewer_name(x_reviewer)
            principal = AuthPrincipal(
                user_id=None,
                email=reviewer,
                full_name=reviewer,
                role="admin",
                allowed_shops=["*"],
                auth_type="api_key",
            )
            request.state.principal = principal
            return principal
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header.",
        )

    # 3. Production fail-closed guard
    if is_production_env():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Vui lòng đăng nhập để truy cập hệ thống.",
        )

    # 4. Development / Test bypass when ECOMREVIEW_API_KEY is empty and not production
    reviewer = _sanitize_reviewer_name(x_reviewer)
    principal = AuthPrincipal(
        user_id=None,
        email=reviewer,
        full_name=reviewer,
        role="admin",
        allowed_shops=["*"],
        auth_type="dev_bypass",
    )
    request.state.principal = principal
    return principal


def require_api_key(
    principal: AuthPrincipal = Depends(get_current_principal),
) -> AuthPrincipal:
    """Backward-compatible dependency enforcing authentication (JWT or X-API-Key)."""
    return principal


def require_roles(*allowed_roles: str) -> Callable[..., AuthPrincipal]:
    """Dependency factory enforcing Role-Based Access Control (RBAC)."""
    allowed = {r.strip().lower() for r in allowed_roles}

    def _checker(principal: AuthPrincipal = Depends(get_current_principal)) -> AuthPrincipal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Tài khoản vai trò '{principal.role}' không có quyền thực hiện thao tác này."
                ),
            )
        return principal

    return _checker


def assert_shop_access(principal: AuthPrincipal, scenario_tag: str) -> None:
    """Enforce per-shop tenant isolation to prevent cross-shop IDOR access."""
    if not principal.can_access_shop(scenario_tag):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Bạn không có quyền truy cập dữ liệu gian hàng '{scenario_tag}'.",
        )


def get_current_reviewer(
    request: Request,
    x_reviewer: str | None = Header(default=None, alias="X-Reviewer"),
) -> str:
    """Return authenticated reviewer identity (JWT email takes precedence over X-Reviewer)."""
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, AuthPrincipal) and principal.auth_type == "jwt":
        return _sanitize_reviewer_name(principal.email)
    return _sanitize_reviewer_name(x_reviewer)


# CreBy: MenBoyBMN
