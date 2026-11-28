"""Tests for Seller Center CSV/XLSX aliases, HMAC webhook ingest, and Marketplace connectors."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from ecomreview.api.main import create_app
from ecomreview.api.rate_limit import rate_limiter, webhook_replay_guard
from ecomreview.connectors.shopee import ShopeeConnector
from ecomreview.connectors.tiktok import TikTokShopConnector
from ecomreview.db.database import DatabaseManager
from ecomreview.ingest_service import parse_review_file


class TestSellerBridgeAndConnectors:
    def test_parse_shopee_and_tiktok_seller_center_columns(self):
        shopee_csv = (
            "Order SN,Product Name,Buyer Rating,Buyer Comment,Review Time\n"
            "261123ABC,Áo mưa bộ vải dù,2,Đi mưa to bị thấm nước phần cổ áo,2026-11-20 14:22:10\n"
        ).encode("utf-8-sig")
        valid, skipped = parse_review_file("shopee.csv", shopee_csv, default_platform="shopee")
        assert len(valid) == 1
        assert skipped == []
        assert valid[0]["review_id"] == "261123ABC"
        assert valid[0]["product"] == "Áo mưa bộ vải dù"
        assert valid[0]["rating"] == 2
        assert valid[0]["created_at"] == "2026-11-20"

        tiktok_csv = (
            "Mã đơn hàng,Phân loại hàng,Điểm đánh giá,Đánh giá của người mua,Thời gian đánh giá\n"
            "TTK_998,Size XL Xanh Navy,5,Giao nhanh vải dày đẹp lắm,2026-11-21\n"
        ).encode("utf-8-sig")
        valid_t, skipped_t = parse_review_file("tiktok.csv", tiktok_csv, default_platform="tiktok")
        assert len(valid_t) == 1
        assert skipped_t == []
        assert valid_t[0]["review_id"] == "TTK_998"
        assert valid_t[0]["product"] == "Size XL Xanh Navy"
        assert valid_t[0]["rating"] == 5

    def test_hmac_webhook_ingest_verifies_signature_and_ingests(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ECOMREVIEW_ENV", "development")
        monkeypatch.setenv("ECOMREVIEW_QUEUE_DISABLE", "true")
        db_file = tmp_path / "webhook.db"
        db = DatabaseManager(db_path=str(db_file))
        shop = db.create_pilot_shop(slug="shop_hook", name="Shop Webhook")

        app = create_app(db_path=str(db_file))
        client = TestClient(app)

        payload_bytes = json.dumps(
            {
                "analyzer_method": "b1_rule",
                "reviews": [
                    {
                        "review_id": "wh_001",
                        "platform": "shopee",
                        "rating": 2,
                        "text": "Áo mưa mặc bị thấm nước ở vai",
                        "created_at": "2026-11-22",
                    }
                ],
            },
            ensure_ascii=False,
        ).encode("utf-8")

        # Invalid signature -> 401
        r_bad = client.post(
            "/api/v1/integrations/webhook/shop_hook",
            content=payload_bytes,
            headers={"Content-Type": "application/json", "X-EcomReview-Signature": "bad_sig"},
        )
        assert r_bad.status_code == 401

        # Valid HMAC signature -> 202 Accepted and review ingested
        good_sig = hmac.new(
            shop["webhook_secret"].encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        r_ok = client.post(
            "/api/v1/integrations/webhook/shop_hook",
            content=payload_bytes,
            headers={"Content-Type": "application/json", "X-EcomReview-Signature": good_sig},
        )
        assert r_ok.status_code == 202
        job_id = r_ok.json()["job_id"]
        assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "completed"

    def test_marketplace_connector_signing_helpers(self):
        shp = ShopeeConnector(
            partner_id="10001",
            partner_key="secret_key",
            shop_id="20002",
            access_token="tok_abc",
        )
        assert shp.is_configured() is True
        sig_shp = shp.sign_request("/api/v2/product/get_comment", 1700000000)
        assert len(sig_shp) == 64

        ttk = TikTokShopConnector(
            app_key="app_1",
            app_secret="sec_1",
            shop_cipher="cipher_1",
            access_token="tok_1",
        )
        assert ttk.is_configured() is True
        sig_ttk = ttk.sign_request(
            "/product/202309/reviews", {"app_key": "app_1", "timestamp": "1"}
        )
        assert len(sig_ttk) == 64

    def test_webhook_replay_protection_and_timestamp_window_in_production(
        self, tmp_path, monkeypatch
    ):
        rate_limiter.reset()
        webhook_replay_guard.reset()
        monkeypatch.setenv("ECOMREVIEW_ENV", "production")
        monkeypatch.setenv("ECOMREVIEW_JWT_SECRET", "super-strong-pilot-jwt-secret-key-32bytes")
        monkeypatch.setenv("ECOMREVIEW_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
        monkeypatch.setenv("ECOMREVIEW_CORS_ORIGINS", "https://pilot.ecomreview.vn")
        monkeypatch.setenv("ECOMREVIEW_QUEUE_DISABLE", "true")

        db_file = tmp_path / "webhook_prod.db"
        db = DatabaseManager(db_path=str(db_file))
        shop = db.create_pilot_shop(slug="shop_prod_wh", name="Shop Prod Webhook")
        app = create_app(db_path=str(db_file))
        client = TestClient(app, base_url="https://testserver")

        payload_bytes = json.dumps(
            {
                "analyzer_method": "b1_rule",
                "reviews": [
                    {
                        "review_id": "wh_prod_1",
                        "platform": "tiktok",
                        "rating": 2,
                        "text": "Áo mưa bị rách đường may vai",
                        "created_at": "2026-11-23",
                    }
                ],
            },
            ensure_ascii=False,
        ).encode("utf-8")

        # Production rejects unsigned/missing timestamp
        legacy_sig = hmac.new(
            shop["webhook_secret"].encode("utf-8"), payload_bytes, hashlib.sha256
        ).hexdigest()
        r_no_ts = client.post(
            "/api/v1/integrations/webhook/shop_prod_wh",
            content=payload_bytes,
            headers={"Content-Type": "application/json", "X-EcomReview-Signature": legacy_sig},
        )
        assert r_no_ts.status_code == 401

        # Expired timestamp (> 5 mins) -> 401
        stale_ts = str(int(time.time()) - 400)
        stale_sig = hmac.new(
            shop["webhook_secret"].encode("utf-8"),
            f"{stale_ts}.".encode("utf-8") + payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        r_stale = client.post(
            "/api/v1/integrations/webhook/shop_prod_wh",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-EcomReview-Timestamp": stale_ts,
                "X-EcomReview-Signature": stale_sig,
            },
        )
        assert r_stale.status_code == 401

        # Fresh timestamp + valid signature -> 202, immediate replay -> 409
        fresh_ts = str(int(time.time()))
        fresh_sig = hmac.new(
            shop["webhook_secret"].encode("utf-8"),
            f"{fresh_ts}.".encode("utf-8") + payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-EcomReview-Timestamp": fresh_ts,
            "X-EcomReview-Nonce": "nonce-abc-1",
            "X-EcomReview-Signature": fresh_sig,
        }
        r_first = client.post(
            "/api/v1/integrations/webhook/shop_prod_wh",
            content=payload_bytes,
            headers=headers,
        )
        assert r_first.status_code == 202

        r_replay = client.post(
            "/api/v1/integrations/webhook/shop_prod_wh",
            content=payload_bytes,
            headers=headers,
        )
        assert r_replay.status_code == 409


# CreBy: MenBoyBMN
