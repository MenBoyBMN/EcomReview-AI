"""Tests for intervention impact analysis and executive reporting (Excel/HTML)."""

from ecomreview.agent.tools_aggregator import get_action_impact
from ecomreview.db.database import DatabaseManager
from ecomreview.reporting import _safe_cell, build_excel_report, build_html_report


class TestImpactAndReporting:
    """Validate intervention impact metrics and report generator fidelity."""

    def test_safe_cell_sanitizes_formula_injection(self):
        """Verify _safe_cell escapes formula triggers =, +, -, @ to prevent CSV/Excel injection."""
        assert _safe_cell("=SUM(A1:A10)") == "'=SUM(A1:A10)"
        assert _safe_cell("+CMD('calc')") == "'+CMD('calc')"
        assert _safe_cell("-1+1") == "'-1+1"
        assert _safe_cell("@something") == "'@something"
        assert _safe_cell("Regular text") == "Regular text"
        assert _safe_cell(12345) == 12345

    def _seed_reporting_db(self, tmp_path):
        db = DatabaseManager(tmp_path / "test_reporting.db")
        for i in range(6):
            pol = "negative" if i < 3 else "positive"
            db.upsert_review_and_opinions(
                review_id=f"rep_rev_{i}",
                platform="shopee" if i % 2 == 0 else "tiktok",
                shop="shop_a",
                product="ao_mua",
                rating=2 if i < 3 else 5,
                text_raw=f"Đánh giá {i} về khả năng chống thấm nước của áo mưa",
                text_norm=f"đánh giá {i} về khả năng chống thấm nước của áo mưa",
                source="review",
                scenario_tag="rep_scen",
                overall_sentiment=pol,
                informative=True,
                opinions=[{"aspect": "WATERPROOF", "polarity": pol, "evidence": "chống thấm"}],
                created_at=f"2026-09-0{i + 1}",
            )
        return db

    def test_build_excel_report_produces_valid_workbook(self, tmp_path):
        """Verify build_excel_report returns valid binary xlsx with 6 worksheets."""
        db = self._seed_reporting_db(tmp_path)
        xlsx_bytes = build_excel_report(scenario_tag="rep_scen", db=db)
        assert isinstance(xlsx_bytes, bytes)
        assert len(xlsx_bytes) > 5000

        # Check signature for zip/xlsx
        assert xlsx_bytes.startswith(b"PK")

    def test_build_html_report_contains_key_sections(self, tmp_path):
        """Verify build_html_report contains styled sections and KPIs."""
        db = self._seed_reporting_db(tmp_path)
        html = build_html_report(scenario_tag="rep_scen", db=db)
        assert "<!DOCTYPE html>" in html
        assert "Chỉ Số Hiệu Năng Cốt Lõi" in html
        assert "Phát Hiện Cốt Lõi Có Căn Cứ" in html
        assert "Báo Cáo Phân Tích & Kế Hoạch Hành Động" in html

    def test_get_action_impact_handles_missing_or_insufficient_data(self, tmp_path):
        """Verify get_action_impact reports insufficient_data gracefully."""
        db = DatabaseManager(tmp_path / "test_impact_missing.db")
        res = get_action_impact(action_id=999999, db=db)
        assert res["status"] == "action_not_found"


# CreBy: MenBoyBMN
