"""Marketplace connector factory and automatic OAuth token refresh helper."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from ecomreview.connectors.base import BasePlatformConnector
from ecomreview.connectors.shopee import ShopeeConnector
from ecomreview.connectors.tiktok import TikTokShopConnector
from ecomreview.db.database import DatabaseManager

logger = logging.getLogger(__name__)

SUPPORTED_PLATFORMS: tuple[str, ...] = ("shopee", "tiktok")


def get_connector_class(platform: str) -> type[BasePlatformConnector]:
    """Resolve connector class for a supported marketplace platform."""
    norm = (platform or "").strip().lower()
    if norm == "shopee":
        return ShopeeConnector
    if norm == "tiktok":
        return TikTokShopConnector
    raise ValueError(f"Unsupported marketplace platform '{platform}'. Choose from shopee/tiktok.")


def build_connector_from_connection(conn: dict[str, Any]) -> BasePlatformConnector:
    """Instantiate a platform connector using decrypted shop connection credentials."""
    cls = get_connector_class(str(conn.get("platform") or ""))
    return cls.from_connection(conn)  # type: ignore[attr-defined]


def _is_expiring_soon(expires_at: str | None, margin_seconds: int) -> bool:
    if not expires_at:
        return False
    try:
        dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt <= datetime.now(timezone.utc) + timedelta(seconds=margin_seconds)
    except ValueError:
        return False


def ensure_fresh_connector(
    db: DatabaseManager,
    conn: dict[str, Any],
    refresh_margin_seconds: int = 900,
) -> BasePlatformConnector:
    """Return a ready connector, refreshing & persisting OAuth token when expiring soon."""
    connector = build_connector_from_connection(conn)
    refresh_tok = str(conn.get("refresh_token") or "").strip()
    if refresh_tok and _is_expiring_soon(conn.get("token_expires_at"), refresh_margin_seconds):
        try:
            refreshed = connector.refresh_access_token(refresh_tok)  # type: ignore[attr-defined]
            new_access = str(refreshed.get("access_token") or "").strip()
            new_refresh = str(refreshed.get("refresh_token") or refresh_tok).strip()
            expires_in = int(refreshed.get("expires_in") or 14400)
            new_exp_iso = (
                datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in))
            ).isoformat()
            if new_access:
                db.upsert_marketplace_connection(
                    scenario_tag=str(conn["scenario_tag"]),
                    platform=str(conn["platform"]),
                    external_shop_id=str(
                        refreshed.get("external_shop_id") or conn["external_shop_id"]
                    ),
                    access_token=new_access,
                    refresh_token=new_refresh,
                    token_expires_at=new_exp_iso,
                    shop_name=str(conn.get("shop_name") or ""),
                    auto_sync_enabled=bool(conn.get("auto_sync_enabled", True)),
                    sync_interval_minutes=int(conn.get("sync_interval_minutes") or 30),
                )
                updated_conn = {
                    **conn,
                    "access_token": new_access,
                    "refresh_token": new_refresh,
                    "token_expires_at": new_exp_iso,
                }
                connector = build_connector_from_connection(updated_conn)
        except Exception as exc:
            logger.warning(
                "Marketplace token auto-refresh failed for %s/%s: %s",
                conn.get("scenario_tag"),
                conn.get("platform"),
                exc,
            )
    return connector


# CreBy: MenBoyBMN
