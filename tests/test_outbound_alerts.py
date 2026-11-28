"""Tests for proactive outbound alerting (Telegram Bot + HMAC Webhook + Deduplication)."""

from __future__ import annotations

import hashlib
import hmac
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from ecomreview.alerts.notifier import dispatch_alert, notify_critical_reviews, send_webhook_alert
from ecomreview.api.main import create_app
from ecomreview.db.database import DatabaseManager


class TestOutboundAlerting:
    def test_telegram_and_webhook_dispatch_scrubs_pii_and_deduplicates(self, tmp_path, monkeypatch):
        db = DatabaseManager(db_path=str(tmp_path / "alerts.db"), db_backend="sqlite")
        shop = db.create_pilot_shop(
            slug="shop_alert",
            name="Shop Áo Mưa Test",
            alert_config={
                "telegram_bot_token": "12345:FAKE_TOKEN",
                "telegram_chat_id": "-100999",
                "webhook_url": "https://hooks.example.test/ecom",
                "min_rating_alert": 2,
            },
        )

        captured_calls = []

        def _fake_post(url, **kwargs):
            captured_calls.append((url, kwargs))
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"ok": True}
            resp.raise_for_status.return_value = None
            return resp

        monkeypatch.setattr("ecomreview.alerts.notifier.requests.post", _fake_post)

        # Dispatch with PII inside message
        res1 = dispatch_alert(
            db=db,
            scenario_tag="shop_alert",
            dedup_key="critical_review:shop_alert:rev_001",
            severity="HIGH",
            title="Review 1 sao",
            message_text="Áo mưa bị rách, liên hệ 0912345678 hoặc khach@example.com",
            payload={"review_id": "rev_001"},
        )
        assert len(res1) == 2
        assert all(r["status"] == "SENT" for r in res1)
        assert len(captured_calls) == 2

        # Verify PII scrubbed in Telegram text
        tg_url, tg_kwargs = captured_calls[0]
        assert "api.telegram.org/bot12345:FAKE_TOKEN/sendMessage" in tg_url
        assert "0912345678" not in tg_kwargs["json"]["text"]
        assert "khach@example.com" not in tg_kwargs["json"]["text"]

        # Verify HMAC-SHA256 signature and redirect-blocking on webhook
        wh_url, wh_kwargs = captured_calls[1]
        assert wh_url == "https://hooks.example.test/ecom"
        assert wh_kwargs.get("allow_redirects") is False
        expected_sig = hmac.new(
            shop["webhook_secret"].encode("utf-8"),
            wh_kwargs["data"],
            hashlib.sha256,
        ).hexdigest()
        assert wh_kwargs["headers"]["X-EcomReview-Signature"] == expected_sig

        # Second call with same dedup_key must be skipped (anti-spam)
        res2 = dispatch_alert(
            db=db,
            scenario_tag="shop_alert",
            dedup_key="critical_review:shop_alert:rev_001",
            severity="HIGH",
            title="Review 1 sao",
            message_text="Duplicate",
            payload={"review_id": "rev_001"},
        )
        assert all(r["status"] == "skipped_duplicate" for r in res2)
        assert len(captured_calls) == 2

    def test_alert_config_test_and_history_endpoints(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ECOMREVIEW_ENV", "development")
        db_file = tmp_path / "alert_api.db"
        app = create_app(db_path=str(db_file))
        client = TestClient(app)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status.return_value = None
        monkeypatch.setattr("ecomreview.alerts.notifier.requests.post", lambda *a, **kw: mock_resp)

        # Configure alerts for shop
        r_cfg = client.patch(
            "/api/v1/shops/real_shop/alerts",
            json={
                "telegram_bot_token": "999:TEST_BOT",
                "telegram_chat_id": "123456",
                "min_rating_alert": 2,
            },
        )
        assert r_cfg.status_code == 200

        # Trigger test alert
        r_test = client.post("/api/v1/shops/real_shop/alerts/test")
        assert r_test.status_code == 200
        assert r_test.json()["results"][0]["status"] == "SENT"

        # List and acknowledge alert history
        r_hist = client.get("/api/v1/alerts/history?scenario_tag=real_shop")
        assert r_hist.status_code == 200
        dispatches = r_hist.json()["dispatches"]
        assert len(dispatches) >= 1
        did = dispatches[0]["id"]

        r_ack = client.patch(f"/api/v1/alerts/history/{did}", json={"status": "ACK"})
        assert r_ack.status_code == 200
        assert r_ack.json()["status"] == "ACK"

        # Verify critical reviews filter skips 4-5 star reviews
        db = DatabaseManager(db_path=str(db_file))
        out = notify_critical_reviews(
            db,
            "real_shop",
            [{"review_id": "ok_5", "rating": 5, "text": "Rất tốt"}],
        )
        assert out == []

    @pytest.mark.parametrize(
        "bad_url",
        [
            "http://hooks.example.com/ecom",
            "http://127.0.0.1:8000/api/v1/health",
            "https://169.254.169.254/latest/meta-data/",
            "https://10.0.0.5/internal-hook",
            "https://localhost/hook",
            "https://redis:6379/",
        ],
    )
    def test_ssrf_blocks_internal_and_insecure_webhook_urls(self, tmp_path, monkeypatch, bad_url):
        monkeypatch.setenv("ECOMREVIEW_ENV", "development")
        app = create_app(db_path=str(tmp_path / "ssrf.db"))
        client = TestClient(app)

        r = client.patch(
            "/api/v1/shops/real_shop/alerts",
            json={"webhook_url": bad_url},
        )
        assert r.status_code == 400

        with pytest.raises(ValueError):
            send_webhook_alert(bad_url, {"ping": True})


# CreBy: MenBoyBMN
