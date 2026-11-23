"""Tests for Pilot JWT/Cookie Authentication, RBAC, Fail-Closed Production & IDOR protection."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ecomreview.api.auth import SESSION_COOKIE_NAME, hash_password
from ecomreview.api.main import create_app
from ecomreview.api.rate_limit import rate_limiter
from ecomreview.db.database import DatabaseManager


def _setup_pilot_app(tmp_path, monkeypatch, env: str = "production"):
    rate_limiter.reset()
    monkeypatch.setenv("ECOMREVIEW_ENV", env)
    monkeypatch.setenv("ECOMREVIEW_JWT_SECRET", "super-strong-pilot-jwt-secret-key-at-least-32b")
    monkeypatch.setenv("ECOMREVIEW_CORS_ORIGINS", "https://pilot.ecomreview.vn")
    monkeypatch.setenv("ECOMREVIEW_TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.delenv("ECOMREVIEW_API_KEY", raising=False)

    db_file = tmp_path / "pilot_auth.db"
    db = DatabaseManager(db_path=str(db_file), db_backend="sqlite")
    db.create_pilot_shop(slug="shop_alpha", name="Shop Alpha")
    db.create_pilot_shop(slug="shop_beta", name="Shop Beta")

    db.upsert_user(
        email="admin@ecom.vn",
        password_hash=hash_password("AdminPass123!"),
        full_name="Admin Pilot",
        role="admin",
        allowed_shops=["*"],
    )
    db.upsert_user(
        email="owner_a@alpha.vn",
        password_hash=hash_password("OwnerPass123!"),
        full_name="Owner Alpha",
        role="owner",
        allowed_shops=["shop_alpha"],
    )
    db.upsert_user(
        email="cskh_a@alpha.vn",
        password_hash=hash_password("CskhPass123!"),
        full_name="CSKH Alpha",
        role="cskh",
        allowed_shops=["shop_alpha"],
    )
    db.upsert_user(
        email="owner_b@beta.vn",
        password_hash=hash_password("BetaPass123!"),
        full_name="Owner Beta",
        role="owner",
        allowed_shops=["shop_beta"],
    )

    # Seed minimal data for shop_alpha and shop_beta
    for slug in ("shop_alpha", "shop_beta"):
        db.upsert_review_and_opinions(
            review_id=f"{slug}_rev_1",
            platform="shopee",
            shop=slug,
            product="ao_mua_da_ca",
            rating=2,
            text_raw="Áo mưa bị thấm nước ở đường may đáy quần",
            text_norm="áo mưa bị thấm nước ở đường may đáy quần",
            source="test",
            scenario_tag=slug,
            overall_sentiment="negative",
            informative=True,
            opinions=[{"aspect": "WATERPROOF", "polarity": "negative", "evidence": "thấm nước"}],
            created_at="2026-10-01",
        )
        db.insert_action(
            scenario_tag=slug,
            action_type="PRODUCT_FIX",
            is_marketing=False,
            title=f"Fix {slug}",
            what_to_do="Gia cố đường may",
            why_rationale="Tỷ lệ thấm cao",
            how_and_when="Trong 48h",
            success_metric="Giảm lỗi 50%",
            effort="LOW",
            impact="HIGH",
            priority_score=4.0,
            insight_ids=["1"],
            evidence_review_ids=[f"{slug}_rev_1", f"{slug}_rev_1"],
        )

    app = create_app(db_path=str(db_file))
    return app, db


class TestPilotAuthRbacAndIdor:
    def test_production_startup_requires_strong_jwt_and_non_wildcard_cors(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("ECOMREVIEW_ENV", "production")
        monkeypatch.delenv("ECOMREVIEW_JWT_SECRET", raising=False)
        monkeypatch.setenv("ECOMREVIEW_CORS_ORIGINS", "https://pilot.ecomreview.vn")
        with pytest.raises(RuntimeError, match="ECOMREVIEW_JWT_SECRET"):
            create_app(db_path=str(tmp_path / "fail1.db"))

        monkeypatch.setenv("ECOMREVIEW_JWT_SECRET", "super-strong-pilot-jwt-secret-key-32chars")
        monkeypatch.setenv("ECOMREVIEW_CORS_ORIGINS", "*")
        with pytest.raises(RuntimeError, match="ECOMREVIEW_CORS_ORIGINS"):
            create_app(db_path=str(tmp_path / "fail2.db"))

    def test_production_fail_closed_and_cookie_login_flow(self, tmp_path, monkeypatch):
        app, _ = _setup_pilot_app(tmp_path, monkeypatch, env="production")
        client = TestClient(app, base_url="https://testserver")

        # Unauthenticated request must return 401
        r_unauth = client.get("/api/v1/stats/overview?scenario_tag=shop_alpha")
        assert r_unauth.status_code == 401

        # Wrong password -> 401
        r_bad = client.post(
            "/api/v1/auth/login",
            json={"email": "owner_a@alpha.vn", "password": "wrong"},
        )
        assert r_bad.status_code == 401

        # Valid login sets HttpOnly cookie and unlocks shop_alpha
        r_ok = client.post(
            "/api/v1/auth/login",
            json={"email": "owner_a@alpha.vn", "password": "OwnerPass123!"},
        )
        assert r_ok.status_code == 200
        assert SESSION_COOKIE_NAME in r_ok.cookies
        assert r_ok.json()["user"]["role"] == "owner"

        r_me = client.get("/api/v1/auth/me")
        assert r_me.status_code == 200
        assert r_me.json()["user"]["email"] == "owner_a@alpha.vn"

        r_shops = client.get("/api/v1/shops")
        assert r_shops.status_code == 200
        assert [s["slug"] for s in r_shops.json()["shops"]] == ["shop_alpha"]

        # Logout clears session
        client.post("/api/v1/auth/logout")
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_cross_shop_idor_is_blocked_on_all_resources(self, tmp_path, monkeypatch):
        app, db = _setup_pilot_app(tmp_path, monkeypatch, env="production")
        client_a = TestClient(app, base_url="https://testserver")
        client_a.post(
            "/api/v1/auth/login",
            json={"email": "owner_a@alpha.vn", "password": "OwnerPass123!"},
        )

        # Owner A can access shop_alpha
        assert client_a.get("/api/v1/stats/overview?scenario_tag=shop_alpha").status_code == 200
        # Owner A cannot access shop_beta overview, reviews, or export
        assert client_a.get("/api/v1/stats/overview?scenario_tag=shop_beta").status_code == 403
        assert client_a.get("/api/v1/reviews?scenario_tag=shop_beta").status_code == 403
        assert client_a.get("/api/v1/reports/export?scenario_tag=shop_beta").status_code == 403

        # Locate shop_beta action_id and reply_id and verify IDOR returns 403
        with db.get_connection(read_only=True) as conn:
            beta_act = conn.execute(
                "SELECT id FROM actions WHERE scenario_tag = 'shop_beta'"
            ).fetchone()
        beta_action_id = int(beta_act["id"])
        beta_reply_id = db.insert_review_reply(
            review_id="shop_beta_rev_1",
            scenario_tag="shop_beta",
            reply_text="Dạ shop xin lỗi và hỗ trợ đổi trả sản phẩm qua kênh chat sàn ạ.",
        )
        beta_job_id = db.log_job_start("analyze_run", scenario_tag="shop_beta")

        assert (
            client_a.post(
                f"/api/v1/actions/{beta_action_id}/decision",
                json={"decision": "APPROVED"},
            ).status_code
            == 403
        )
        assert client_a.get(f"/api/v1/actions/{beta_action_id}/impact").status_code == 403
        assert (
            client_a.post(
                f"/api/v1/reviews/replies/{beta_reply_id}/status",
                json={"status": "APPROVED"},
            ).status_code
            == 403
        )
        assert client_a.get(f"/api/v1/jobs/{beta_job_id}").status_code == 403

    def test_rbac_restricts_cskh_from_admin_and_owner_actions(self, tmp_path, monkeypatch):
        app, db = _setup_pilot_app(tmp_path, monkeypatch, env="production")
        client_cskh = TestClient(app, base_url="https://testserver")
        client_cskh.post(
            "/api/v1/auth/login",
            json={"email": "cskh_a@alpha.vn", "password": "CskhPass123!"},
        )

        # CSKH can view reviews and create/update reply drafts
        assert client_cskh.get("/api/v1/reviews?scenario_tag=shop_alpha").status_code == 200
        r_draft = client_cskh.post(
            "/api/v1/reviews/shop_alpha_rev_1/reply-draft?scenario_tag=shop_alpha&mode=template"
        )
        assert r_draft.status_code == 200
        reply_id = r_draft.json()["reply_id"]
        assert (
            client_cskh.post(
                f"/api/v1/reviews/replies/{reply_id}/status",
                json={"status": "SENT"},
            ).status_code
            == 200
        )

        # CSKH cannot approve strategic actions, run analysis, upload, or create shops
        with db.get_connection(read_only=True) as conn:
            alpha_act = conn.execute(
                "SELECT id FROM actions WHERE scenario_tag = 'shop_alpha'"
            ).fetchone()
        assert (
            client_cskh.post(
                f"/api/v1/actions/{int(alpha_act['id'])}/decision",
                json={"decision": "APPROVED"},
            ).status_code
            == 403
        )
        assert (
            client_cskh.post(
                "/api/v1/analyze/run",
                json={"scenario_tag": "shop_alpha", "analyzer_method": "b1_rule"},
            ).status_code
            == 403
        )
        assert (
            client_cskh.post(
                "/api/v1/shops",
                json={"slug": "new_shop", "name": "New Shop"},
            ).status_code
            == 403
        )


# CreBy: MenBoyBMN
