"""Integration tests for the 10 FastAPI RESTful endpoints in Week 7."""

from fastapi.testclient import TestClient

from ecomreview.api.main import create_app


class TestEcomReviewAPI:
    """Verify all 10 RESTful endpoints of the EcomReview AI backend."""

    def test_full_10_endpoints_lifecycle(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ECOMREVIEW_TRACE_DIR", str(tmp_path / "traces"))
        db_file = tmp_path / "test_api.db"
        app = create_app(db_path=str(db_file))
        client = TestClient(app)

        # 1. GET /api/v1/health
        r_health = client.get("/api/v1/health")
        assert r_health.status_code == 200
        assert r_health.json()["status"] == "healthy"

        # 2. POST /api/v1/reviews/upload
        upload_payload = {
            "scenario_tag": "api_scen",
            "reviews": [
                {
                    "review_id": f"api_rev_{i:03d}",
                    "platform": "tiktok" if i % 2 == 0 else "shopee",
                    "rating": 2 if i < 6 else 5,
                    "text": (
                        "Áo mưa đi mưa to bị thấm nước ở đường may đáy quần"
                        if i < 6
                        else "Áo mưa vải dù dày dặn màu xanh pastel rất đẹp"
                    ),
                    "overall_sentiment": "negative" if i < 6 else "positive",
                    "opinions": [
                        {
                            "aspect": "WATERPROOF" if i < 6 else "ACCESSIBILITY_DESIGN",
                            "polarity": "negative" if i < 6 else "positive",
                            "evidence": "thấm nước ở đường may"
                            if i < 6
                            else "màu xanh pastel rất đẹp",
                        }
                    ],
                }
                for i in range(10)
            ],
        }
        r_up = client.post("/api/v1/reviews/upload", json=upload_payload)
        assert r_up.status_code == 200
        assert r_up.json()["inserted_count"] == 10
        upload_job_id = r_up.json()["job_id"]

        # 3. POST /api/v1/analyze/run
        r_ana = client.post(
            "/api/v1/analyze/run",
            json={"scenario_tag": "api_scen", "analyzer_method": "b1_rule", "min_n": 3},
        )
        assert r_ana.status_code == 200
        assert r_ana.json()["insights_generated"] >= 1

        # 4. GET /api/v1/jobs/{job_id}
        r_job = client.get(f"/api/v1/jobs/{upload_job_id}")
        assert r_job.status_code == 200
        assert r_job.json()["status"] == "completed"

        # 5. GET /api/v1/stats/overview
        r_stats = client.get("/api/v1/stats/overview?scenario_tag=api_scen&min_n=3")
        assert r_stats.status_code == 200
        stats_data = r_stats.json()
        assert stats_data["total_reviews"] == 10
        assert len(stats_data["negative_ci_95"]) == 2
        assert len(stats_data["aspect_stats"]) >= 1

        # 6. GET /api/v1/insights
        r_ins = client.get("/api/v1/insights?scenario_tag=api_scen")
        assert r_ins.status_code == 200
        assert r_ins.json()["count"] >= 1

        # 7. POST /api/v1/actions/generate
        r_gen = client.post(
            "/api/v1/actions/generate",
            json={"scenario_tag": "api_scen", "min_n": 3, "max_actions": 4},
        )
        assert r_gen.status_code == 200
        gen_data = r_gen.json()
        assert gen_data["final_critic_passed"] is True
        assert gen_data["actions_count"] >= 1

        # 8. GET /api/v1/actions
        r_act = client.get("/api/v1/actions?scenario_tag=api_scen")
        assert r_act.status_code == 200
        actions_list = r_act.json()["actions"]
        assert len(actions_list) >= 1
        first_action_id = actions_list[0]["id"]

        # 9. POST /api/v1/actions/{action_id}/decision (Human-in-the-Loop Edit & Approve)
        r_dec = client.post(
            f"/api/v1/actions/{first_action_id}/decision",
            json={
                "decision": "EDITED",
                "edited_content": (
                    "Gia cố keo ép nhiệt đường may đáy quần và kiểm tra 30 mẫu trong 24h."
                ),
                "note": "Chủ shop duyệt và tăng mẫu QC lên 30.",
            },
        )
        assert r_dec.status_code == 200
        dec_data = r_dec.json()
        assert dec_data["decision"] == "EDITED"
        assert dec_data["edit_distance_chars"] >= 0

        # 10. GET /api/v1/reviews
        r_revs = client.get(
            "/api/v1/reviews?scenario_tag=api_scen&review_ids=api_rev_000,api_rev_001"
        )
        assert r_revs.status_code == 200
        assert r_revs.json()["count"] == 2


# CreBy: MenBoyBMN
