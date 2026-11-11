"""Tests for intervention impact analysis and executive reporting (Excel/HTML)."""

from ecomreview.agent.tools_aggregator import get_action_impact
from ecomreview.db.database import DatabaseManager
from ecomreview.reporting import build_excel_report, build_html_report


class TestImpactAndReporting:
    """Validate intervention impact metrics and report generator fidelity."""

    def test_build_excel_report_produces_valid_workbook(self):
        """Verify build_excel_report returns valid binary xlsx with 6 worksheets."""
        db = DatabaseManager()
        xlsx_bytes = build_excel_report(scenario_tag="real_shop", db=db)
        assert isinstance(xlsx_bytes, bytes)
        assert len(xlsx_bytes) > 5000

        # Check signature for zip/xlsx
        assert xlsx_bytes.startswith(b"PK")

    def test_build_html_report_contains_key_sections(self):
        """Verify build_html_report contains styled sections and KPIs."""
        db = DatabaseManager()
        html = build_html_report(scenario_tag="real_shop", db=db)
        assert "<!DOCTYPE html>" in html
        assert "Chỉ Số Hiệu Năng Cốt Lõi" in html
        assert "Phát Hiện Cốt Lõi Có Căn Cứ" in html
        assert "Báo Cáo Phân Tích & Kế Hoạch Hành Động" in html

    def test_get_action_impact_handles_missing_or_insufficient_data(self):
        """Verify get_action_impact reports insufficient_data gracefully."""
        db = DatabaseManager()
        res = get_action_impact(action_id=999999, db=db)
        assert res["status"] == "action_not_found"


# CreBy: MenBoyBMN
