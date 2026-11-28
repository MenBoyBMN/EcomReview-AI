"""Tests for marketplace auto-sync worker, critical alerting, and 1-click push reply."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from ecomreview.api.auth import hash_password
from ecomreview.api.main import create_app
from ecomreview.api.rate_limit import account_lockout, rate_limiter
from ecomreview.db.database import DatabaseManager
from ecomreview.jobs.queue_worker import run_scheduled_marketplace_sync


def _setup_sync_app(tmp_path: Path, monkeypatch):
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
    monkeypatch.delenv("ECOMREVIEW_API_KEY", raising=False)

    db_file = tmp_path / "sync_reply.db"
    db = DatabaseManager(db_path=str(db_file), db_backend="sqlite")
    db.create_pilot_shop(
        slug="shop_sync",
        name="Shop Sync Test",
        alert_config={
            "telegram_bot_token": "12345:TG_SYNC_TOK",
            "telegram_chat_id": "-1009999",
            "min_rating_alert": 2,
        },
    )
    db.upsert_user(
        email="owner@sync.vn",
        password_hash=hash_password("OwnerPass123!"),
        full_name="Owner Sync",
        role="owner",
        allowed_shops=["shop_sync"],
    )
    app = create_app(db_path=str(db_file))
    return app, db, db_file


class TestMarketplaceSyncAndPushReply:
    def test_manual_and_scheduled_sync_ingests_reviews_and_alerts_critical(
        self, tmp_path, monkeypatch
    ):
        app, db, db_file = _setup_sync_app(tmp_path, monkeypatch)
        client = TestClient(app, base_url="https://testserver")
        client.post(
            "/api/v1/auth/login",
            json={"email": "owner@sync.vn", "password": "OwnerPass123!"},
        )

        # Save manual connection for shop_sync -> shopee
        future_exp = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
        r_conn = client.post(
            "/api/v1/shops/shop_sync/connectors/shopee/manual",
            json={
                "external_shop_id": "889900",
                "access_token": "shp_tok_valid",
                "refresh_token": "shp_ref_valid",
                "auto_sync_enabled": True,
                "sync_interval_minutes": 15,
            },
        )
        assert r_conn.status_code == 200
        assert r_conn.json()["connection"]["external_shop_id"] == "889900"

        # Mock Shopee fetch_reviews HTTP & Telegram alert POST
        now_ts = int(datetime.now(timezone.utc).timestamp())
        tg_calls = []

        def _fake_shp_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            resp.json.return_value = {
                "response": {
                    "item_comment_list": [
                        {
                            "comment_id": 7701,
                            "item_id": 12345,
                            "rating_star": 1,
                            "comment": "Áo mưa bị thấm nước ở đường may vai",
                            "create_time": now_ts,
                        },
                        {
                            "comment_id": 7702,
                            "item_id": 12345,
                            "rating_star": 5,
                            "comment": "Vải dày dặn giao hàng nhanh",
                            "create_time": now_ts,
                        },
                    ]
                }
            }
            return resp

        def _fake_tg_post(url, **kwargs):
            tg_calls.append((url, kwargs))
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            resp.json.return_value = {"ok": True}
            return resp

        monkeypatch.setattr("ecomreview.connectors.shopee.requests.get", _fake_shp_get)
        monkeypatch.setattr("ecomreview.alerts.notifier.requests.post", _fake_tg_post)

        r_sync = client.post(
            "/api/v1/shops/shop_sync/connectors/shopee/sync",
            json={"analyzer_method": "b1_rule", "limit": 50},
        )
        assert r_sync.status_code == 202
        job_id = r_sync.json()["job_id"]
        job_info = client.get(f"/api/v1/jobs/{job_id}").json()
        assert job_info["status"] == "completed"
        assert job_info["details"]["fetched_count"] == 2
        assert job_info["details"]["inserted_count"] == 2
        assert len(tg_calls) == 1  # 1-star review triggered Telegram alert

        # Verify connection last_synced_at updated -> scheduler skips immediately
        skipped_runs = run_scheduled_marketplace_sync(
            analyzer_method="b1_rule", db_path=str(db_file)
        )
        assert skipped_runs == []

        # Backdate last_synced_at beyond sync_interval_minutes -> scheduler triggers job
        old_sync = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        db.upsert_marketplace_connection(
            scenario_tag="shop_sync",
            platform="shopee",
            external_shop_id="889900",
            access_token="shp_tok_valid",
            token_expires_at=future_exp,
            sync_interval_minutes=15,
        )
        db.record_marketplace_sync_result("shop_sync", "shopee", "OK", synced_at=old_sync)
        due_runs = run_scheduled_marketplace_sync(analyzer_method="b1_rule", db_path=str(db_file))
        assert len(due_runs) == 1
        assert due_runs[0]["scenario_tag"] == "shop_sync"

    def test_one_click_push_reply_idempotency_retry_and_local_only_fallback(
        self, tmp_path, monkeypatch
    ):
        app, db, _ = _setup_sync_app(tmp_path, monkeypatch)
        client = TestClient(app, base_url="https://testserver")
        client.post(
            "/api/v1/auth/login",
            json={"email": "owner@sync.vn", "password": "OwnerPass123!"},
        )

        # Seed a Shopee review and a TikTok review (only Shopee is connected)
        db.upsert_review_and_opinions(
            review_id="shp_9001",
            platform="shopee",
            shop="shop_sync",
            product="ao_mua_da_ca",
            rating=2,
            text_raw="Áo mưa bị thấm nước ở vai",
            text_norm="áo mưa bị thấm nước ở vai",
            source="shopee_api",
            scenario_tag="shop_sync",
            overall_sentiment="negative",
            informative=True,
            opinions=[{"aspect": "WATERPROOF", "polarity": "negative", "evidence": "thấm nước"}],
            created_at="2026-11-23",
        )
        db.upsert_review_and_opinions(
            review_id="ttk_9002",
            platform="tiktok",
            shop="shop_sync",
            product="ao_mua_da_ca",
            rating=2,
            text_raw="Áo mưa hơi mỏng",
            text_norm="áo mưa hơi mỏng",
            source="tiktok_api",
            scenario_tag="shop_sync",
            overall_sentiment="negative",
            informative=True,
            opinions=[
                {"aspect": "MATERIAL_DURABILITY", "polarity": "negative", "evidence": "hơi mỏng"}
            ],
            created_at="2026-11-23",
        )
        db.upsert_marketplace_connection(
            scenario_tag="shop_sync",
            platform="shopee",
            external_shop_id="889900",
            access_token="shp_tok_valid",
            token_expires_at=(datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
        )

        # 1. TikTok has no connection -> marking SENT remains LOCAL_ONLY
        r_ttk_draft = client.post(
            "/api/v1/reviews/ttk_9002/reply-draft?scenario_tag=shop_sync&mode=template"
        )
        ttk_reply_id = r_ttk_draft.json()["reply_id"]
        r_ttk_sent = client.post(
            f"/api/v1/reviews/replies/{ttk_reply_id}/status",
            json={"status": "SENT"},
        )
        assert r_ttk_sent.status_code == 200
        assert r_ttk_sent.json()["external_sync_status"] == "LOCAL_ONLY"

        # 2. Shopee has connection -> first failure sets FAILED, retry succeeds -> PUSHED
        r_shp_draft = client.post(
            "/api/v1/reviews/shp_9001/reply-draft?scenario_tag=shop_sync&mode=template"
        )
        shp_reply_id = r_shp_draft.json()["reply_id"]

        post_calls = []
        should_fail = {"flag": True}

        def _fake_reply_post(url, **kwargs):
            post_calls.append((url, kwargs))
            if should_fail["flag"]:
                raise RuntimeError("Shopee upstream 503")
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            resp.json.return_value = {"error": "", "response": {"succ_comment_id_list": [9001]}}
            return resp

        monkeypatch.setattr("ecomreview.connectors.shopee.requests.post", _fake_reply_post)

        r_fail = client.post(
            f"/api/v1/reviews/replies/{shp_reply_id}/status",
            json={"status": "SENT"},
        )
        assert r_fail.status_code == 200
        assert r_fail.json()["external_sync_status"] in {"QUEUED", "FAILED"}
        rep_after_fail = client.get(
            "/api/v1/reviews/shp_9001/replies?scenario_tag=shop_sync"
        ).json()["replies"][0]
        assert rep_after_fail["external_sync_status"] == "FAILED"
        assert "Shopee upstream 503" in str(rep_after_fail["external_sync_error"])
        assert len(post_calls) == 1

        # Retry push after upstream recovers -> PUSHED
        should_fail["flag"] = False
        r_retry = client.post(f"/api/v1/reviews/replies/{shp_reply_id}/retry-push")
        assert r_retry.status_code == 200
        assert r_retry.json()["external_sync_status"] in {"QUEUED", "PUSHED"}
        rep_after_retry = client.get(
            "/api/v1/reviews/shp_9001/replies?scenario_tag=shop_sync"
        ).json()["replies"][0]
        assert rep_after_retry["external_sync_status"] == "PUSHED"
        assert len(post_calls) == 2

        # Idempotent: calling retry again does NOT push a duplicate reply
        r_retry_again = client.post(f"/api/v1/reviews/replies/{shp_reply_id}/retry-push")
        assert r_retry_again.status_code == 200
        assert r_retry_again.json()["external_sync_status"] == "PUSHED"
        assert len(post_calls) == 2


# CreBy: MenBoyBMN
