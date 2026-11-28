"""Executive reporting service generating multi-tab Excel workbooks and printable HTML reports."""

from __future__ import annotations

import html
import io
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from ecomreview.agent.insight_engine import ASPECT_VN_LABELS, verify_numbers_in_statement
from ecomreview.agent.tools_aggregator import (
    detect_trend_alerts,
    get_aspect_sentiment_stats,
    get_platform_comparison,
    wilson_ci_pct,
)
from ecomreview.db.database import DatabaseManager
from ecomreview.security import scrub_pii

logger = logging.getLogger(__name__)


def _safe_cell(val: Any) -> Any:
    """Sanitize Excel cells to prevent formula injection (=, +, -, @, tab, CR)."""
    if isinstance(val, str):
        stripped = val.lstrip(" \t\r\n")
        if val.startswith(("=", "+", "-", "@", "\t", "\r")) or stripped.startswith(
            ("=", "+", "-", "@")
        ):
            return f"'{val}"
    return val


def build_excel_report(
    scenario_tag: str = "real_shop",
    db: DatabaseManager | None = None,
) -> bytes:
    """Generate professional executive Excel workbook with 6 structured sheets.

    Sheets:
    1. Tổng quan KPI (Executive KPIs & Platform counts)
    2. Đánh giá 8 Khía cạnh (Aspect Wilson 95% CI)
    3. Insights Đã Xác Thực (Evidence-grounded statistical insights)
    4. Kế hoạch Hành động (Critic-verified marketing & operational actions)
    5. Cảnh báo Xu hướng (Early warning statistical alerts)
    6. So sánh Sàn TMĐT (Shopee vs TikTok Shop z-test comparison)
    """
    db_mgr = db or DatabaseManager()
    wb = openpyxl.Workbook()
    try:
        # Remove default sheet
        wb.remove(wb.active)

        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        center_align = Alignment(horizontal="center", vertical="center")

        # Fetch KPI, Insights, and Actions in a single read-only connection
        with db_mgr.get_connection(read_only=True) as conn:
            kpi_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    AVG(rating) AS avg_rating,
                    SUM(CASE WHEN overall_sentiment = 'positive' THEN 1 ELSE 0 END) AS pos,
                    SUM(CASE WHEN overall_sentiment = 'negative' THEN 1 ELSE 0 END) AS neg,
                    SUM(CASE WHEN platform = 'shopee' THEN 1 ELSE 0 END) AS shopee,
                    SUM(CASE WHEN platform = 'tiktok' THEN 1 ELSE 0 END) AS tiktok
                FROM reviews WHERE scenario_tag = ?
                """,
                (scenario_tag,),
            ).fetchone()
            in_rows = conn.execute(
                "SELECT * FROM insights WHERE scenario_tag = ? AND COALESCE(is_archived, 0) = 0 "
                "ORDER BY id ASC",
                (scenario_tag,),
            ).fetchall()
            act_rows = conn.execute(
                """
                SELECT a.*, f.decision, f.decided_by
                FROM actions a
                LEFT JOIN (
                    SELECT action_id, decision, decided_by
                    FROM action_feedback
                    WHERE id IN (SELECT MAX(id) FROM action_feedback GROUP BY action_id)
                ) f ON a.id = f.action_id
                WHERE a.scenario_tag = ? AND COALESCE(a.is_archived, 0) = 0
                ORDER BY a.priority_score DESC, a.id ASC
                """,
                (scenario_tag,),
            ).fetchall()

        # Sheet 1: Tổng quan KPI
        ws1 = wb.create_sheet(title="Tổng quan KPI")

        total_revs = int(kpi_row["total"] or 0)
        pos_revs = int(kpi_row["pos"] or 0)
        neg_revs = int(kpi_row["neg"] or 0)
        avg_rating = round(float(kpi_row["avg_rating"] or 0.0), 2)
        neg_rate = round((neg_revs / total_revs) * 100.0, 1) if total_revs else 0.0
        ci_low, ci_high = wilson_ci_pct(neg_revs, total_revs)

        ws1.append(["Chỉ Số KPI", "Giá Trị", "Đơn Vị / Diễn Giải"])
        ws1.append(["Tổng số đánh giá phân tích", total_revs, "Đánh giá"])
        ws1.append(["Điểm đánh giá trung bình", avg_rating, "sao (1 - 5)"])
        ws1.append(
            [
                "Số lượng phản hồi hài lòng (Positive)",
                pos_revs,
                f"{round((pos_revs / total_revs) * 100, 1)}% tổng số" if total_revs else "0%",
            ]
        )
        ws1.append(["Số lượng phàn nàn (Negative)", neg_revs, f"{neg_rate}% tổng số"])
        ws1.append(
            [
                "Khoảng tin cậy tỷ lệ tiêu cực (Wilson 95% CI)",
                f"[{ci_low}% - {ci_high}%]",
                "Mức độ tin cậy thống kê",
            ]
        )
        ws1.append(["Đánh giá trên Shopee", int(kpi_row["shopee"] or 0), "Đánh giá"])
        ws1.append(["Đánh giá trên TikTok Shop", int(kpi_row["tiktok"] or 0), "Đánh giá"])

        # Sheet 2: 8 Khía cạnh
        ws2 = wb.create_sheet(title="Đánh giá 8 Khía cạnh")
        ws2.append(
            [
                "Khía Cạnh (Aspect)",
                "Tích Cực (+)",
                "Tiêu Cực (-)",
                "Trung Tính",
                "Tổng Lượt",
                "Tỷ Lệ Tiêu Cực (%)",
                "Wilson 95% CI Dưới (%)",
                "Wilson 95% CI Trên (%)",
                "Độ Tin Cậy",
            ]
        )
        aspect_stats = get_aspect_sentiment_stats(scenario_tag=scenario_tag, min_n=1, db=db_mgr)
        for s in aspect_stats:
            ws2.append(
                [
                    _safe_cell(s["aspect"]),
                    s["pos_count"],
                    s["neg_count"],
                    s["neu_count"],
                    s["total"],
                    s["neg_pct"],
                    s["wilson_ci_low"],
                    s["wilson_ci_high"],
                    _safe_cell(s["confidence"]),
                ]
            )

        # Sheet 3: Insights
        ws3 = wb.create_sheet(title="Insights Đã Xác Thực")
        ws3.append(
            [
                "ID",
                "Loại Insight",
                "Khía Cạnh",
                "Nội Dung Tuyên Bố",
                "Số Liệu Đối Chứng (SQL)",
                "Độ Tin Cậy",
                "Mã Review Bằng Chứng",
            ]
        )
        for r in in_rows:
            ws3.append(
                [
                    r["id"],
                    _safe_cell(r["kind"]),
                    _safe_cell(r["aspect"] or "GENERAL"),
                    _safe_cell(r["statement"]),
                    _safe_cell(str(r["numbers"])),
                    _safe_cell(r["confidence"]),
                    _safe_cell(str(r["evidence_ids"])),
                ]
            )

        # Sheet 4: Kế hoạch Hành động
        ws4 = wb.create_sheet(title="Kế hoạch Hành động")
        ws4.append(
            [
                "ID",
                "Phân Loại",
                "Kênh Áp Dụng",
                "Tiêu Đề Đề Xuất",
                "Hành Động Cụ Thể (What to do)",
                "Lý Do Căn Cứ (Why)",
                "Cách Thức & Thời Gian (How/When)",
                "Chỉ Số Đo Lường (Success Metric)",
                "Độ Ưu Tiên",
                "Điểm Critic",
                "Trạng Thái",
                "Người Duyệt",
            ]
        )
        for a in act_rows:
            critic_score = "5.0"
            if a["critic_trace"]:
                try:
                    ct = json.loads(a["critic_trace"])
                    if isinstance(ct, dict) and "critic_score" in ct:
                        critic_score = str(ct["critic_score"])
                except Exception:
                    pass
            if not a["critic_passed"]:
                critic_score = f"{critic_score} (Vi phạm)"

            ws4.append(
                [
                    a["id"],
                    "Marketing" if a["is_marketing"] else "Vận hành/Sản phẩm",
                    _safe_cell(a["action_type"]),
                    _safe_cell(a["title"]),
                    _safe_cell(a["what_to_do"]),
                    _safe_cell(a["why_rationale"]),
                    _safe_cell(a["how_and_when"]),
                    _safe_cell(a["success_metric"]),
                    round(float(a["priority_score"] or 0), 2),
                    _safe_cell(critic_score),
                    _safe_cell(str(a["decision"] or a["status"]).upper()),
                    _safe_cell(str(a["decided_by"] or "Chưa duyệt")),
                ]
            )

        # Sheet 5: Cảnh báo Xu hướng
        ws5 = wb.create_sheet(title="Cảnh báo Xu hướng")
        ws5.append(
            [
                "Khía Cạnh",
                "Kỳ Phát Hiện",
                "Mức Độ",
                "Mức Tăng (+pp)",
                "Tỷ Lệ Mới (%)",
                "Tỷ Lệ Gốc (%)",
                "Cỡ Mẫu Mới",
                "Cỡ Mẫu Gốc",
                "P-Value",
                "Nội Dung",
            ]
        )
        alerts = detect_trend_alerts(scenario_tag=scenario_tag, period="month", db=db_mgr)
        for al in alerts:
            ws5.append(
                [
                    _safe_cell(al["aspect"]),
                    _safe_cell(al["period"]),
                    _safe_cell(al["severity"]),
                    al["delta_pp"],
                    al["latest_neg_pct"],
                    al["baseline_neg_pct"],
                    al["latest_n"],
                    al["baseline_n"],
                    al["p_value"],
                    _safe_cell(al["message"]),
                ]
            )

        # Sheet 6: So sánh Sàn TMĐT
        ws6 = wb.create_sheet(title="So sánh Sàn TMĐT")
        ws6.append(
            [
                "Khía Cạnh",
                "Shopee Neg (%)",
                "Shopee Cỡ Mẫu",
                "TikTok Neg (%)",
                "TikTok Cỡ Mẫu",
                "Chênh Lệch (pp)",
                "Sàn Cao Hơn",
                "P-Value",
                "Ý Nghĩa Thống Kê (p<0.05)",
            ]
        )
        plat_comp = get_platform_comparison(scenario_tag=scenario_tag, min_n=1, db=db_mgr)
        for p in plat_comp:
            ws6.append(
                [
                    _safe_cell(p["aspect"]),
                    p["shopee_neg_pct"],
                    p["shopee_total"],
                    p["tiktok_neg_pct"],
                    p["tiktok_total"],
                    p["gap_pct"],
                    _safe_cell(p["higher_platform"]),
                    p["p_value"],
                    "CÓ" if p["significant"] else "KHÔNG",
                ]
            )

        # Format all sheets
        for ws in wb.worksheets:
            first_row = ws[1]
            for cell in first_row:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center_align
            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                col_letter = col[0].column_letter
                ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 50)

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
    finally:
        wb.close()


def build_html_report(
    scenario_tag: str = "real_shop",
    db: DatabaseManager | None = None,
) -> str:
    """Generate self-contained, printable HTML report with CSS for PDF browser export."""
    db_mgr = db or DatabaseManager()
    with db_mgr.get_connection(read_only=True) as conn:
        kpi_row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                AVG(rating) AS avg_rating,
                SUM(CASE WHEN overall_sentiment = 'positive' THEN 1 ELSE 0 END) AS pos,
                SUM(CASE WHEN overall_sentiment = 'negative' THEN 1 ELSE 0 END) AS neg
            FROM reviews WHERE scenario_tag = ?
            """,
            (scenario_tag,),
        ).fetchone()
        in_rows = conn.execute(
            "SELECT * FROM insights WHERE scenario_tag = ? AND COALESCE(is_archived, 0) = 0 "
            "ORDER BY id ASC",
            (scenario_tag,),
        ).fetchall()
        act_rows = conn.execute(
            "SELECT * FROM actions WHERE scenario_tag = ? AND COALESCE(is_archived, 0) = 0 "
            "ORDER BY priority_score DESC, id ASC",
            (scenario_tag,),
        ).fetchall()

    def _esc(val: Any) -> str:
        return html.escape(str(val if val is not None else ""), quote=True)

    tot = int(kpi_row["total"] or 0)
    pos = int(kpi_row["pos"] or 0)
    neg = int(kpi_row["neg"] or 0)
    avg_r = round(float(kpi_row["avg_rating"] or 0.0), 2)
    ci_low, ci_high = wilson_ci_pct(neg, tot)

    insights_html = "".join(
        f"<li><b>[{_esc(r['kind'])}] {_esc(r['aspect'] or 'GENERAL')}:</b> {_esc(r['statement'])} "
        f"<i>(Độ tin cậy: {_esc(r['confidence'])})</i></li>"
        for r in in_rows
    )

    actions_html = "".join(
        f"<tr><td><b>{_esc(a['title'])}</b></td><td>{_esc(a['action_type'])}</td>"
        f"<td>{'Marketing' if a['is_marketing'] else 'Vận hành'}</td>"
        f"<td>{_esc(a['what_to_do'])}</td><td>{_esc(a['success_metric'])}</td>"
        f"<td>{_esc(str(a['status'] or 'PENDING').upper())}</td></tr>"
        for a in act_rows
    )

    alerts = detect_trend_alerts(scenario_tag=scenario_tag, period="month", db=db_mgr)
    alerts_html = (
        "".join(
            f"<div class='alert alert-{_esc(al['severity'].lower())}'>"
            f"<b>{_esc(al['severity'])}:</b> {_esc(al['message'])}</div>"
            for al in alerts
        )
        or "<p>Không có cảnh báo đột biến nào trong giai đoạn khảo sát.</p>"
    )

    btn_style = (
        "padding: 10px 18px; font-size: 15px; background: #0284c7; "
        "color: #fff; border: none; border-radius: 6px; cursor: pointer;"
    )
    neg_p = round((neg / tot) * 100, 1) if tot else 0
    safe_scen = _esc(scenario_tag)

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>Báo Cáo Tác Nghiệp EcomReview AI — {safe_scen}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.6; color: #222; margin: 30px;
  }}
  h1, h2, h3 {{ color: #1F497D; }}
  .kpi-container {{ display: flex; gap: 20px; margin: 20px 0; }}
  .kpi-card {{
    flex: 1; border: 1px solid #ddd; border-radius: 8px;
    padding: 16px; background: #f8fafc; text-align: center;
  }}
  .kpi-num {{ font-size: 26px; font-weight: bold; color: #0284c7; }}
  table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 10px; text-align: left; }}
  th {{ background: #1F497D; color: #fff; }}
  tr:nth-child(even) {{ background: #f8fafc; }}
  .alert {{ padding: 12px; border-radius: 6px; margin: 10px 0; }}
  .alert-high {{ background: #fee2e2; border-left: 5px solid #dc2626; color: #991b1b; }}
  .alert-medium {{ background: #fef3c7; border-left: 5px solid #d97706; color: #92400e; }}
  @media print {{
    body {{ margin: 0; }}
    .no-print {{ display: none; }}
  }}
</style>
</head>
<body>
<div class="no-print" style="text-align: right; margin-bottom: 20px;">
  <button onclick="window.print()" style="{btn_style}">
    🖨️ In ra PDF / Máy In
  </button>
</div>
<h1>🌧️ Báo Cáo Phân Tích & Kế Hoạch Hành Động — EcomReview AI</h1>
<p><b>Kịch bản:</b> <code>{safe_scen}</code> | <b>Hệ thống:</b> EcomReview AI v1.1</p>

<h2>1. Tổng Quan Chỉ Số Hiệu Năng Cốt Lõi (Executive KPIs)</h2>
<div class="kpi-container">
  <div class="kpi-card"><div class="kpi-num">{tot}</div>Tổng số đánh giá</div>
  <div class="kpi-card"><div class="kpi-num">{avg_r} ⭐</div>Điểm trung bình</div>
  <div class="kpi-card"><div class="kpi-num" style="color: #16a34a;">{pos}</div>Hài lòng</div>
  <div class="kpi-card">
    <div class="kpi-num" style="color: #dc2626;">{neg} ({neg_p}%)</div>
    Phàn nàn (Wilson 95% CI: [{ci_low}% - {ci_high}%])
  </div>
</div>

<h2>2. Cảnh Báo Xu Hướng Đột Biến (Early Warning Alerts)</h2>
{alerts_html}

<h2>3. Phát Hiện Cốt Lõi Có Căn Cứ (Evidence-Grounded Insights)</h2>
<ul>{insights_html}</ul>

<h2>4. Danh Mục Đề Xuất Hành Động Khả Thi (Verified Action Proposals)</h2>
<table>
  <thead>
    <tr>
      <th>Tiêu Đề</th><th>Loại</th><th>Kênh</th>
      <th>Hành Động Cụ Thể</th><th>Chỉ Số Mục Tiêu</th><th>Trạng Thái</th>
    </tr>
  </thead>
  <tbody>
    {actions_html}
  </tbody>
</table>

<hr style="margin-top: 40px;">
<p style="font-size: 12px; color: #64748b; text-align: center;">
  Báo cáo được tổng hợp tự động và kiểm định xác thực bởi EcomReview AI.
</p>
<!-- CreBy: MenBoyBMN -->
</body>
</html>
"""


def build_weekly_digest(
    scenario_tag: str = "real_shop",
    db: DatabaseManager | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Build an executive weekly digest (verified metrics, PII-scrubbed) for Telegram/Webhook."""
    db_mgr = db or DatabaseManager()
    ict_tz = timezone(timedelta(hours=7))
    if as_of:
        try:
            ref_dt = datetime.strptime(str(as_of)[:10], "%Y-%m-%d").replace(tzinfo=ict_tz)
        except ValueError:
            ref_dt = datetime.now(ict_tz)
    else:
        ref_dt = datetime.now(ict_tz)
    iso_cal = ref_dt.isocalendar()
    week_key = f"{iso_cal.year}-W{iso_cal.week:02d}"

    shop_name = scenario_tag
    try:
        shop_info = db_mgr.get_pilot_shop(scenario_tag, include_secret=False)
        if shop_info and shop_info.get("name"):
            shop_name = str(shop_info["name"])
    except Exception:
        pass

    with db_mgr.get_connection(read_only=True) as conn:
        kpi_row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                AVG(rating) AS avg_rating,
                SUM(CASE WHEN overall_sentiment = 'negative' THEN 1 ELSE 0 END) AS neg,
                SUM(CASE WHEN platform = 'shopee' THEN 1 ELSE 0 END) AS shopee,
                SUM(CASE WHEN platform = 'tiktok' THEN 1 ELSE 0 END) AS tiktok,
                SUM(CASE WHEN rating <= 3 THEN 1 ELSE 0 END) AS low_star_total
            FROM reviews WHERE scenario_tag = ?
            """,
            (scenario_tag,),
        ).fetchone()
        sla_row = conn.execute(
            """
            SELECT COUNT(DISTINCT r.review_id) AS low_star_sent
            FROM reviews r
            JOIN review_replies rr
              ON r.review_id = rr.review_id AND r.scenario_tag = rr.scenario_tag
            WHERE r.scenario_tag = ? AND r.rating <= 3 AND rr.status = 'SENT'
            """,
            (scenario_tag,),
        ).fetchone()

    total_revs = int(kpi_row["total"] or 0)
    avg_rating = round(float(kpi_row["avg_rating"] or 0.0), 2)
    neg_revs = int(kpi_row["neg"] or 0)
    neg_rate = round((neg_revs / total_revs) * 100.0, 1) if total_revs else 0.0
    ci_low, ci_high = wilson_ci_pct(neg_revs, total_revs)
    shopee_cnt = int(kpi_row["shopee"] or 0)
    tiktok_cnt = int(kpi_row["tiktok"] or 0)
    low_star_total = int(kpi_row["low_star_total"] or 0)
    low_star_sent = int(sla_row["low_star_sent"] or 0)
    pending_cskh = max(0, low_star_total - low_star_sent)
    sla_pct = round((low_star_sent / low_star_total) * 100.0, 1) if low_star_total else 100.0

    aspect_stats = get_aspect_sentiment_stats(scenario_tag=scenario_tag, min_n=1, db=db_mgr)
    top_pains = [s for s in aspect_stats if s.get("neg_count", 0) > 0][:3]
    alerts = detect_trend_alerts(scenario_tag=scenario_tag, min_n=5, as_of=as_of, db=db_mgr)

    lines = [
        f"Báo cáo tuần {week_key} — {scrub_pii(shop_name)} ({scenario_tag})",
        f"• Tổng đánh giá: {total_revs} (Shopee: {shopee_cnt}, TikTok: {tiktok_cnt})",
        (
            f"• Điểm TB: {avg_rating} sao | "
            f"Tiêu cực: {neg_revs} ({neg_rate}%, Wilson CI [{ci_low}%-{ci_high}%])"
        ),
        (
            f"• Tiến độ CSKH (<=3 sao): đã gửi {low_star_sent}/{low_star_total} "
            f"({sla_pct}%), tồn đọng {pending_cskh}"
        ),
    ]
    num_bank: dict[str, Any] = {
        "total_revs": total_revs,
        "shopee_cnt": shopee_cnt,
        "tiktok_cnt": tiktok_cnt,
        "avg_rating": avg_rating,
        "neg_revs": neg_revs,
        "neg_rate": neg_rate,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "low_star_sent": low_star_sent,
        "low_star_total": low_star_total,
        "sla_pct": sla_pct,
        "pending_cskh": pending_cskh,
        "alerts_cnt": len(alerts),
        "week_year": iso_cal.year,
        "week_num": iso_cal.week,
    }
    if top_pains:
        pain_parts = []
        for idx, tp in enumerate(top_pains, start=1):
            asp_code = str(tp["aspect"])
            asp_label = ASPECT_VN_LABELS.get(asp_code, asp_code)
            pain_parts.append(
                f"{idx}. {asp_label}: {tp['neg_pct']}% ({tp['neg_count']}/{tp['total']})"
            )
            num_bank[f"tp_{idx}_idx"] = idx
            num_bank[f"tp_{idx}_pct"] = tp["neg_pct"]
            num_bank[f"tp_{idx}_neg"] = tp["neg_count"]
            num_bank[f"tp_{idx}_tot"] = tp["total"]
        lines.append("• Top vấn đề nổi bật: " + "; ".join(pain_parts))
    else:
        lines.append("• Top vấn đề nổi bật: Chưa ghi nhận khía cạnh tiêu cực.")

    lines.append(f"• Cảnh báo đột biến (Z-test): {len(alerts)} cảnh báo đang kích hoạt.")

    raw_msg = scrub_pii("\n".join(lines))
    if not verify_numbers_in_statement(raw_msg, num_bank):
        logger.warning("Weekly digest numeric verification fallback triggered for %s", scenario_tag)
        raw_msg = scrub_pii(
            f"Báo cáo tuần {week_key} — {shop_name}: {total_revs} đánh giá, "
            f"điểm TB {avg_rating}, tiêu cực {neg_rate}%."
        )

    return {
        "week_key": week_key,
        "scenario_tag": scenario_tag,
        "shop_name": shop_name,
        "title": f"Báo cáo tổng hợp tuần {week_key}",
        "message_text": raw_msg,
        "metrics": {
            "total_reviews": total_revs,
            "avg_rating": avg_rating,
            "negative_reviews": neg_revs,
            "negative_rate_pct": neg_rate,
            "wilson_ci_95": [ci_low, ci_high],
            "shopee_reviews": shopee_cnt,
            "tiktok_reviews": tiktok_cnt,
            "low_star_total": low_star_total,
            "low_star_sent": low_star_sent,
            "pending_cskh": pending_cskh,
            "cskh_sla_pct": sla_pct,
            "top_pains": top_pains,
            "alerts_count": len(alerts),
        },
    }


# CreBy: MenBoyBMN
