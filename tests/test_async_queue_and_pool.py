"""Tests for async upload worker, progress tracking, SLA overdue flag, and implemented_at."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ecomreview.api.main import create_app


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


# CreBy: MenBoyBMN
