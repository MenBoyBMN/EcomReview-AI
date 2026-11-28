"""Tests for Shopee/TikTok OAuth 2.0 per-shop connections, encryption, and token refresh."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from alembic import command
from ecomreview.api.auth import hash_password
from ecomreview.api.main import create_app
from ecomreview.api.rate_limit import account_lockout, rate_limiter
from ecomreview.connectors.factory import ensure_fresh_connector
from ecomreview.crypto import ENCRYPTED_PREFIX
from ecomreview.db.database import DatabaseManager


def _setup_oauth_app(tmp_path: Path, monkeypatch):
    rate_limiter.reset()
    account_lockout.reset()
    monkeypatch.setenv("ECOMREVIEW_ENV", "production")
    monkeypatch.setenv("ECOMREVIEW_JWT_SECRET", "super-strong-pilot-jwt-secret-key-32bytes")
    monkeypatch.setenv("ECOMREVIEW_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("ECOMREVIEW_CORS_ORIGINS", "https://pilot.ecomreview.vn")
    monkeypatch.setenv("ECOMREVIEW_TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.setenv("ECOMREVIEW_QUEUE_DISABLE", "true")
    monkeypatch.setenv("SHOPEE_PARTNER_ID", "100888")
    monkeypatch.setenv("SHOPEE_PARTNER_KEY", "shopee_partner_secret_key")
    monkeypatch.setenv("TIKTOK_APP_KEY", "ttk_app_key_123")
    monkeypatch.setenv("TIKTOK_APP_SECRET", "ttk_app_secret_456")
    monkeypatch.delenv("ECOMREVIEW_API_KEY", raising=False)

    db_file = tmp_path / "oauth_shops.db"
    db = DatabaseManager(db_path=str(db_file), db_backend="sqlite")
    db.create_pilot_shop(slug="shop_alpha", name="Shop Alpha")
    db.upsert_user(
        email="owner@alpha.vn",
        password_hash=hash_password("OwnerPass123!"),
        full_name="Owner Alpha",
        role="owner",
        allowed_shops=["shop_alpha"],
    )
    app = create_app(db_path=str(db_file))
    return app, db, db_file


class TestMarketplaceOAuth:
    def test_alembic_0004_creates_marketplace_table_and_reply_sync_columns(
        self, tmp_path, monkeypatch
    ):
        db_file = tmp_path / "alembic_0004.db"
        monkeypatch.setenv("ECOMREVIEW_DB_BACKEND", "sqlite")
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")

        repo_root = Path(__file__).resolve().parents[1]
        cfg = Config(str(repo_root / "alembic.ini"))
        cfg.set_main_option("script_location", str(repo_root / "alembic"))
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file.as_posix()}")
        command.upgrade(cfg, "head")

        with sqlite3.connect(db_file) as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            reply_cols = {
                r[1] for r in conn.execute("PRAGMA table_info(review_replies)").fetchall()
            }

        assert "shop_marketplace_connections" in tables
        assert {"external_sync_status", "external_sync_error", "external_synced_at"}.issubset(
            reply_cols
        )

    def test_shopee_and_tiktok_oauth_authorize_and_callback_encrypt_tokens(
        self, tmp_path, monkeypatch
    ):
        app, _, db_file = _setup_oauth_app(tmp_path, monkeypatch)
        client = TestClient(app, base_url="https://testserver")
        client.post(
            "/api/v1/auth/login",
            json={"email": "owner@alpha.vn", "password": "OwnerPass123!"},
        )

        # Generate Shopee & TikTok OAuth URLs
        r_auth_shp = client.post(
            "/api/v1/shops/shop_alpha/connectors/shopee/authorize",
            json={
                "redirect_url": "https://pilot.ecomreview.vn/api/v1/integrations/oauth/shopee/callback"
            },
        )
        assert r_auth_shp.status_code == 200
        assert "partner_id=100888" in r_auth_shp.json()["auth_url"]
        shp_state = r_auth_shp.json()["state"]

        r_auth_ttk = client.post(
            "/api/v1/shops/shop_alpha/connectors/tiktok/authorize",
            json={
                "redirect_url": "https://pilot.ecomreview.vn/api/v1/integrations/oauth/tiktok/callback"
            },
        )
        assert r_auth_ttk.status_code == 200
        assert "app_key=ttk_app_key_123" in r_auth_ttk.json()["auth_url"]
        ttk_state = r_auth_ttk.json()["state"]

        # Tampered OAuth state is rejected
        r_bad_state = client.get(
            "/api/v1/integrations/oauth/shopee/callback?code=abc&shop_id=99&state=forged_state_token"
        )
        assert r_bad_state.status_code == 401

        # Mock Shopee POST token exchange & TikTok GET token exchange
        def _fake_shp_post(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            resp.json.return_value = {
                "access_token": "shp_live_access_secret_01",
                "refresh_token": "shp_live_refresh_secret_01",
                "expire_in": 14400,
                "refresh_expire_in": 2592000,
            }
            return resp

        def _fake_ttk_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            resp.json.return_value = {
                "code": 0,
                "data": {
                    "access_token": "ttk_live_access_secret_02",
                    "refresh_token": "ttk_live_refresh_secret_02",
                    "open_id": "ttk_open_99",
                    "seller_name": "TikTok Alpha Mall",
                    "access_token_expire_in": 2000000000,
                },
            }
            return resp

        monkeypatch.setattr("ecomreview.connectors.shopee.requests.post", _fake_shp_post)
        monkeypatch.setattr("ecomreview.connectors.tiktok.requests.get", _fake_ttk_get)

        r_cb_shp = client.get(
            f"/api/v1/integrations/oauth/shopee/callback?code=auth_code_1&shop_id=556677&state={shp_state}"
        )
        assert r_cb_shp.status_code == 200
        assert r_cb_shp.json()["connection"]["external_shop_id"] == "556677"
        assert "access_token" not in r_cb_shp.json()["connection"]

        r_cb_ttk = client.get(
            f"/api/v1/integrations/oauth/tiktok/callback?code=ttk_code_2&shop_cipher=cipher_77&state={ttk_state}"
        )
        assert r_cb_ttk.status_code == 200
        assert r_cb_ttk.json()["connection"]["external_shop_id"] == "cipher_77"

        # Verify raw SQLite stores ciphertext, never plaintext tokens
        with sqlite3.connect(db_file) as raw_conn:
            rows = raw_conn.execute(
                "SELECT platform, access_token, refresh_token FROM shop_marketplace_connections"
            ).fetchall()
        assert len(rows) == 2
        for _, enc_acc, enc_ref in rows:
            assert str(enc_acc).startswith(ENCRYPTED_PREFIX)
            assert str(enc_ref).startswith(ENCRYPTED_PREFIX)
            assert "live_access_secret" not in str(enc_acc)
            assert "live_refresh_secret" not in str(enc_ref)

        # Listing connectors never returns raw tokens
        r_list = client.get("/api/v1/shops/shop_alpha/connectors")
        assert r_list.status_code == 200
        conns = r_list.json()["connections"]
        assert len(conns) == 2
        assert all("access_token" not in c and c["has_access_token"] is True for c in conns)

    def test_ensure_fresh_connector_auto_refreshes_expiring_token(self, tmp_path, monkeypatch):
        _, db, _ = _setup_oauth_app(tmp_path, monkeypatch)
        near_expiry = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
        db.upsert_marketplace_connection(
            scenario_tag="shop_alpha",
            platform="shopee",
            external_shop_id="556677",
            access_token="old_access_tok",
            refresh_token="old_refresh_tok",
            token_expires_at=near_expiry,
        )

        def _fake_refresh_post(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            resp.json.return_value = {
                "shop_id": 556677,
                "access_token": "fresh_access_tok_999",
                "refresh_token": "fresh_refresh_tok_999",
                "expire_in": 14400,
            }
            return resp

        monkeypatch.setattr("ecomreview.connectors.shopee.requests.post", _fake_refresh_post)

        conn_with_tokens = db.get_marketplace_connection(
            "shop_alpha", "shopee", include_tokens=True
        )
        assert conn_with_tokens is not None
        connector = ensure_fresh_connector(db, conn_with_tokens, refresh_margin_seconds=900)
        assert connector.access_token == "fresh_access_tok_999"

        persisted = db.get_marketplace_connection("shop_alpha", "shopee", include_tokens=True)
        assert persisted is not None
        assert persisted["access_token"] == "fresh_access_tok_999"
        assert persisted["refresh_token"] == "fresh_refresh_tok_999"


# CreBy: MenBoyBMN
