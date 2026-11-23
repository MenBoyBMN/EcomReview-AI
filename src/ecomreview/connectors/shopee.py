"""Shopee Open Platform v2 connector (HMAC-SHA256 request signing ready for Partner App)."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import datetime
from typing import Any

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

    def is_configured(self) -> bool:
        return bool(self.partner_id and self.partner_key and self.shop_id and self.access_token)

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
        for c in items:
            create_ts = int(c.get("create_time") or 0)
            created_dt = datetime.fromtimestamp(create_ts) if create_ts else None
            if since and created_dt and created_dt < since:
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
