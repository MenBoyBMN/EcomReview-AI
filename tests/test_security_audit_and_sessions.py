"""Tests for scoped shop API keys, audit logs, token revocation, refresh rotation & lockout."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from alembic import command
from ecomreview.api.auth import REFRESH_COOKIE_NAME, SESSION_COOKIE_NAME, hash_password
from ecomreview.api.main import create_app
from ecomreview.api.rate_limit import account_lockout, rate_limiter
from ecomreview.db.database import DatabaseManager


def _setup_app(tmp_path: Path, monkeypatch):
    rate_limiter.reset()
    account_lockout.reset()
    monkeypatch.setenv("ECOMREVIEW_ENV", "production")
    monkeypatch.setenv("ECOMREVIEW_JWT_SECRET", "super-strong-pilot-jwt-secret-key-32bytes")
    monkeypatch.setenv("ECOMREVIEW_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("ECOMREVIEW_CORS_ORIGINS", "https://pilot.ecomreview.vn")
    monkeypatch.setenv("ECOMREVIEW_TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.delenv("ECOMREVIEW_API_KEY", raising=False)

    db_file = tmp_path / "sec_audit.db"
    db = DatabaseManager(db_path=str(db_file), db_backend="sqlite")
    db.create_pilot_shop(slug="shop_alpha", name="Shop Alpha")
    db.create_pilot_shop(slug="shop_beta", name="Shop Beta")

    admin_u = db.upsert_user(
        email="admin@ecom.vn",
        password_hash=hash_password("AdminPass123!"),
        full_name="Admin Pilot",
        role="admin",
        allowed_shops=["*"],
    )
    owner_a = db.upsert_user(
        email="owner_a@alpha.vn",
        password_hash=hash_password("OwnerPass123!"),
        full_name="Owner Alpha",
        role="owner",
        allowed_shops=["shop_alpha"],
    )
    db.upsert_user(
        email="owner_b@beta.vn",
        password_hash=hash_password("BetaPass123!"),
        full_name="Owner Beta",
        role="owner",
        allowed_shops=["shop_beta"],
    )

    for slug in ("shop_alpha", "shop_beta"):
        db.upsert_review_and_opinions(
            review_id=f"{slug}_rev_1",
            platform="shopee",
            shop=slug,
            product="ao_mua_da_ca",
            rating=2,
            text_raw="Áo mưa bị thấm nước ở đường may vai",
            text_norm="áo mưa bị thấm nước ở đường may vai",
            source="test",
            scenario_tag=slug,
            overall_sentiment="negative",
            informative=True,
            opinions=[{"aspect": "WATERPROOF", "polarity": "negative", "evidence": "thấm nước"}],
            created_at="2026-10-01",
        )

    app = create_app(db_path=str(db_file))
    return app, db, admin_u, owner_a


class TestSecurityAuditAndSessions:
    def test_scoped_shop_api_key_isolation_and_revocation(self, tmp_path, monkeypatch):
        app, _, _, _ = _setup_app(tmp_path, monkeypatch)
        owner_client = TestClient(app, base_url="https://testserver")
        owner_client.post(
            "/api/v1/auth/login",
            json={"email": "owner_a@alpha.vn", "password": "OwnerPass123!"},
        )

        # Cannot mint admin role on shop-scoped key
        r_bad_role = owner_client.post(
            "/api/v1/shops/shop_alpha/api-keys",
            json={"name": "Bad Admin Key", "role": "admin"},
        )
        assert r_bad_role.status_code == 400

        # Mint valid owner key for shop_alpha
        r_mint = owner_client.post(
            "/api/v1/shops/shop_alpha/api-keys",
            json={"name": "n8n Sync Alpha", "role": "owner"},
        )
        assert r_mint.status_code == 200
        minted = r_mint.json()
        raw_key = minted["api_key"]
        key_id = minted["id"]
        assert raw_key.startswith("ek_live_")

        # List omits key_hash and raw api_key
        r_list = owner_client.get("/api/v1/shops/shop_alpha/api-keys")
        assert r_list.status_code == 200
        listed_item = r_list.json()["api_keys"][0]
        assert "key_hash" not in listed_item
        assert "api_key" not in listed_item

        # Key works for shop_alpha but is blocked (403) on shop_beta
        api_client = TestClient(app, base_url="https://testserver")
        assert (
            api_client.get(
                "/api/v1/stats/overview?scenario_tag=shop_alpha",
                headers={"X-API-Key": raw_key},
            ).status_code
            == 200
        )
        assert (
            api_client.get(
                "/api/v1/stats/overview?scenario_tag=shop_beta",
                headers={"X-API-Key": raw_key},
            ).status_code
            == 403
        )

        # Revoke key -> subsequent calls get 401
        r_rev = owner_client.delete(f"/api/v1/shops/shop_alpha/api-keys/{key_id}")
        assert r_rev.status_code == 200
        assert r_rev.json()["is_active"] is False
        assert (
            api_client.get(
                "/api/v1/stats/overview?scenario_tag=shop_alpha",
                headers={"X-API-Key": raw_key},
            ).status_code
            == 401
        )

    def test_audit_logs_capture_sensitive_actions_and_respect_tenant_scope(
        self, tmp_path, monkeypatch
    ):
        app, db, _, _ = _setup_app(tmp_path, monkeypatch)
        client_a = TestClient(app, base_url="https://testserver")
        client_a.post(
            "/api/v1/auth/login",
            json={"email": "owner_a@alpha.vn", "password": "OwnerPass123!"},
        )

        # Trigger sensitive actions in shop_alpha
        client_a.patch("/api/v1/shops/shop_alpha/alerts", json={"min_rating_alert": 1})
        client_a.post(
            "/api/v1/shops/shop_alpha/api-keys",
            json={"name": "Audit Test Key", "role": "cskh"},
        )
        assert (
            client_a.get("/api/v1/reports/export?scenario_tag=shop_alpha&format=html").status_code
            == 200
        )

        reply_id = db.insert_review_reply(
            review_id="shop_alpha_rev_1",
            scenario_tag="shop_alpha",
            reply_text=(
                "Dạ shop xin lỗi về sự cố thấm nước và sẽ hỗ trợ đổi trả theo chính sách sàn ạ."
            ),
        )
        r_rep = client_a.post(
            f"/api/v1/reviews/replies/{reply_id}/status",
            json={"status": "APPROVED"},
        )
        assert r_rep.status_code == 200

        # Also generate a beta shop audit entry via owner_b
        client_b = TestClient(app, base_url="https://testserver")
        client_b.post(
            "/api/v1/auth/login",
            json={"email": "owner_b@beta.vn", "password": "BetaPass123!"},
        )
        client_b.patch("/api/v1/shops/shop_beta/alerts", json={"min_rating_alert": 2})

        r_logs_a = client_a.get("/api/v1/audit-logs")
        assert r_logs_a.status_code == 200
        logs_a = r_logs_a.json()["logs"]
        actions_a = {item["action"] for item in logs_a}
        assert {
            "shop.alerts_update",
            "shop.api_key_create",
            "report.export",
            "reply.approved",
        }.issubset(actions_a)
        # Owner A must never see shop_beta audit records
        assert all(item["scenario_tag"] != "shop_beta" for item in logs_a)
        assert client_a.get("/api/v1/audit-logs?scenario_tag=shop_beta").status_code == 403

    def test_refresh_token_rotation_and_reuse_detection(self, tmp_path, monkeypatch):
        app, _, _, _ = _setup_app(tmp_path, monkeypatch)
        client = TestClient(app, base_url="https://testserver")

        r_login = client.post(
            "/api/v1/auth/login",
            json={"email": "owner_a@alpha.vn", "password": "OwnerPass123!"},
        )
        assert r_login.status_code == 200
        assert SESSION_COOKIE_NAME in r_login.cookies
        assert REFRESH_COOKIE_NAME in r_login.cookies
        rt1 = r_login.json()["refresh_token"]

        # Rotate refresh token -> yields new rt2
        r_ref = client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
        assert r_ref.status_code == 200
        rt2 = r_ref.json()["refresh_token"]
        assert rt2 != rt1

        # Replay old rt1 (reuse attack) -> 401 and revokes entire family (rt2 also dies)
        r_reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
        assert r_reuse.status_code == 401

        r_after_reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": rt2})
        assert r_after_reuse.status_code == 401

    def test_change_password_and_admin_suspend_revoke_existing_jwt(self, tmp_path, monkeypatch):
        app, _, _, owner_a = _setup_app(tmp_path, monkeypatch)
        owner_client = TestClient(app, base_url="https://testserver")
        r_login = owner_client.post(
            "/api/v1/auth/login",
            json={"email": "owner_a@alpha.vn", "password": "OwnerPass123!"},
        )
        old_jwt = r_login.json()["access_token"]

        # Change password revokes old_jwt immediately
        r_chg = owner_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "OwnerPass123!", "new_password": "NewStrongPass456!"},
            headers={"Authorization": f"Bearer {old_jwt}"},
        )
        assert r_chg.status_code == 200
        assert (
            owner_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {old_jwt}"},
            ).status_code
            == 401
        )

        # Login with new password succeeds
        r_relogin = owner_client.post(
            "/api/v1/auth/login",
            json={"email": "owner_a@alpha.vn", "password": "NewStrongPass456!"},
        )
        assert r_relogin.status_code == 200
        new_jwt = r_relogin.json()["access_token"]

        # Admin suspends owner_a -> new_jwt immediately rejected
        admin_client = TestClient(app, base_url="https://testserver")
        admin_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@ecom.vn", "password": "AdminPass123!"},
        )
        r_susp = admin_client.patch(
            f"/api/v1/users/{owner_a['id']}/status",
            json={"is_active": False},
        )
        assert r_susp.status_code == 200
        assert r_susp.json()["is_active"] is False
        assert (
            owner_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {new_jwt}"},
            ).status_code
            == 401
        )

    def test_account_lockout_blocks_after_five_failures_regardless_of_ip(
        self, tmp_path, monkeypatch
    ):
        app, _, _, _ = _setup_app(tmp_path, monkeypatch)
        client = TestClient(app, base_url="https://testserver")

        for idx in range(5):
            r = client.post(
                "/api/v1/auth/login",
                json={"email": "owner_a@alpha.vn", "password": "WrongPassword!"},
                headers={"X-Forwarded-For": f"198.51.100.{idx + 1}"},
            )
            assert r.status_code == 401

        # 6th attempt even from a brand new IP and with correct password is locked (429)
        r_locked = client.post(
            "/api/v1/auth/login",
            json={"email": "owner_a@alpha.vn", "password": "OwnerPass123!"},
            headers={"X-Forwarded-For": "203.0.113.99"},
        )
        assert r_locked.status_code == 429

        # Different user is unaffected
        r_other = client.post(
            "/api/v1/auth/login",
            json={"email": "owner_b@beta.vn", "password": "BetaPass123!"},
        )
        assert r_other.status_code == 200

    def test_alembic_upgrade_head_applies_0001_through_0003_cleanly(self, tmp_path, monkeypatch):
        db_file = tmp_path / "alembic_fresh.db"
        monkeypatch.setenv("ECOMREVIEW_DB_BACKEND", "sqlite")
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")

        repo_root = Path(__file__).resolve().parents[1]
        cfg = Config(str(repo_root / "alembic.ini"))
        cfg.set_main_option("script_location", str(repo_root / "alembic"))
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file.as_posix()}")
        command.upgrade(cfg, "head")

        with sqlite3.connect(db_file) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}

        assert {"shop_api_keys", "audit_logs", "refresh_tokens"}.issubset(tables)
        assert "token_version" in user_cols


# CreBy: MenBoyBMN
