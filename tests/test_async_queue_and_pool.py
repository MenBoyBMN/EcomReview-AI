"""Tests for async upload worker, progress tracking, SLA overdue flag, and implemented_at."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from ecomreview.api.auth import hash_password
from ecomreview.api.main import create_app
from ecomreview.api.rate_limit import account_lockout, rate_limiter, tenant_job_quota
from ecomreview.db.database import DatabaseManager
from ecomreview.ingest_service import ingest_review_batch
from ecomreview.jobs import queue_worker
from ecomreview.schemas import Aspect, AspectOpinion, Polarity, ReviewAnalysis


class TestAsyncQueueSlaAndImplemented:
    def test_upload_file_async_mode_completes_and_updates_progress(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ECOMREVIEW_ENV", "development")
        monkeypatch.setenv("ECOMREVIEW_QUEUE_DISABLE", "true")
        db_file = tmp_path / "async_upload.db"
        app = create_app(db_path=str(db_file))
        client = TestClient(app)

        csv_content = (
            "Mã đơn hàng,Số sao,Đánh giá của người mua,Thời gian đánh giá\n"
            "ORD_001,1,Áo mưa bị rách và thấm nước quá tệ,2026-09-01\n"
            "ORD_002,5,Vải dù dày dặn mặc rất vừa vặn và đẹp,2026-09-02\n"
        ).encode("utf-8-sig")

        r_up = client.post(
            "/api/v1/reviews/upload-file",
            data={
                "scenario_tag": "async_shop",
                "analyzer_method": "b1_rule",
                "platform": "shopee",
                "async_mode": "true",
            },
            files={"file": ("shopee_export.csv", csv_content, "text/csv")},
        )
        assert r_up.status_code == 202
        body = r_up.json()
        assert body["status"] == "running"
        assert body["valid_count"] == 2
        job_id = body["job_id"]

        # TestClient runs FastAPI BackgroundTasks before returning, so job should be completed
        r_job = client.get(f"/api/v1/jobs/{job_id}")
        assert r_job.status_code == 200
        job_data = r_job.json()
        assert job_data["status"] == "completed"
        assert job_data["details"]["inserted_count"] == 2

        # Verify SLA overdue flag on old 1-star unanswered review vs 5-star review
        r_revs = client.get("/api/v1/reviews?scenario_tag=async_shop")
        assert r_revs.status_code == 200
        by_id = {r["review_id"]: r for r in r_revs.json()["reviews"]}
        assert by_id["ORD_001"]["sla_overdue"] is True
        assert by_id["ORD_002"]["sla_overdue"] is False

    def test_mark_action_implemented_updates_impact_milestone(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ECOMREVIEW_ENV", "development")
        monkeypatch.setenv("ECOMREVIEW_TRACE_DIR", str(tmp_path / "traces"))
        db_file = tmp_path / "impl_impact.db"
        app = create_app(db_path=str(db_file))
        client = TestClient(app)

        reviews = [
            {
                "review_id": f"imp_{i}",
                "platform": "shopee",
                "rating": 2 if i < 4 else 5,
                "created_at": "2026-09-05" if i < 4 else "2026-09-25",
                "text": (
                    "Áo mưa đi mưa to bị thấm nước đường may"
                    if i < 4
                    else "Áo mưa chống thấm nước rất tốt không còn bị ướt"
                ),
                "opinions": [
                    {
                        "aspect": "WATERPROOF",
                        "polarity": "negative" if i < 4 else "positive",
                        "evidence": "thấm nước",
                    }
                ],
            }
            for i in range(8)
        ]
        assert (
            client.post(
                "/api/v1/reviews/upload",
                json={
                    "scenario_tag": "impl_shop",
                    "analyzer_method": "b1_rule",
                    "reviews": reviews,
                },
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/v1/analyze/run",
                json={"scenario_tag": "impl_shop", "analyzer_method": "b1_rule", "min_n": 3},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/v1/actions/generate",
                json={"scenario_tag": "impl_shop", "min_n": 3, "max_actions": 3},
            ).status_code
            == 200
        )
        actions = client.get("/api/v1/actions?scenario_tag=impl_shop").json()["actions"]
        aid = actions[0]["id"]

        r_impl = client.post(
            f"/api/v1/actions/{aid}/implemented",
            json={"implemented_at": "2026-09-15"},
        )
        assert r_impl.status_code == 200
        assert r_impl.json()["implemented_at"] == "2026-09-15"

        r_imp = client.get(f"/api/v1/actions/{aid}/impact?window_days=20&min_n=2")
        assert r_imp.status_code == 200
        assert r_imp.json()["milestone_date"] == "2026-09-15"

    def test_bulk_upsert_idempotency_and_parallel_ingest_speed(self, tmp_path, monkeypatch):
        db = DatabaseManager(db_path=str(tmp_path / "bulk.db"), db_backend="sqlite")
        records = [
            {
                "review_id": f"blk_{i:04d}",
                "scenario_tag": "bulk_shop",
                "platform": "shopee",
                "shop": "bulk_shop",
                "product": "ao_mua_da_ca",
                "rating": 2 if i % 3 == 0 else 5,
                "text_raw": "Áo mưa bị thấm nước vai" if i % 3 == 0 else "Áo mưa vải dày đẹp",
                "text_norm": "áo mưa bị thấm nước vai" if i % 3 == 0 else "áo mưa vải dày đẹp",
                "source": "bulk_test",
                "overall_sentiment": "negative" if i % 3 == 0 else "positive",
                "informative": True,
                "opinions": [
                    {
                        "aspect": "WATERPROOF" if i % 3 == 0 else "MATERIAL_DURABILITY",
                        "polarity": "negative" if i % 3 == 0 else "positive",
                        "evidence": "thấm nước" if i % 3 == 0 else "vải dày",
                        "evidence_ok": True,
                    }
                ],
                "analyzer_method": "b1_rule",
                "created_at": "2026-11-20",
            }
            for i in range(250)
        ]

        written = db.bulk_upsert_reviews_and_opinions(records, chunk_size=100)
        assert written == 250
        # Re-upserting same records must stay idempotent without duplicating opinions
        db.bulk_upsert_reviews_and_opinions(records, chunk_size=100)
        with db.get_connection(read_only=True) as conn:
            rev_cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM reviews WHERE scenario_tag = 'bulk_shop'"
            ).fetchone()["c"]
            op_cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM opinions WHERE scenario_tag = 'bulk_shop'"
            ).fetchone()["c"]
        assert rev_cnt == 250
        assert op_cnt == 250

        # Parallel analysis speedup check with simulated 40ms LLM latency per review
        class _SlowFakeAnalyzer:
            last_used_fallback = False

            def analyze_review(self, text: str) -> ReviewAnalysis:
                time.sleep(0.04)
                return ReviewAnalysis(
                    overall_sentiment=Polarity.POS,
                    opinions=[
                        AspectOpinion(
                            aspect=Aspect.WATERPROOF,
                            polarity=Polarity.POS,
                            evidence="chống nước",
                        )
                    ],
                    informative=True,
                )

        monkeypatch.setattr("ecomreview.ingest_service.get_analyzer", lambda _: _SlowFakeAnalyzer())
        batch = [
            {
                "review_id": f"par_{i:02d}",
                "platform": "tiktok",
                "rating": 5,
                "text": "Áo mưa chống nước rất tốt",
            }
            for i in range(12)
        ]
        progress_calls = []
        t0 = time.perf_counter()
        res = ingest_review_batch(
            db=db,
            reviews=batch,
            scenario_tag="parallel_shop",
            analyzer_method="a1_gemini_v2",
            progress_callback=lambda done, tot: progress_calls.append((done, tot)),
            max_workers=6,
        )
        elapsed = time.perf_counter() - t0
        assert res["inserted_count"] == 12
        # 12 * 0.04s sequential = 0.48s; with 6 workers should finish well under 0.35s
        assert elapsed < 0.35
        assert progress_calls[-1] == (12, 12)

    def test_priority_queues_tenant_quota_isolation_and_admin_dlq(self, tmp_path, monkeypatch):
        rate_limiter.reset()
        account_lockout.reset()
        tenant_job_quota.reset()

        assert queue_worker.resolve_queue_name("critical") == queue_worker.QUEUE_CRITICAL
        assert queue_worker.resolve_queue_name("default") == queue_worker.QUEUE_DEFAULT
        assert queue_worker.resolve_queue_name("low") == queue_worker.QUEUE_LOW

        mock_queue = MagicMock()
        mock_rq_job = MagicMock()
        mock_rq_job.id = "rq_123"
        mock_queue.enqueue.return_value = mock_rq_job
        requested_queues = []

        def _fake_get_rq(queue_name=queue_worker.DEFAULT_QUEUE_NAME):
            requested_queues.append(queue_name)
            return mock_queue

        monkeypatch.setattr(queue_worker, "_get_rq_queue", _fake_get_rq)
        backend = queue_worker.enqueue_background_job(
            lambda **kw: kw,
            None,
            priority="critical",
            scenario_tag="shop_a",
        )
        assert backend == f"rq:{queue_worker.QUEUE_CRITICAL}:rq_123"
        assert requested_queues == [queue_worker.QUEUE_CRITICAL]
        assert mock_queue.enqueue.called

        # Undo _get_rq_queue mock and test per-tenant quota + DLQ endpoint
        monkeypatch.undo()
        monkeypatch.setenv("ECOMREVIEW_ENV", "production")
        monkeypatch.setenv("ECOMREVIEW_JWT_SECRET", "super-strong-pilot-jwt-secret-key-32bytes")
        monkeypatch.setenv("ECOMREVIEW_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
        monkeypatch.setenv("ECOMREVIEW_CORS_ORIGINS", "https://pilot.ecomreview.vn")
        monkeypatch.setenv("ECOMREVIEW_QUEUE_DISABLE", "true")
        monkeypatch.setenv("ECOMREVIEW_TENANT_MAX_JOBS_PER_MIN", "2")
        monkeypatch.delenv("ECOMREVIEW_API_KEY", raising=False)

        db_file = tmp_path / "quota_dlq.db"
        db = DatabaseManager(db_path=str(db_file), db_backend="sqlite")
        db.create_pilot_shop(slug="shop_a", name="Shop A")
        db.create_pilot_shop(slug="shop_b", name="Shop B")
        db.upsert_user(
            email="admin@ecom.vn",
            password_hash=hash_password("AdminPass123!"),
            full_name="Admin",
            role="admin",
            allowed_shops=["*"],
        )
        db.upsert_user(
            email="owner@ecom.vn",
            password_hash=hash_password("OwnerPass123!"),
            full_name="Owner",
            role="owner",
            allowed_shops=["shop_a", "shop_b"],
        )
        failed_jid = db.log_job_start("marketplace_sync", scenario_tag="shop_a")
        db.log_job_complete(failed_jid, status="failed", details={"error": "Upstream timeout"})

        app = create_app(db_path=str(db_file))
        owner_client = TestClient(app, base_url="https://testserver")
        owner_client.post(
            "/api/v1/auth/login",
            json={"email": "owner@ecom.vn", "password": "OwnerPass123!"},
        )

        # Shop A succeeds twice, 3rd async job hits tenant quota (429) while Shop B still works
        for _ in range(2):
            assert (
                owner_client.post(
                    "/api/v1/analyze/run",
                    json={
                        "scenario_tag": "shop_a",
                        "analyzer_method": "b1_rule",
                        "async_mode": True,
                    },
                ).status_code
                == 202
            )
        assert (
            owner_client.post(
                "/api/v1/analyze/run",
                json={"scenario_tag": "shop_a", "analyzer_method": "b1_rule", "async_mode": True},
            ).status_code
            == 429
        )
        assert (
            owner_client.post(
                "/api/v1/analyze/run",
                json={"scenario_tag": "shop_b", "analyzer_method": "b1_rule", "async_mode": True},
            ).status_code
            == 202
        )

        # DLQ endpoint is admin-only
        assert owner_client.get("/api/v1/admin/jobs/dlq").status_code == 403

        admin_client = TestClient(app, base_url="https://testserver")
        admin_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@ecom.vn", "password": "AdminPass123!"},
        )
        r_dlq = admin_client.get("/api/v1/admin/jobs/dlq")
        assert r_dlq.status_code == 200
        assert any(e["job_id"] == failed_jid for e in r_dlq.json()["entries"])


# CreBy: MenBoyBMN
