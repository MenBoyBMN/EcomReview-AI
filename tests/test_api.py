"""Integration tests for all 15 FastAPI RESTful endpoints."""

from fastapi.testclient import TestClient

from ecomreview.api.main import create_app


class TestEcomReviewAPI:
    """Verify all 15 RESTful endpoints, async jobs, and security boundaries."""

    def test_full_15_endpoints_lifecycle(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ECOMREVIEW_TRACE_DIR", str(tmp_path / "traces"))
        db_file = tmp_path / "test_api.db"
        app = create_app(db_path=str(db_file))
        client = TestClient(app)

        # 1. GET /api/v1/health
        r_health = client.get("/api/v1/health")
        assert r_health.status_code == 200
        assert r_health.json()["status"] == "healthy"
        assert r_health.json()["endpoints_count"] == 15
        assert r_health.json()["extended_endpoints_count"] == 18

        # 2. POST /api/v1/reviews/upload
        upload_payload = {
            "scenario_tag": "api_scen",
            "analyzer_method": "b1_rule",
            "reviews": [
                {
                    "review_id": f"api_rev_{i:03d}",
                    "platform": "tiktok" if i % 2 == 0 else "shopee",
                    "rating": 2 if i < 6 else 5,
                    "created_at": f"2026-09-{10 + i:02d}",
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

        # 3. POST /api/v1/analyze/run (sync mode)
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
        assert "platform_comparison" in stats_data

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

        # 9. POST /api/v1/actions/{action_id}/decision (with X-Reviewer header)
        r_dec = client.post(
            f"/api/v1/actions/{first_action_id}/decision",
            headers={"X-Reviewer": "reviewer_lead"},
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
        assert dec_data["decided_by"] == "reviewer_lead"

        # 10. GET /api/v1/reviews
        r_revs = client.get(
            "/api/v1/reviews?scenario_tag=api_scen&review_ids=api_rev_000,api_rev_001"
        )
        assert r_revs.status_code == 200
        assert r_revs.json()["count"] == 2

        # 10b. GET /api/v1/reviews with pagination (limit + offset)
        r_page = client.get("/api/v1/reviews?scenario_tag=api_scen&limit=3&offset=2")
        assert r_page.status_code == 200
        assert r_page.json()["count"] == 3

        # 11. GET /api/v1/trends
        r_trends = client.get("/api/v1/trends?scenario_tag=api_scen&period=month&min_n=1")
        assert r_trends.status_code == 200
        assert "trends" in r_trends.json()

        # 12. GET /api/v1/alerts
        r_alerts = client.get("/api/v1/alerts?scenario_tag=api_scen&period=month")
        assert r_alerts.status_code == 200
        assert "alerts" in r_alerts.json()

        # 13. POST /api/v1/reviews/{review_id}/reply-draft
        r_reply = client.post(
            "/api/v1/reviews/api_rev_000/reply-draft?scenario_tag=api_scen&mode=template"
        )
        assert r_reply.status_code == 200
        assert r_reply.json()["guardrail_report"]["passed"]

        # 14. GET /api/v1/actions/{action_id}/impact
        r_imp = client.get(f"/api/v1/actions/{first_action_id}/impact")
        assert r_imp.status_code == 200
        assert "status" in r_imp.json()

        # 15. GET /api/v1/reports/export (Excel & HTML)
        r_exp_xlsx = client.get("/api/v1/reports/export?scenario_tag=api_scen&format=xlsx")
        assert r_exp_xlsx.status_code == 200
        assert len(r_exp_xlsx.content) > 1000

        r_exp_html = client.get("/api/v1/reports/export?scenario_tag=api_scen&format=html")
        assert r_exp_html.status_code == 200
        assert "<!DOCTYPE html>" in r_exp_html.text

    def test_async_analysis_mode_returns_202(self, tmp_path, monkeypatch):
        """Verify analyze/run with async_mode=True returns HTTP 202."""
        monkeypatch.setenv("ECOMREVIEW_TRACE_DIR", str(tmp_path / "traces"))
        db_file = tmp_path / "test_async.db"
        app = create_app(db_path=str(db_file))
        client = TestClient(app)

        r = client.post(
            "/api/v1/analyze/run",
            json={"scenario_tag": "async_scen", "analyzer_method": "b1_rule", "async_mode": True},
        )
        assert r.status_code == 202
        data = r.json()
        assert data["status"] == "running"
        assert "job_id" in data

    def test_api_key_authentication_enforcement(self, tmp_path, monkeypatch):
        """Verify 401 when API key is set and missing/wrong, 200 when valid."""
        monkeypatch.setenv("ECOMREVIEW_API_KEY", "secret_token_123")
        db_file = tmp_path / "test_auth.db"
        app = create_app(db_path=str(db_file))
        client = TestClient(app)

        # Health is public
        assert client.get("/api/v1/health").status_code == 200

        # Protected route without key -> 401
        assert client.get("/api/v1/insights").status_code == 401

        # Protected route with wrong key -> 401
        assert client.get("/api/v1/insights", headers={"X-API-Key": "wrong_key"}).status_code == 401

        # Protected route with valid key -> 200
        r_ok = client.get("/api/v1/insights", headers={"X-API-Key": "secret_token_123"})
        assert r_ok.status_code == 200

    def test_upload_file_csv_xlsx_pagination_and_replies_history(self, tmp_path, monkeypatch):
        """Verify CSV/XLSX batch upload, total_count pagination, and reply_status persistence."""
        import io

        import openpyxl

        monkeypatch.setenv("ECOMREVIEW_TRACE_DIR", str(tmp_path / "traces"))
        db_file = tmp_path / "test_upload_file.db"
        app = create_app(db_path=str(db_file))
        client = TestClient(app)

        # 1. CSV upload with Vietnamese headers, BOM, PII, and 1 bad row
        csv_content = (
            "\ufeffmã đơn hàng,số sao,bình luận,sàn\n"
            "csv_001,2,Áo mưa bị thấm nước gọi mình 0912345678 nhé,shopee\n"
            "csv_002,5,Vải dày dặn đẹp lắm shop ơi,tiktok\n"
            "csv_bad,9,Rating ngoài phạm vi sẽ bị bỏ qua,shopee\n"
        ).encode("utf-8")
        r_csv = client.post(
            "/api/v1/reviews/upload-file",
            data={"scenario_tag": "file_scen", "analyzer_method": "b1_rule"},
            files={"file": ("reviews.csv", csv_content, "text/csv")},
        )
        assert r_csv.status_code == 200
        d_csv = r_csv.json()
        assert d_csv["inserted_count"] == 2
        assert d_csv["skipped_count"] == 1

        # 2. XLSX upload via openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["review_id", "rating", "text"])
        ws.append(["xlsx_001", 4, "Giao hàng nhanh đóng gói cẩn thận"])
        buf = io.BytesIO()
        wb.save(buf)
        wb.close()
        r_xlsx = client.post(
            "/api/v1/reviews/upload-file",
            data={"scenario_tag": "file_scen", "analyzer_method": "b1_rule"},
            files={
                "file": (
                    "batch.xlsx",
                    buf.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert r_xlsx.status_code == 200
        assert r_xlsx.json()["inserted_count"] == 1

        # 3. Unsupported extension -> 400; > 5MB -> 413
        r_bad_ext = client.post(
            "/api/v1/reviews/upload-file",
            data={"scenario_tag": "file_scen"},
            files={"file": ("bad.txt", b"hello", "text/plain")},
        )
        assert r_bad_ext.status_code == 400
        r_big = client.post(
            "/api/v1/reviews/upload-file",
            data={"scenario_tag": "file_scen"},
            files={"file": ("big.csv", b"a" * (5 * 1024 * 1024 + 10), "text/csv")},
        )
        assert r_big.status_code == 413

        r_bad_xlsx = client.post(
            "/api/v1/reviews/upload-file",
            data={"scenario_tag": "file_scen"},
            files={"file": ("corrupt.xlsx", b"not-a-valid-zip", "application/octet-stream")},
        )
        assert r_bad_xlsx.status_code == 400

        # 4. Reply persistence + status transitions + total_count pagination + PII scrubbed
        r_rep = client.post(
            "/api/v1/reviews/csv_001/reply-draft?scenario_tag=file_scen&mode=template"
        )
        assert r_rep.status_code == 200
        reply_id = r_rep.json()["reply_id"]
        assert reply_id > 0

        r_hist = client.get("/api/v1/reviews/csv_001/replies?scenario_tag=file_scen")
        assert r_hist.status_code == 200
        assert r_hist.json()["count"] == 1

        # Guardrail violation must block APPROVED/SENT
        r_bad_status = client.post(
            f"/api/v1/reviews/replies/{reply_id}/status",
            json={
                "status": "APPROVED",
                "reply_text": "Shop cam kết chống thấm 100% và tặng tiền đổi 5 sao cho bạn nhé.",
            },
        )
        assert r_bad_status.status_code == 400

        # Stored violating draft must ALSO be blocked when reply_text is omitted
        from ecomreview.db.database import DatabaseManager

        db_direct = DatabaseManager(db_path=str(db_file))
        bad_id = db_direct.insert_review_reply(
            review_id="csv_002",
            scenario_tag="file_scen",
            reply_text="Shop cam kết chống thấm 100% bảo hành trọn đời ạ.",
            mode_used="llm",
            guardrail_passed=False,
            violations=["G1 (Overclaim)"],
        )
        r_bypass = client.post(
            f"/api/v1/reviews/replies/{bad_id}/status",
            json={"status": "APPROVED"},
        )
        assert r_bypass.status_code == 400

        # Valid DRAFT -> APPROVED -> SENT transition
        r_app = client.post(
            f"/api/v1/reviews/replies/{reply_id}/status",
            json={"status": "APPROVED"},
        )
        assert r_app.status_code == 200
        assert r_app.json()["status"] == "APPROVED"

        r_sent = client.post(
            f"/api/v1/reviews/replies/{reply_id}/status",
            json={"status": "SENT"},
        )
        assert r_sent.status_code == 200
        assert r_sent.json()["status"] == "SENT"
        assert r_sent.json()["sent_at"] is not None

        r_list = client.get("/api/v1/reviews?scenario_tag=file_scen&limit=2&offset=0")
        assert r_list.status_code == 200
        list_data = r_list.json()
        assert list_data["total_count"] == 3
        assert list_data["count"] == 2
        by_id = {r["review_id"]: r for r in list_data["reviews"]}
        assert by_id["csv_001"]["reply_status"] == "SENT"
        assert by_id["csv_001"]["latest_reply"]["status"] == "SENT"
        assert by_id["csv_001"]["latest_reply"]["sent_at"] is not None
        assert "[PHONE]" in by_id["csv_001"]["text_raw"]


# CreBy: MenBoyBMN
