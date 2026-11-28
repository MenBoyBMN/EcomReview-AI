"""Tests for Phase 3A: Multi-industry Playbooks, Alert Formatters/Digest & Pre-aggregation."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import yaml
from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from alembic import command
from ecomreview.agent.critic import HybridCritic
from ecomreview.agent.graph_runner import EcomReviewGraphRunner
from ecomreview.agent.planner import ActionPlanner
from ecomreview.agent.playbook_loader import (
    INDUSTRY_REGISTRY,
    list_industry_templates,
    load_shop_playbook,
    normalize_industry,
    resolve_playbook_path,
)
from ecomreview.agent.reply_assistant import check_reply_guardrails, generate_customer_reply
from ecomreview.agent.tools_aggregator import (
    detect_trend_alerts,
    get_aspect_sentiment_stats,
    get_aspect_trend,
)
from ecomreview.alerts.notifier import dispatch_alert, format_webhook_payload
from ecomreview.api.auth import hash_password
from ecomreview.api.main import create_app
from ecomreview.api.rate_limit import account_lockout, rate_limiter, tenant_job_quota
from ecomreview.db.database import DatabaseManager
from ecomreview.jobs.queue_worker import run_scheduled_weekly_digests
from ecomreview.reporting import build_weekly_digest
from ecomreview.schemas import Aspect


def _setup_3a_app(tmp_path: Path, monkeypatch):
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

    db_file = tmp_path / "phase3a.db"
    db = DatabaseManager(db_path=str(db_file), db_backend="sqlite")
    db.create_pilot_shop(slug="shop_beauty", name="Lumina Beauty", industry="cosmetics")
    db.create_pilot_shop(slug="shop_rain", name="Raincoat VN", industry="raincoat")
    db.upsert_user(
        email="owner@beauty.vn",
        password_hash=hash_password("OwnerPass123!"),
        full_name="Beauty Owner",
        role="owner",
        allowed_shops=["shop_beauty"],
    )
    app = create_app(db_path=str(db_file))
    return app, db


class TestPhase3APlaybooksDigestMetrics:
    def test_all_industry_templates_pass_r1_r7_and_g1_g6(self):
        templates = list_industry_templates()
        assert {t["industry"] for t in templates} == set(INDUSTRY_REGISTRY.keys())
        assert normalize_industry("thoi_trang") == "fashion"
        assert normalize_industry("unknown_vertical") == "raincoat"

        sample_insights = [
            {
                "insight_id": 1,
                "kind": "TOP_PAIN",
                "aspect": "PACKAGING_SHIPPING",
                "statement": "Khía cạnh PACKAGING_SHIPPING có 30.0% đánh giá tiêu cực (6/20).",
                "numbers": {"neg_pct": 30.0, "neg_count": 6, "total": 20},
                "evidence_ids": ["ev1", "ev2"],
                "confidence": "HIGH",
            },
            {
                "insight_id": 2,
                "kind": "TOP_PAIN",
                "aspect": "FIT_SIZE",
                "statement": "Khía cạnh FIT_SIZE có 25.0% đánh giá tiêu cực (5/20).",
                "numbers": {"neg_pct": 25.0, "neg_count": 5, "total": 20},
                "evidence_ids": ["ev3", "ev4"],
                "confidence": "HIGH",
            },
            {
                "insight_id": 3,
                "kind": "STRENGTH",
                "aspect": "ACCESSIBILITY_DESIGN",
                "statement": "Khía cạnh ACCESSIBILITY_DESIGN đạt 85.0% tích cực (17/20).",
                "numbers": {"pos_pct": 85.0, "pos_count": 17, "total": 20},
                "evidence_ids": ["ev5", "ev6"],
                "confidence": "HIGH",
            },
        ]

        for ind in INDUSTRY_REGISTRY:
            pb_path = resolve_playbook_path(ind)
            pb_data = yaml.safe_load(pb_path.read_text(encoding="utf-8")) or {}
            planner = ActionPlanner(industry=ind, use_llm=False)
            critic = HybridCritic(industry=ind)
            proposals = planner.generate_proposals(
                insights=sample_insights,
                fallback_review_ids=["ev1", "ev2", "ev3", "ev4", "ev5", "ev6"],
                max_actions=6,
            )
            assert len(proposals) >= 2
            report = critic.evaluate(
                proposals=proposals,
                insights=sample_insights,
                valid_review_ids={"ev1", "ev2", "ev3", "ev4", "ev5", "ev6"},
            )
            assert report.passed, f"{ind} failed R1-R7: {report.violations}"

            greeting = pb_data["reply_templates"]["greeting"]
            closing = pb_data["reply_templates"]["closing"]
            handlers = pb_data["reply_templates"]["aspect_handlers"]
            for asp in Aspect:
                if asp == Aspect.GENERAL:
                    continue
                msg = f"{greeting} {handlers[asp.value]} {closing}"
                rep = check_reply_guardrails(msg, [asp.value], playbook_path=pb_path)
                assert rep.passed, f"{ind}/{asp.value} failed G1-G6: {rep.violations}"

    def test_shop_profile_api_wires_industry_and_brand_voice(self, tmp_path, monkeypatch):
        app, db = _setup_3a_app(tmp_path, monkeypatch)
        client = TestClient(app, base_url="https://testserver")
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@beauty.vn", "password": "OwnerPass123!"},
        )
        assert login.status_code == 200

        ind_res = client.get("/api/v1/industries")
        assert ind_res.status_code == 200
        assert len(ind_res.json()["industries"]) == 5

        # Update shop profile & brand voice (ensure PII in notes is scrubbed)
        prof_res = client.patch(
            "/api/v1/shops/shop_beauty/profile",
            json={
                "industry": "cosmetics",
                "shop_signature": "Lumina Beauty Official",
                "tone": "Ân cần, chuyên gia da liễu",
                "return_policy": "Hỗ trợ đổi mới miễn phí trong 7 ngày",
                "cskh_notes": "Liên hệ nếu lỗi vòi xịt 0901234567",
                "custom_overclaim_keywords": ["trị nám vĩnh viễn"],
            },
        )
        assert prof_res.status_code == 200
        bv = prof_res.json()["alert_config"]["brand_voice"]
        assert bv["shop_signature"] == "Lumina Beauty Official"
        assert "0901234567" not in bv["cskh_notes"]

        # Seed reviews for shop_beauty to verify GraphRunner & ReplyAssistant use cosmetics/voice
        for i in range(6):
            db.upsert_review_and_opinions(
                review_id=f"cos_{i}",
                platform="shopee",
                shop="shop_beauty",
                product="serum_ha",
                rating=2,
                text_raw="Hộp bị móp và tràn dung dịch khi giao hàng",
                text_norm="hộp bị móp và tràn dung dịch khi giao hàng",
                source="review",
                scenario_tag="shop_beauty",
                overall_sentiment="negative",
                informative=True,
                opinions=[
                    {
                        "aspect": "PACKAGING_SHIPPING",
                        "polarity": "negative",
                        "evidence": "Hộp bị móp và tràn dung dịch khi giao hàng",
                    }
                ],
                created_at="2026-11-20",
            )

        runner = EcomReviewGraphRunner(db=db, trace_dir=tmp_path / "traces", use_llm=False)
        trace = runner.run_scenario("shop_beauty", min_n=3, max_actions=4)
        assert trace["industry"] == "cosmetics"
        assert trace["final_critic_passed"] is True
        assert any(
            "xốp" in a["title"].lower() or "tràn" in a["title"].lower() for a in trace["actions"]
        )

        reply = generate_customer_reply("cos_0", scenario_tag="shop_beauty", mode="template", db=db)
        assert "Lumina Beauty Official" in reply["reply_text"]
        assert "Hỗ trợ đổi mới miễn phí trong 7 ngày" in reply["reply_text"]
        assert reply["guardrail_report"]["passed"] is True

        # Custom overclaim keyword should be enforced for shop_beauty
        pb_loaded = load_shop_playbook(db=db, scenario_tag="shop_beauty")
        oc_report = check_reply_guardrails(
            "Dạ Lumina Beauty đảm bảo trị nám vĩnh viễn cho Quý khách với đóng gói giao hàng kỹ.",
            negative_aspects=["PACKAGING_SHIPPING"],
            playbook_path=pb_loaded["_resolved_path"],
            extra_overclaim_keywords=pb_loaded["shop_profile"]["brand_voice"][
                "custom_overclaim_keywords"
            ],
        )
        assert oc_report.passed is False
        assert any("G1" in v for v in oc_report.violations)

    def test_webhook_formatters_weekly_digest_and_dedup(self, tmp_path, monkeypatch):
        slack_body = format_webhook_payload(
            "slack",
            scenario_tag="shop_beauty",
            shop_name="Lumina",
            severity="HIGH",
            title="Cảnh báo 1★",
            clean_message="Khách 0912345678 chê rò nước",
            payload={"k": 1},
        )
        assert "blocks" in slack_body and "0912345678" not in slack_body["text"]

        lark_body = format_webhook_payload(
            "lark",
            scenario_tag="shop_beauty",
            shop_name="Lumina",
            severity="MEDIUM",
            title="Test Lark",
            clean_message="Nội dung cảnh báo",
            payload={},
        )
        assert lark_body["msg_type"] == "interactive"

        zalo_body = format_webhook_payload(
            "zalo_oa",
            scenario_tag="shop_beauty",
            shop_name="Lumina",
            severity="INFO",
            title="Digest",
            clean_message="Báo cáo tuần",
            payload={"total": 10},
            recipient_id="uid_999",
        )
        assert zalo_body["event_name"] == "ecomreview_alert"
        assert zalo_body["recipient"]["user_id"] == "uid_999"

        app, db = _setup_3a_app(tmp_path, monkeypatch)
        db.upsert_review_and_opinions(
            review_id="d1",
            platform="shopee",
            shop="shop_beauty",
            product="serum_ha",
            rating=2,
            text_raw="Giao hàng hơi chậm và móp hộp",
            text_norm="giao hàng hơi chậm và móp hộp",
            source="review",
            scenario_tag="shop_beauty",
            overall_sentiment="negative",
            informative=True,
            opinions=[
                {
                    "aspect": "PACKAGING_SHIPPING",
                    "polarity": "negative",
                    "evidence": "móp hộp",
                }
            ],
            created_at="2026-11-23",
        )

        client = TestClient(app, base_url="https://testserver")
        client.post(
            "/api/v1/auth/login",
            json={"email": "owner@beauty.vn", "password": "OwnerPass123!"},
        )
        wh_patch = client.patch(
            "/api/v1/shops/shop_beauty/alerts",
            json={
                "webhook_url": "https://93.184.216.34/hooks/lark",
                "webhook_format": "lark",
                "weekly_digest_enabled": True,
                "min_rating_alert": 2,
            },
        )
        assert wh_patch.status_code == 200

        digest = build_weekly_digest("shop_beauty", db=db, as_of="2026-11-23")
        assert digest["week_key"] == "2026-W48"
        assert digest["metrics"]["total_reviews"] == 1
        assert "1/1" not in digest["message_text"] or digest["metrics"]["low_star_sent"] == 0

        captured_payloads = []
        with patch("ecomreview.alerts.notifier.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.raise_for_status = lambda: None
            mock_post.side_effect = lambda url, data=None, **kw: (
                captured_payloads.append(data),
                mock_post.return_value,
            )[1]

            send_res = client.post("/api/v1/shops/shop_beauty/digest/send")
            assert send_res.status_code == 200
            assert send_res.json()["dispatches"][0]["status"] == "SENT"
            assert len(captured_payloads) == 1
            assert b'"msg_type": "interactive"' in captured_payloads[0]

            # Scheduled Monday 09:00 ICT on same week should deduplicate cleanly
            monday_09_ict_utc = datetime(2026, 11, 23, 2, 0, tzinfo=timezone.utc)
            sched_res = run_scheduled_weekly_digests(
                db_path=str(db.db_path), now_utc=monday_09_ict_utc
            )
            assert sched_res == []

            # Next Monday 09:00 ICT (2026-W49) should trigger exactly once
            next_monday_utc = datetime(2026, 11, 30, 2, 0, tzinfo=timezone.utc)
            sched_next = run_scheduled_weekly_digests(
                db_path=str(db.db_path), now_utc=next_monday_utc
            )
            assert len(sched_next) == 1
            assert sched_next[0]["week_key"] == "2026-W49"

        # Invalid webhook format rejected with 400
        bad_fmt = client.patch(
            "/api/v1/shops/shop_beauty/alerts",
            json={"webhook_format": "unknown_fmt"},
        )
        assert bad_fmt.status_code == 400

        # Direct dispatch_alert checks dedup
        dup_call = dispatch_alert(
            db=db,
            scenario_tag="shop_beauty",
            dedup_key=f"weekly_digest:shop_beauty:{digest['week_key']}",
            severity="INFO",
            title="Dup",
            message_text="Dup",
            payload={},
        )
        assert dup_call[0]["status"] == "skipped_duplicate"

    def test_alembic_0006_and_daily_aspect_metrics_zero_drift(self, tmp_path, monkeypatch):
        db_file = tmp_path / "alembic_0006.db"
        monkeypatch.setenv("ECOMREVIEW_DB_BACKEND", "sqlite")
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")

        repo_root = Path(__file__).resolve().parents[1]
        cfg = Config(str(repo_root / "alembic.ini"))
        cfg.set_main_option("script_location", str(repo_root / "alembic"))
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file.as_posix()}")
        command.upgrade(cfg, "head")

        with sqlite3.connect(db_file) as conn:
            rev_cols = {r[1] for r in conn.execute("PRAGMA table_info(reviews)").fetchall()}
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "created_at_ts" in rev_cols
        assert "daily_aspect_metrics" in tables

        db = DatabaseManager(db_path=str(db_file), db_backend="sqlite")
        records = []
        for idx in range(10):
            records.append(
                {
                    "review_id": f"m_{idx}",
                    "scenario_tag": "shop_metrics",
                    "platform": "shopee" if idx % 2 == 0 else "tiktok",
                    "shop": "shop_metrics",
                    "product": "ao_mua_a",
                    "rating": 2 if idx >= 6 else 5,
                    "text_raw": "Thấm nước" if idx >= 6 else "Rất tốt",
                    "text_norm": "thấm nước" if idx >= 6 else "rất tốt",
                    "source": "review",
                    "overall_sentiment": "negative" if idx >= 6 else "positive",
                    "informative": True,
                    "created_at": "2026-10-10" if idx < 5 else "2026-11-10",
                    "opinions": [
                        {
                            "aspect": "WATERPROOF",
                            "polarity": "negative" if idx >= 6 else "positive",
                            "evidence": "Thấm nước" if idx >= 6 else "Rất tốt",
                            "evidence_ok": True,
                        }
                    ],
                }
            )
        db.bulk_upsert_reviews_and_opinions(records, chunk_size=5)

        pre_stats = get_aspect_sentiment_stats("shop_metrics", min_n=1, db=db)
        pre_trend = get_aspect_trend("shop_metrics", aspect="WATERPROOF", min_n=1, db=db)
        pre_alerts = detect_trend_alerts("shop_metrics", min_n=5, db=db)

        # Idempotent re-upsert + date move check (must not double-count or leave stale dates)
        db.upsert_review_and_opinions(
            review_id="m_0",
            platform="shopee",
            shop="shop_metrics",
            product="ao_mua_a",
            rating=5,
            text_raw="Rất tốt",
            text_norm="rất tốt",
            source="review",
            scenario_tag="shop_metrics",
            overall_sentiment="positive",
            informative=True,
            opinions=[{"aspect": "WATERPROOF", "polarity": "positive", "evidence": "Rất tốt"}],
            created_at="2026-10-10",
        )
        assert get_aspect_sentiment_stats("shop_metrics", min_n=1, db=db) == pre_stats
        assert get_aspect_trend("shop_metrics", aspect="WATERPROOF", min_n=1, db=db) == pre_trend

        # Clear daily_aspect_metrics to verify raw fallback produces bit-for-bit identical output
        with db.get_connection(read_only=False) as conn:
            conn.execute("DELETE FROM daily_aspect_metrics WHERE scenario_tag = 'shop_metrics'")
        raw_stats = get_aspect_sentiment_stats("shop_metrics", min_n=1, db=db)
        raw_trend = get_aspect_trend("shop_metrics", aspect="WATERPROOF", min_n=1, db=db)
        raw_alerts = detect_trend_alerts("shop_metrics", min_n=5, db=db)

        assert pre_stats == raw_stats
        assert pre_trend == raw_trend
        assert pre_alerts == raw_alerts

        # Backfill restores daily_aspect_metrics cleanly
        summary = db.backfill_daily_aspect_metrics(scenario_tag="shop_metrics")
        assert summary["daily_metric_rows"] > 0
        assert get_aspect_sentiment_stats("shop_metrics", min_n=1, db=db) == raw_stats


# CreBy: MenBoyBMN
