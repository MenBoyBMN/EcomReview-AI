"""TikTok Shop Partner API connector (HMAC-SHA256 signing ready for Partner App)."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from ecomreview.connectors.base import BasePlatformConnector


class TikTokShopConnector(BasePlatformConnector):
    """Two-way connector for TikTok Shop Partner API review ingestion & reply."""

    platform_name = "tiktok"

    def __init__(
        self,
        app_key: str | None = None,
        app_secret: str | None = None,
        shop_cipher: str | None = None,
        access_token: str | None = None,
        base_url: str | None = None,
        auth_base_url: str | None = None,
        token_base_url: str | None = None,
    ) -> None:
        self.app_key = (app_key or os.getenv("TIKTOK_APP_KEY", "")).strip()
        self.app_secret = (app_secret or os.getenv("TIKTOK_APP_SECRET", "")).strip()
        self.shop_cipher = (shop_cipher or os.getenv("TIKTOK_SHOP_CIPHER", "")).strip()
        self.access_token = (access_token or os.getenv("TIKTOK_ACCESS_TOKEN", "")).strip()
        self.base_url = (
            base_url or os.getenv("TIKTOK_API_BASE_URL", "https://open-api.tiktokglobalshop.com")
        ).rstrip("/")
        self.auth_base_url = (
            auth_base_url
            or os.getenv("TIKTOK_AUTH_BASE_URL", "https://services.tiktokshop.com/open/authorize")
        ).rstrip("/")
        self.token_base_url = (
            token_base_url or os.getenv("TIKTOK_TOKEN_BASE_URL", "https://auth.tiktok-shops.com")
        ).rstrip("/")

    @classmethod
    def from_connection(cls, conn: dict[str, Any]) -> TikTokShopConnector:
        """Instantiate connector from an encrypted shop_marketplace_connections record."""
        return cls(
            shop_cipher=str(conn.get("external_shop_id") or ""),
            access_token=str(conn.get("access_token") or ""),
        )

    def is_configured(self) -> bool:
        return bool(self.app_key and self.app_secret and self.shop_cipher and self.access_token)

    def build_auth_url(self, redirect_url: str, state: str = "") -> str:
        """Build TikTok Shop Partner OAuth authorization URL."""
        if not self.app_key:
            raise RuntimeError("TIKTOK_APP_KEY is required for TikTok Shop OAuth.")
        params = {
            "app_key": self.app_key,
            "redirect_uri": redirect_url.strip(),
        }
        if state:
            params["state"] = state
        return f"{self.auth_base_url}?{urlencode(params)}"

    def exchange_code_for_token(self, code: str, shop_cipher: str = "") -> dict[str, Any]:
        """Exchange TikTok Shop OAuth auth code for access_token & refresh_token."""
        if not self.app_key or not self.app_secret:
            raise RuntimeError("TIKTOK_APP_KEY and TIKTOK_APP_SECRET are required for OAuth.")
        params = {
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "auth_code": code.strip(),
            "grant_type": "authorized_code",
        }
        resp = requests.get(
            f"{self.token_base_url}/api/v2/token/get",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        if int(body.get("code", 0) or 0) != 0:
            raise RuntimeError(f"TikTok OAuth error: {body.get('message') or body.get('code')}")
        data = body.get("data") or {}
        now_ts = int(time.time())
        exp_in = max(300, int(data.get("access_token_expire_in") or (now_ts + 7 * 86400)) - now_ts)
        return {
            "external_shop_id": str(shop_cipher or data.get("open_id") or "tiktok_shop"),
            "shop_name": str(data.get("seller_name") or ""),
            "access_token": str(data.get("access_token") or ""),
            "refresh_token": str(data.get("refresh_token") or ""),
            "expires_in": exp_in,
        }

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh an expiring TikTok Shop access_token using refresh_token."""
        if not self.app_key or not self.app_secret:
            raise RuntimeError("TIKTOK_APP_KEY and TIKTOK_APP_SECRET are required for OAuth.")
        params = {
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "refresh_token": refresh_token.strip(),
            "grant_type": "refresh_token",
        }
        resp = requests.get(
            f"{self.token_base_url}/api/v2/token/refresh",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        if int(body.get("code", 0) or 0) != 0:
            raise RuntimeError(f"TikTok refresh error: {body.get('message') or body.get('code')}")
        data = body.get("data") or {}
        now_ts = int(time.time())
        exp_in = max(300, int(data.get("access_token_expire_in") or (now_ts + 7 * 86400)) - now_ts)
        return {
            "external_shop_id": self.shop_cipher,
            "access_token": str(data.get("access_token") or ""),
            "refresh_token": str(data.get("refresh_token") or refresh_token),
            "expires_in": exp_in,
        }

    def sign_request(self, api_path: str, params: dict[str, Any], body: str = "") -> str:
        """Generate TikTok Shop Partner API HMAC-SHA256 signature."""
        filtered = sorted(
            (k, str(v)) for k, v in params.items() if k not in {"sign", "access_token"}
        )
        concat = "".join(f"{k}{v}" for k, v in filtered)
        sign_input = f"{self.app_secret}{api_path}{concat}{body}{self.app_secret}"
        return hmac.new(
            self.app_secret.encode("utf-8"),
            sign_input.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def fetch_reviews(
        self, since: datetime | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("TikTok Shop Partner API credentials are not configured.")
        api_path = "/product/202309/reviews"
        params = {
            "app_key": self.app_key,
            "timestamp": str(int(time.time())),
            "shop_cipher": self.shop_cipher,
            "page_size": str(min(100, max(1, limit))),
        }
        params["sign"] = self.sign_request(api_path, params)
        headers = {"x-tts-access-token": self.access_token}
        resp = requests.get(
            f"{self.base_url}{api_path}", params=params, headers=headers, timeout=15
        )
        resp.raise_for_status()
        items = (resp.json().get("data") or {}).get("reviews") or []
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
                    "review_id": f"ttk_{c.get('review_id')}",
                    "platform": "tiktok",
                    "shop": f"tiktok_{self.shop_cipher[:8]}",
                    "product": str(c.get("product_id") or "tiktok_sku"),
                    "rating": int(c.get("rating") or 5),
                    "text": str(c.get("text") or "").strip(),
                    "created_at": created_dt.strftime("%Y-%m-%d") if created_dt else None,
                    "source": "tiktok_api",
                }
            )
        return results

    def post_reply(self, external_review_id: str, reply_text: str) -> dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("TikTok Shop Partner API credentials are not configured.")
        clean_id = external_review_id.removeprefix("ttk_")
        api_path = f"/product/202309/reviews/{clean_id}/reply"
        params = {
            "app_key": self.app_key,
            "timestamp": str(int(time.time())),
            "shop_cipher": self.shop_cipher,
        }
        import json

        body_str = json.dumps({"reply_text": reply_text}, ensure_ascii=False)
        params["sign"] = self.sign_request(api_path, params, body=body_str)
        headers = {
            "x-tts-access-token": self.access_token,
            "Content-Type": "application/json",
        }
        resp = requests.post(
            f"{self.base_url}{api_path}",
            params=params,
            headers=headers,
            data=body_str.encode("utf-8"),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


# CreBy: MenBoyBMN
