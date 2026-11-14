"""Tests for dual database backend (SQLite & PostgreSQL) and read-only enforcement."""

import os
import sqlite3

import pytest

from ecomreview.db.database import DatabaseManager


class TestDatabaseBackend:
    """Validate database initialization, querying, and security boundaries."""

    def test_sqlite_initialization_and_crud(self, tmp_path):
        """Verify SQLite backend initializes all 6 core tables and supports RETURNING id."""
        db_file = tmp_path / "test_backend.db"
        db = DatabaseManager(db_path=str(db_file), db_backend="sqlite")

        # Insert review
        db.upsert_review_and_opinions(
            review_id="test_001",
            platform="tiktok",
            shop="shop_a",
            product="ao_mua",
            rating=5,
            text_raw="Ao mua dep lam",
            text_norm="ao mua dep lam",
            source="test",
            scenario_tag="test_scenario",
            overall_sentiment="positive",
            informative=True,
            opinions=[{"aspect": "MATERIAL_DURABILITY", "polarity": "positive", "evidence": "dep"}],
            analyzer_method="test",
        )

        with db.get_connection(read_only=True) as conn:
            row = conn.execute(
                "SELECT * FROM reviews WHERE review_id = ?", ("test_001",)
            ).fetchone()
            assert row is not None
            assert row["rating"] == 5
            assert row["platform"] == "tiktok"

    def test_sqlite_read_only_mode_blocks_writes(self, tmp_path):
        """Verify read_only=True blocks write transactions with SQLite OperationalError."""
        db_file = tmp_path / "test_ro.db"
        db = DatabaseManager(db_path=str(db_file), db_backend="sqlite")

        with pytest.raises(sqlite3.OperationalError, match="attempt to write a readonly database"):
            with db.get_connection(read_only=True) as conn:
                conn.execute(
                    "INSERT INTO reviews (review_id, scenario_tag, text_raw, text_norm) "
                    "VALUES (?, ?, ?, ?)",
                    ("fail_01", "test", "raw", "norm"),
                )

    def test_record_action_decision_with_decided_by(self, tmp_path):
        """Verify decided_by is persisted in action_feedback."""
        db_file = tmp_path / "test_act.db"
        db = DatabaseManager(db_path=str(db_file), db_backend="sqlite")

        aid = db.insert_action(
            scenario_tag="test_scenario",
            action_type="LISTING_UPDATE",
            is_marketing=True,
            title="Cap nhat mo ta",
            what_to_do="Sua mo ta",
            why_rationale="Ly do",
            how_and_when="Trong 24h",
            success_metric="Giam loi",
            effort="LOW",
            impact="MEDIUM",
            priority_score=4.5,
            insight_ids=["1"],
            evidence_review_ids=["test_001", "test_002"],
        )

        res = db.record_action_decision(
            action_id=aid,
            decision="APPROVED",
            note="Duyet qua UI",
            decided_by="admin_user",
        )

        assert res["decision"] == "APPROVED"
        assert res["decided_by"] == "admin_user"

        with db.get_connection(read_only=True) as conn:
            fb = conn.execute(
                "SELECT * FROM action_feedback WHERE action_id = ?", (aid,)
            ).fetchone()
            assert fb is not None
            assert fb["decided_by"] == "admin_user"

    def test_action_archiving_preserves_feedback_and_review_replies(self, tmp_path):
        """Re-running graph archives previous actions instead of deleting action_feedback."""
        from ecomreview.agent.graph_runner import EcomReviewGraphRunner

        db_file = tmp_path / "test_archive.db"
        db = DatabaseManager(db_path=str(db_file), db_backend="sqlite")

        for i in range(6):
            pol = "negative" if i < 4 else "positive"
            db.upsert_review_and_opinions(
                review_id=f"arc_{i:03d}",
                platform="shopee",
                shop="shop_a",
                product="ao_mua",
                rating=2 if i < 4 else 5,
                text_raw=f"Đánh giá {i} về khả năng chống thấm nước đường may áo mưa",
                text_norm=f"đánh giá {i} về khả năng chống thấm nước đường may áo mưa",
                source="review",
                scenario_tag="arc_scen",
                overall_sentiment=pol,
                informative=True,
                opinions=[{"aspect": "WATERPROOF", "polarity": pol, "evidence": "chống thấm nước"}],
            )

        runner = EcomReviewGraphRunner(db=db, trace_dir=tmp_path / "traces", use_llm=False)
        runner.run_scenario(scenario_tag="arc_scen", min_n=5, max_actions=3)

        with db.get_connection(read_only=True) as conn:
            act1 = conn.execute(
                "SELECT id FROM actions WHERE scenario_tag = 'arc_scen' AND is_archived = 0"
            ).fetchone()
        assert act1 is not None
        first_id = int(act1["id"])
        db.record_action_decision(action_id=first_id, decision="APPROVED", decided_by="owner")

        # Run again: old action must be archived, feedback must stay intact
        runner.run_scenario(scenario_tag="arc_scen", min_n=5, max_actions=3)
        with db.get_connection(read_only=True) as conn:
            old_row = conn.execute(
                "SELECT status, is_archived FROM actions WHERE id = ?", (first_id,)
            ).fetchone()
            fb_row = conn.execute(
                "SELECT decision FROM action_feedback WHERE action_id = ?", (first_id,)
            ).fetchone()
            active_rows = conn.execute(
                "SELECT id FROM actions WHERE scenario_tag = 'arc_scen' AND is_archived = 0"
            ).fetchall()
        assert old_row is not None and old_row["is_archived"] == 1
        assert old_row["status"] == "APPROVED"
        assert fb_row is not None and fb_row["decision"] == "APPROVED"
        assert all(int(r["id"]) != first_id for r in active_rows)

        # Verify review_replies insert and list
        rep_id = db.insert_review_reply(
            review_id="arc_000",
            scenario_tag="arc_scen",
            reply_text="Dạ shop xin lỗi và hỗ trợ đổi mới 1-1 qua chat sàn ạ.",
            mode_used="template",
            guardrail_passed=True,
            violations=[],
            created_by="cskh_staff",
        )
        assert rep_id > 0
        replies = db.list_review_replies("arc_000", "arc_scen")
        assert len(replies) == 1
        assert replies[0]["created_by"] == "cskh_staff"

    def test_postgres_integration_when_url_provided(self):
        """Execute integration tests on PostgreSQL 16 if ECOMREVIEW_TEST_PG_URL is set."""
        pg_url = os.getenv("ECOMREVIEW_TEST_PG_URL")
        if not pg_url:
            pytest.skip("ECOMREVIEW_TEST_PG_URL not configured. Skipping live PostgreSQL test.")

        db = DatabaseManager(db_backend="postgres", database_url=pg_url)
        assert db.backend == "postgres"

        with db.get_connection(read_only=False) as conn:
            cur = conn.execute("SELECT 1 AS check_col")
            res = cur.fetchone()
            assert res["check_col"] == 1


# CreBy: MenBoyBMN
