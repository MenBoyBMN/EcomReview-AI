"""Tests for Phase 3B: Agency Executive Dashboard, Owner Team, Trial Onboarding & Quota."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from alembic import command
from ecomreview.api.auth import hash_password
from ecomreview.api.main import create_app
from ecomreview.api.rate_limit import account_lockout, rate_limiter, tenant_job_quota
from ecomreview.billing.quota_service import current_month_key
from ecomreview.db.database import DatabaseManager
from ecomreview.ingest_service import ingest_review_batch


def _setup_3b_app(tmp_path: Path, monkeypatch):
    rate_limiter.reset()
    account_lockout.reset()
    tenant_job_quota.reset()
    monkeypatch.setenv("ECOMREVIEW_ENV", "production")
    monkeypatch.setenv("ECOMREVIEW_JWT_SECRET", "super-strong-pilot-jwt-secret-key-32bytes")
    monkeypatch.setenv("ECOMREVIEW_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("ECOMREVIEW_CORS_ORIGINS", "https://pilot.ecomreview.vn")
    monkeypatch.setenv("ECOMREVIEW_TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.setenv("ECOMREVIEW_QUEUE_DISABLE", "true")
    monkeypatch.setenv("ECOMREVIEW_ALLOW_SELF_SIGNUP", "true")
    monkeypatch.delenv("ECOMREVIEW_API_KEY", raising=False)

    db_file = tmp_path / "phase3b.db"
    db = DatabaseManager(db_path=str(db_file), db_backend="sqlite")
    db.create_pilot_shop(slug="ag_shop_a", name="Agency Shop A", industry="fashion")
    db.create_pilot_shop(slug="ag_shop_b", name="Agency Shop B", industry="cosmetics")
    db.create_pilot_shop(slug="other_tenant", name="Other Tenant Shop", industry="raincoat")

    db.upsert_user(
        email="admin@ecom.vn",
        password_hash=hash_password("AdminPass123!"),
        full_name="Platform Admin",
        role="admin",
        allowed_shops=["*"],
    )
    db.upsert_user(
        email="agency@ecom.vn",
        password_hash=hash_password("AgencyPass123!"),
        full_name="Agency Owner",
        role="owner",
        allowed_shops=["ag_shop_a", "ag_shop_b"],
    )
    db.upsert_user(
        email="other@ecom.vn",
        password_hash=hash_password("OtherPass123!"),
        full_name="Other Owner",
        role="owner",
        allowed_shops=["other_tenant"],
    )
    app = create_app(db_path=str(db_file))
    return app, db


class TestPhase3BAgencyTeamBilling:
    def test_executive_summary_scopes_to_allowed_shops_and_ranks_risk(self, tmp_path, monkeypatch):
        app, db = _setup_3b_app(tmp_path, monkeypatch)

        # Shop A: high negative rate (3/4 negative)
        for idx, (rat, sent, pol) in enumerate(
            [
                (1, "negative", "negative"),
                (2, "negative", "negative"),
                (2, "negative", "negative"),
                (5, "positive", "positive"),
            ]
        ):
            db.upsert_review_and_opinions(
                review_id=f"a_{idx}",
                platform="shopee" if idx < 3 else "tiktok",
                shop="ag_shop_a",
                product="ao_kaki",
                rating=rat,
                text_raw="Chất lượng chật" if pol == "negative" else "Rất đẹp",
                text_norm="chất lượng chật" if pol == "negative" else "rất đẹp",
                source="review",
                scenario_tag="ag_shop_a",
                overall_sentiment=sent,
                informative=True,
                opinions=[
                    {
                        "aspect": "FIT_SIZE",
                        "polarity": pol,
                        "evidence": "chật" if pol == "negative" else "đẹp",
                    }
                ],
                created_at="2026-11-20",
            )
        # Mark 1 of 3 low-star reviews as replied (SENT) -> SLA 33.3%
        db.insert_review_reply(
            review_id="a_0",
            scenario_tag="ag_shop_a",
            reply_text="Shop xin lỗi về kích cỡ ạ",
            status="SENT",
        )

        # Shop B: healthy (2/2 positive)
        for idx in range(2):
            db.upsert_review_and_opinions(
                review_id=f"b_{idx}",
                platform="tiktok",
                shop="ag_shop_b",
                product="serum_c",
                rating=5,
                text_raw="Thấm nhanh cực kỳ ưng",
                text_norm="thấm nhanh cực kỳ ưng",
                source="review",
                scenario_tag="ag_shop_b",
                overall_sentiment="positive",
                informative=True,
                opinions=[
                    {"aspect": "WATERPROOF", "polarity": "positive", "evidence": "Thấm nhanh"}
                ],
                created_at="2026-11-20",
            )

        # Other tenant data (must NEVER leak into agency@ecom.vn summary)
        db.upsert_review_and_opinions(
            review_id="oth_1",
            platform="shopee",
            shop="other_tenant",
            product="secret_sku",
            rating=1,
            text_raw="Rách đường may",
            text_norm="rách đường may",
            source="review",
            scenario_tag="other_tenant",
            overall_sentiment="negative",
            informative=True,
            opinions=[
                {
                    "aspect": "MATERIAL_DURABILITY",
                    "polarity": "negative",
                    "evidence": "Rách đường may",
                }
            ],
            created_at="2026-11-20",
        )

        client = TestClient(app, base_url="https://testserver")
        client.post(
            "/api/v1/auth/login",
            json={"email": "agency@ecom.vn", "password": "AgencyPass123!"},
        )
        res = client.get("/api/v1/executive/summary")
        assert res.status_code == 200
        data = res.json()
        assert data["portfolio"]["total_shops"] == 2
        assert data["portfolio"]["total_reviews"] == 6
        assert [s["slug"] for s in data["shops"]] == ["ag_shop_a", "ag_shop_b"]
        shop_a = data["shops"][0]
        assert shop_a["negative_rate_pct"] == 75.0
        assert shop_a["cskh_sla_pct"] == 33.3
        assert shop_a["top_pain_aspect"] == "FIT_SIZE"
        assert data["channel_summary"]["shopee"]["reviews"] == 3
        assert data["channel_summary"]["tiktok"]["reviews"] == 3

    def test_owner_team_management_workspace_quota_and_trial_signup(self, tmp_path, monkeypatch):
        app, db = _setup_3b_app(tmp_path, monkeypatch)
        agency_client = TestClient(app, base_url="https://testserver")
        agency_client.post(
            "/api/v1/auth/login",
            json={"email": "agency@ecom.vn", "password": "AgencyPass123!"},
        )

        # Owner cannot create admin/owner or assign unauthorized shop
        bad_role = agency_client.post(
            "/api/v1/team/users",
            json={
                "email": "hack@ecom.vn",
                "password": "Password123!",
                "full_name": "Hack",
                "role": "admin",
                "allowed_shops": ["ag_shop_a"],
            },
        )
        assert bad_role.status_code == 403

        bad_shop = agency_client.post(
            "/api/v1/team/users",
            json={
                "email": "cskh_x@ecom.vn",
                "password": "Password123!",
                "full_name": "Staff X",
                "role": "cskh",
                "allowed_shops": ["other_tenant"],
            },
        )
        assert bad_shop.status_code == 403

        # Valid CSKH provisioning within owner's shops
        ok_staff = agency_client.post(
            "/api/v1/team/users",
            json={
                "email": "cskh_a@ecom.vn",
                "password": "StaffPass123!",
                "full_name": "CSKH A",
                "role": "cskh",
                "allowed_shops": ["ag_shop_a"],
            },
        )
        assert ok_staff.status_code == 200
        staff_id = ok_staff.json()["id"]

        team_list = agency_client.get("/api/v1/team/users")
        assert team_list.status_code == 200
        emails = {u["email"] for u in team_list.json()["users"]}
        assert emails == {"agency@ecom.vn", "cskh_a@ecom.vn"}

        # CSKH logs in, then owner suspends CSKH -> immediate 401 token revocation
        staff_client = TestClient(app, base_url="https://testserver")
        assert (
            staff_client.post(
                "/api/v1/auth/login",
                json={"email": "cskh_a@ecom.vn", "password": "StaffPass123!"},
            ).status_code
            == 200
        )
        assert staff_client.get("/api/v1/auth/me").status_code == 200

        susp = agency_client.patch(
            f"/api/v1/team/users/{staff_id}/status", json={"is_active": False}
        )
        assert susp.status_code == 200
        assert staff_client.get("/api/v1/auth/me").status_code == 401

        # Owner on default basic plan has 2 shops (ag_shop_a, ag_shop_b) -> 3rd blocked (402)
        over_shop = agency_client.post(
            "/api/v1/workspace/shops",
            json={"slug": "ag_shop_c", "name": "Shop C", "industry": "electronics"},
        )
        assert over_shop.status_code == 402

        # Admin upgrades ag_shop_a to Agency plan -> owner can now add 3rd shop
        admin_client = TestClient(app, base_url="https://testserver")
        admin_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@ecom.vn", "password": "AdminPass123!"},
        )
        up_res = admin_client.patch(
            "/api/v1/admin/subscriptions/ag_shop_a",
            json={"plan_code": "agency", "status": "ACTIVE"},
        )
        assert up_res.status_code == 200
        assert up_res.json()["max_shops"] == 30

        ok_shop_c = agency_client.post(
            "/api/v1/workspace/shops",
            json={"slug": "ag_shop_c", "name": "Shop C", "industry": "electronics"},
        )
        assert ok_shop_c.status_code == 200
        # Updated JWT cookie grants immediate access to ag_shop_c
        assert agency_client.get("/api/v1/stats/overview?scenario_tag=ag_shop_c").status_code == 200

        # Self-service 14-day trial onboarding
        anon = TestClient(app, base_url="https://testserver")
        reg = anon.post(
            "/api/v1/auth/register-trial",
            json={
                "email": "newbrand@vn.com",
                "password": "TrialPassword123!",
                "full_name": "New Brand Owner",
                "shop_name": "Brand Gia Dụng Mới",
                "shop_slug": "brand_giadung",
                "industry": "home_living",
                "seed_sample_data": True,
            },
        )
        assert reg.status_code == 200
        reg_json = reg.json()
        assert reg_json["shop"]["industry"] == "home_living"
        assert reg_json["subscription"]["plan_code"] == "trial"
        assert reg_json["subscription"]["status"] == "TRIAL"
        # Authenticated immediately via HttpOnly cookies and populated with starter data
        ov = anon.get("/api/v1/stats/overview?scenario_tag=brand_giadung")
        assert ov.status_code == 200
        assert ov.json()["total_reviews"] == 3

        # Duplicate trial email blocked with 409
        dup_reg = anon.post(
            "/api/v1/auth/register-trial",
            json={
                "email": "newbrand@vn.com",
                "password": "TrialPassword123!",
                "full_name": "Dup",
                "shop_name": "Dup Shop",
                "shop_slug": "dup_shop",
            },
        )
        assert dup_reg.status_code == 409

    def test_alembic_0007_quota_metering_soft_fallback_and_block(self, tmp_path, monkeypatch):
        db_file = tmp_path / "alembic_0007.db"
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
        assert {"tenant_subscriptions", "usage_monthly"}.issubset(tables)

        app, db = _setup_3b_app(tmp_path, monkeypatch)
        admin_client = TestClient(app, base_url="https://testserver")
        admin_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@ecom.vn", "password": "AdminPass123!"},
        )

        # Configure soft fallback quota with limit=10 and pre-fill 10 LLM reviews used this month
        sub_res = admin_client.patch(
            "/api/v1/admin/subscriptions/ag_shop_a",
            json={
                "plan_code": "basic",
                "monthly_llm_review_limit": 10,
                "overage_policy": "fallback_b1",
            },
        )
        assert sub_res.status_code == 200
        db.increment_monthly_usage("ag_shop_a", current_month_key(), llm_reviews=10)

        # Exceeded quota with fallback_b1 must NOT crash -> softly downgrades a1 -> b1_rule
        soft_res = ingest_review_batch(
            db=db,
            reviews=[
                {
                    "review_id": "q_1",
                    "platform": "shopee",
                    "rating": 2,
                    "text": "Vải mỏng dễ rách ở đường may",
                }
            ],
            scenario_tag="ag_shop_a",
            analyzer_method="a1_gemini_v2",
        )
        assert soft_res["inserted_count"] == 1
        assert soft_res["quota_fallback"] is True
        assert "b1_rule" in soft_res["analyzer_method"]

        usage_res = admin_client.get("/api/v1/billing/usage?scenario_tag=ag_shop_a")
        assert usage_res.status_code == 200
        u_json = usage_res.json()
        assert u_json["usage"]["llm_reviews_used"] == 10
        assert u_json["usage"]["rule_reviews_used"] == 1
        assert u_json["usage"]["is_over_limit"] is True

        # Switching policy to 'block' causes API upload to return HTTP 402
        admin_client.patch(
            "/api/v1/admin/subscriptions/ag_shop_a",
            json={
                "plan_code": "basic",
                "monthly_llm_review_limit": 10,
                "overage_policy": "block",
            },
        )
        blocked = admin_client.post(
            "/api/v1/reviews/upload",
            json={
                "scenario_tag": "ag_shop_a",
                "analyzer_method": "a1_gemini_v2",
                "reviews": [
                    {
                        "review_id": "q_2",
                        "platform": "shopee",
                        "rating": 1,
                        "text": "Thấm nước quá nhiều",
                    }
                ],
            },
        )
        assert blocked.status_code == 402


# CreBy: MenBoyBMN
