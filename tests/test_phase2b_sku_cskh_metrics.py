"""Tests for Phase 2B: SKU/variation breakdown, anomalies, 5-star auto-reply & metrics."""

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
from ecomreview.db.database import DatabaseManager
from ecomreview.ingest_service import detect_review_anomalies, parse_review_file


def _setup_2b_app(tmp_path: Path, monkeypatch):
    rate_limiter.reset()
    account_lockout.reset()
    tenant_job_quota.reset()
    monkeypatch.setenv("ECOMREVIEW_ENV", "production")
    monkeypatch.setenv("ECOMREVIEW_JWT_SECRET", "super-strong-pilot-jwt-secret-key-32bytes")
    monkeypatch.setenv("ECOMREVIEW_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("ECOMREVIEW_CORS_ORIGINS", "https://pilot.ecomreview.vn")
    monkeypatch.setenv("ECOMREVIEW_TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.setenv("ECOMREVIEW_QUEUE_DISABLE", "true")
    monkeypatch.delenv("ECOMREVIEW_API_KEY", raising=False)

    db_file = tmp_path / "phase2b.db"
    db = DatabaseManager(db_path=str(db_file), db_backend="sqlite")
    db.create_pilot_shop(slug="shop_sku", name="Shop SKU")
    db.create_pilot_shop(slug="shop_other", name="Shop Other")
    db.upsert_user(
        email="owner@sku.vn",
        password_hash=hash_password("OwnerPass123!"),
        full_name="Owner SKU",
        role="owner",
        allowed_shops=["shop_sku"],
    )
    app = create_app(db_path=str(db_file))
    return app, db


class TestPhase2BSkuCskhMetrics:
    def test_alembic_0005_adds_variation_and_anomaly_columns(self, tmp_path, monkeypatch):
        db_file = tmp_path / "alembic_0005.db"
        monkeypatch.setenv("ECOMREVIEW_DB_BACKEND", "sqlite")
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")

        repo_root = Path(__file__).resolve().parents[1]
        cfg = Config(str(repo_root / "alembic.ini"))
        cfg.set_main_option("script_location", str(repo_root / "alembic"))
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file.as_posix()}")
        command.upgrade(cfg, "head")

        with sqlite3.connect(db_file) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(reviews)").fetchall()}
        assert {"variation", "anomaly_flags"}.issubset(cols)

    def test_variation_parse_anomaly_flags_and_sku_breakdown_endpoint(self, tmp_path, monkeypatch):
        csv_bytes = (
            "Order SN,Product Name,Variation,Buyer Rating,Buyer Comment,Review Time\n"
            "S1,Áo mưa bộ,Size XL Đen,1,Thấm nước ở vai,2026-11-20\n"
            "S2,Áo mưa bộ,Size XL Đen,2,Rách đường may đáy quần,2026-11-20\n"
            "S3,Áo mưa bộ,Size L Xanh,5,Vải dày dặn đẹp lắm,2026-11-20\n"
            "S4,Áo mưa bộ,Size L Xanh,5,Áo mưa mặc rất vừa vặn và mát,2026-11-20\n"
        ).encode("utf-8-sig")
        valid, skipped = parse_review_file("sku.csv", csv_bytes, default_platform="shopee")
        assert len(valid) == 4
        assert skipped == []
        assert valid[0]["product"] == "Áo mưa bộ"
        assert valid[0]["variation"] == "Size XL Đen"

        # Verify anomaly detector rules
        assert "SPAM_REPEATED_CHARS" in detect_review_anomalies("aaaaaaa bbb", "aaaaaaa bbb", 5, [])
        assert "SEEDING_DUPLICATE" in detect_review_anomalies(
            "Sản phẩm rất tốt giao hàng nhanh chóng",
            "sản phẩm rất tốt giao hàng nhanh chóng",
            5,
            [],
            dup_count=3,
        )
        assert "HIDDEN_COMPLAINT" in detect_review_anomalies(
            "Đẹp nhưng hơi thấm nước",
            "đẹp nhưng hơi thấm nước",
            5,
            [{"aspect": "WATERPROOF", "polarity": "negative"}],
        )

        app, _ = _setup_2b_app(tmp_path, monkeypatch)
        client = TestClient(app, base_url="https://testserver")
        client.post(
            "/api/v1/auth/login",
            json={"email": "owner@sku.vn", "password": "OwnerPass123!"},
        )

        upload_payload = {
            "scenario_tag": "shop_sku",
            "analyzer_method": "b1_rule",
            "reviews": [
                {
                    "review_id": "v1",
                    "platform": "shopee",
                    "product": "ao_mua_bo",
                    "variation": "Size XL Đen",
                    "rating": 1,
                    "text": "Áo mưa bị thấm nước ở đường may vai",
                    "opinions": [
                        {"aspect": "WATERPROOF", "polarity": "negative", "evidence": "thấm nước"}
                    ],
                },
                {
                    "review_id": "v2",
                    "platform": "shopee",
                    "product": "ao_mua_bo",
                    "variation": "Size XL Đen",
                    "rating": 2,
                    "text": "Đường may thấm nước khi đi mưa to",
                    "opinions": [
                        {"aspect": "WATERPROOF", "polarity": "negative", "evidence": "thấm nước"}
                    ],
                },
                {
                    "review_id": "v3",
                    "platform": "shopee",
                    "product": "ao_mua_bo",
                    "variation": "Size L Xanh",
                    "rating": 5,
                    "text": "aaaaaaaaa 1111111111111",
                    "opinions": [],
                },
                {
                    "review_id": "v4",
                    "platform": "shopee",
                    "product": "ao_mua_bo",
                    "variation": "Size L Xanh",
                    "rating": 5,
                    "text": "Vải dày đẹp nhưng hơi thấm nước cổ áo",
                    "opinions": [
                        {"aspect": "WATERPROOF", "polarity": "negative", "evidence": "thấm nước"}
                    ],
                },
            ],
        }
        assert client.post("/api/v1/reviews/upload", json=upload_payload).status_code == 200

        r_sku = client.get("/api/v1/stats/sku-breakdown?scenario_tag=shop_sku&min_n=2")
        assert r_sku.status_code == 200
        items = r_sku.json()["items"]
        assert items[0]["variation"] == "Size XL Đen"
        assert items[0]["negative_rate_pct"] == 100.0
        assert items[0]["top_negative_aspect"] == "WATERPROOF"

        # Anomaly filter on reviews endpoint
        r_anom = client.get("/api/v1/reviews?scenario_tag=shop_sku&anomaly_only=true")
        assert r_anom.status_code == 200
        anom_map = {r["review_id"]: r["anomaly_flags"] for r in r_anom.json()["reviews"]}
        assert "SPAM_REPEATED_CHARS" in anom_map["v3"]
        assert "HIDDEN_COMPLAINT" in anom_map["v4"]

    def test_auto_reply_5star_skips_hidden_complaints_and_bulk_cskh_enforces_tenant(
        self, tmp_path, monkeypatch
    ):
        app, db = _setup_2b_app(tmp_path, monkeypatch)
        client = TestClient(app, base_url="https://testserver")
        client.post(
            "/api/v1/auth/login",
            json={"email": "owner@sku.vn", "password": "OwnerPass123!"},
        )

        # Clean 5-star, hidden-complaint 5-star, and negative 2-star
        db.upsert_review_and_opinions(
            review_id="c5_clean",
            platform="shopee",
            shop="shop_sku",
            product="ao_mua",
            rating=5,
            text_raw="Áo mưa rất đẹp và chắc chắn",
            text_norm="áo mưa rất đẹp và chắc chắn",
            source="test",
            scenario_tag="shop_sku",
            overall_sentiment="positive",
            informative=True,
            opinions=[
                {"aspect": "MATERIAL_DURABILITY", "polarity": "positive", "evidence": "chắc chắn"}
            ],
        )
        db.upsert_review_and_opinions(
            review_id="c5_hidden",
            platform="shopee",
            shop="shop_sku",
            product="ao_mua",
            rating=5,
            text_raw="Giao nhanh nhưng bị thấm nước nhẹ",
            text_norm="giao nhanh nhưng bị thấm nước nhẹ",
            source="test",
            scenario_tag="shop_sku",
            overall_sentiment="positive",
            informative=True,
            opinions=[{"aspect": "WATERPROOF", "polarity": "negative", "evidence": "thấm nước"}],
            anomaly_flags=["HIDDEN_COMPLAINT"],
        )
        db.upsert_review_and_opinions(
            review_id="c2_neg",
            platform="shopee",
            shop="shop_sku",
            product="ao_mua",
            rating=2,
            text_raw="Áo mưa bị thấm nước ở vai",
            text_norm="áo mưa bị thấm nước ở vai",
            source="test",
            scenario_tag="shop_sku",
            overall_sentiment="negative",
            informative=True,
            opinions=[{"aspect": "WATERPROOF", "polarity": "negative", "evidence": "thấm nước"}],
        )

        # Auto-reply 5-star only replies c5_clean, skips c5_hidden
        r_auto = client.post(
            "/api/v1/reviews/auto-reply-5star",
            json={"scenario_tag": "shop_sku", "push_to_marketplace": False},
        )
        assert r_auto.status_code == 200
        assert r_auto.json()["replied_count"] == 1
        assert r_auto.json()["skipped_count"] == 1

        # Second run is idempotent -> 0 new replies
        r_auto2 = client.post(
            "/api/v1/reviews/auto-reply-5star",
            json={"scenario_tag": "shop_sku", "push_to_marketplace": False},
        )
        assert r_auto2.json()["replied_count"] == 0

        # Bulk draft & bulk send on remaining reviews
        r_bd = client.post(
            "/api/v1/reviews/bulk-reply-draft",
            json={"scenario_tag": "shop_sku", "review_ids": ["c5_hidden", "c2_neg"]},
        )
        assert r_bd.status_code == 200
        assert r_bd.json()["created_count"] == 2
        rep_ids = [d["reply_id"] for d in r_bd.json()["drafts"]]

        r_bs = client.post(
            "/api/v1/reviews/replies/bulk-status",
            json={
                "scenario_tag": "shop_sku",
                "reply_ids": rep_ids,
                "status": "SENT",
                "push_to_marketplace": False,
            },
        )
        assert r_bs.status_code == 200
        assert r_bs.json()["updated_count"] == 2

        # Cross-shop IDOR on bulk-status is blocked (403)
        other_rep_id = db.insert_review_reply(
            review_id="c2_neg",
            scenario_tag="shop_sku",
            reply_text="Dạ shop hỗ trợ đổi trả sản phẩm lỗi chống thấm ạ.",
        )
        db.upsert_review_and_opinions(
            review_id="other_r1",
            platform="shopee",
            shop="shop_other",
            product="ao_mua",
            rating=2,
            text_raw="Thấm nước",
            text_norm="thấm nước",
            source="test",
            scenario_tag="shop_other",
            overall_sentiment="negative",
            informative=True,
            opinions=[],
        )
        other_shop_rep = db.insert_review_reply(
            review_id="other_r1",
            scenario_tag="shop_other",
            reply_text="Dạ shop hỗ trợ đổi trả sản phẩm qua kênh chat sàn ạ.",
        )
        r_idor = client.post(
            "/api/v1/reviews/replies/bulk-status",
            json={
                "scenario_tag": "shop_sku",
                "reply_ids": [other_rep_id, other_shop_rep],
                "status": "APPROVED",
            },
        )
        assert r_idor.status_code == 403

    def test_prometheus_metrics_token_guard_and_deep_health(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ECOMREVIEW_METRICS_TOKEN", "prom_secret_tok_99")
        app, _ = _setup_2b_app(tmp_path, monkeypatch)
        client = TestClient(app, base_url="https://testserver")

        r_health = client.get("/api/v1/health")
        assert r_health.status_code == 200
        h_json = r_health.json()
        assert h_json["endpoints_count"] == 15
        assert h_json["components"]["database"]["status"] == "up"
        assert "redis" in h_json["components"]

        # Without token -> 403; with valid token -> Prometheus exposition text
        assert client.get("/metrics").status_code == 403
        r_met = client.get("/metrics", headers={"X-Metrics-Token": "prom_secret_tok_99"})
        assert r_met.status_code == 200
        assert "ecomreview_http_requests_total" in r_met.text
        assert "ecomreview_absa_cache_events_total" in r_met.text


# CreBy: MenBoyBMN
