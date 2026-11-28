"""Shopee Open Platform v2 connector (HMAC-SHA256 request signing ready for Partner App)."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

from ecomreview.connectors.base import BasePlatformConnector


class ShopeeConnector(BasePlatformConnector):
    """Two-way connector for Shopee Open Platform v2 review & reply endpoints."""

    platform_name = "shopee"

    def __init__(
        self,
        partner_id: str | None = None,
        partner_key: str | None = None,
        shop_id: str | None = None,
        access_token: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.partner_id = (partner_id or os.getenv("SHOPEE_PARTNER_ID", "")).strip()
        self.partner_key = (partner_key or os.getenv("SHOPEE_PARTNER_KEY", "")).strip()
        self.shop_id = (shop_id or os.getenv("SHOPEE_SHOP_ID", "")).strip()
        self.access_token = (access_token or os.getenv("SHOPEE_ACCESS_TOKEN", "")).strip()
        self.base_url = (
            base_url or os.getenv("SHOPEE_API_BASE_URL", "https://partner.shopeemobile.com")
        ).rstrip("/")

    @classmethod
    def from_connection(cls, conn: dict[str, Any]) -> ShopeeConnector:
        """Instantiate connector from an encrypted shop_marketplace_connections record."""
        return cls(
            shop_id=str(conn.get("external_shop_id") or ""),
            access_token=str(conn.get("access_token") or ""),
        )

    def is_configured(self) -> bool:
        return bool(self.partner_id and self.partner_key and self.shop_id and self.access_token)

    def sign_public_request(self, api_path: str, timestamp: int) -> str:
        """Generate Shopee v2 public/auth HMAC-SHA256 signature (partner_id + path + ts)."""
        base_str = f"{self.partner_id}{api_path}{timestamp}"
        return hmac.new(
            self.partner_key.encode("utf-8"),
            base_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def build_auth_url(self, redirect_url: str, state: str = "") -> str:
        """Build Shopee Open Platform partner authorization URL."""
        if not self.partner_id or not self.partner_key:
            raise RuntimeError("SHOPEE_PARTNER_ID and SHOPEE_PARTNER_KEY are required for OAuth.")
        final_redirect = redirect_url.strip()
        if state:
            parsed = urlparse(final_redirect)
            qs = dict(parse_qsl(parsed.query))
            qs["state"] = state
            final_redirect = urlunparse(parsed._replace(query=urlencode(qs)))
        api_path = "/api/v2/shop/auth_partner"
        ts = int(time.time())
        sign = self.sign_public_request(api_path, ts)
        query = urlencode(
            {
                "partner_id": int(self.partner_id),
                "timestamp": ts,
                "sign": sign,
                "redirect": final_redirect,
            }
        )
        return f"{self.base_url}{api_path}?{query}"

    def exchange_code_for_token(self, code: str, shop_id: str) -> dict[str, Any]:
        """Exchange Shopee OAuth authorization code for access_token & refresh_token."""
        if not self.partner_id or not self.partner_key:
            raise RuntimeError("SHOPEE_PARTNER_ID and SHOPEE_PARTNER_KEY are required for OAuth.")
        api_path = "/api/v2/auth/token/get"
        ts = int(time.time())
        params = {
            "partner_id": int(self.partner_id),
            "timestamp": ts,
            "sign": self.sign_public_request(api_path, ts),
        }
        body = {
            "code": code.strip(),
            "shop_id": int(shop_id) if str(shop_id).isdigit() else shop_id,
            "partner_id": int(self.partner_id),
        }
        resp = requests.post(f"{self.base_url}{api_path}", params=params, json=body, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"Shopee OAuth error: {data.get('message') or data.get('error')}")
        return {
            "external_shop_id": str(shop_id),
            "access_token": str(data.get("access_token") or ""),
            "refresh_token": str(data.get("refresh_token") or ""),
            "expires_in": int(data.get("expire_in") or 14400),
            "refresh_expires_in": int(data.get("refresh_expire_in") or 30 * 86400),
        }

    def refresh_access_token(
        self, refresh_token: str, shop_id: str | None = None
    ) -> dict[str, Any]:
        """Refresh an expiring Shopee access_token using refresh_token."""
        if not self.partner_id or not self.partner_key:
            raise RuntimeError("SHOPEE_PARTNER_ID and SHOPEE_PARTNER_KEY are required for OAuth.")
        target_shop = (shop_id or self.shop_id).strip()
        api_path = "/api/v2/auth/access_token/get"
        ts = int(time.time())
        params = {
            "partner_id": int(self.partner_id),
            "timestamp": ts,
            "sign": self.sign_public_request(api_path, ts),
        }
        body = {
            "refresh_token": refresh_token.strip(),
            "partner_id": int(self.partner_id),
            "shop_id": int(target_shop) if target_shop.isdigit() else target_shop,
        }
        resp = requests.post(f"{self.base_url}{api_path}", params=params, json=body, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"Shopee refresh error: {data.get('message') or data.get('error')}")
        return {
            "external_shop_id": str(data.get("shop_id") or target_shop),
            "access_token": str(data.get("access_token") or ""),
            "refresh_token": str(data.get("refresh_token") or refresh_token),
            "expires_in": int(data.get("expire_in") or 14400),
        }

    def sign_request(self, api_path: str, timestamp: int) -> str:
        """Generate Shopee Open Platform v2 HMAC-SHA256 signature."""
        base_str = f"{self.partner_id}{api_path}{timestamp}{self.access_token}{self.shop_id}"
        return hmac.new(
            self.partner_key.encode("utf-8"),
            base_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _auth_params(self, api_path: str) -> dict[str, Any]:
        ts = int(time.time())
        return {
            "partner_id": int(self.partner_id),
            "timestamp": ts,
            "access_token": self.access_token,
            "shop_id": int(self.shop_id),
            "sign": self.sign_request(api_path, ts),
        }

    def fetch_reviews(
        self, since: datetime | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("Shopee Partner API credentials are not configured.")
        api_path = "/api/v2/product/get_comment"
        params = {**self._auth_params(api_path), "page_size": min(100, max(1, limit))}
        resp = requests.get(f"{self.base_url}{api_path}", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("response", {})
        items = data.get("item_comment_list") or []
        results: list[dict[str, Any]] = []
        since_cmp = (
            since
            if (since is None or since.tzinfo is not None)
            else since.replace(tzinfo=timezone.utc)
        )
        for c in items:
            create_ts = int(c.get("create_time") or 0)
            created_dt = datetime.fromtimestamp(create_ts, tz=timezone.utc) if create_ts else None
            if since_cmp and created_dt and created_dt < since_cmp:
                continue
            results.append(
                {
                    "review_id": f"shp_{c.get('comment_id')}",
                    "platform": "shopee",
                    "shop": f"shopee_{self.shop_id}",
                    "product": str(c.get("item_id") or "shopee_sku"),
                    "rating": int(c.get("rating_star") or 5),
                    "text": str(c.get("comment") or "").strip(),
                    "created_at": created_dt.strftime("%Y-%m-%d") if created_dt else None,
                    "source": "shopee_api",
                }
            )
        return results

    def post_reply(self, external_review_id: str, reply_text: str) -> dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("Shopee Partner API credentials are not configured.")
        api_path = "/api/v2/product/reply_comment"
        clean_id = external_review_id.removeprefix("shp_")
        params = self._auth_params(api_path)
        payload = {
            "comment_list": [
                {
                    "comment_id": int(clean_id) if clean_id.isdigit() else clean_id,
                    "comment": reply_text,
                }
            ]
        }
        resp = requests.post(
            f"{self.base_url}{api_path}",
            params=params,
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


# CreBy: MenBoyBMN
