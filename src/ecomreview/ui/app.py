"""Streamlit 5-Page Executive Dashboard for EcomReview AI.

Pages:
1. Executive Overview (KPIs + Wilson 95% CI + Historical Trend Line + Early Warning Alerts)
2. Evidence-Grounded Insights (5 Insight Categories + Number Verification Badge + Verbatim Quotes)
3. Action Center & Critic Trace (Marketing vs Ops Tabs + R1-R7 Trace + Impact + Human Gate)
4. Review Explorer & Policy Reply Assistant (ABSA Filter + Dynamic G1-G6 Guardrailed Reply Drafts)
5. Ingestion & Executive Reports (CSV/Excel Upload & Mapping + 1-Click Excel/HTML Export)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ecomreview.agent.graph_runner import EcomReviewGraphRunner
from ecomreview.agent.insight_engine import ASPECT_VN_LABELS
from ecomreview.agent.reply_assistant import generate_customer_reply
from ecomreview.agent.tools_aggregator import (
    detect_trend_alerts,
    get_action_impact,
    get_aspect_sentiment_stats,
    get_aspect_trend,
    get_platform_comparison,
    wilson_ci_pct,
)
from ecomreview.db.database import DatabaseManager
from ecomreview.ingest_service import ingest_review_batch
from ecomreview.reporting import build_excel_report, build_html_report

logger = logging.getLogger(__name__)


def get_db() -> DatabaseManager:
    """Return configured DatabaseManager instance."""
    return DatabaseManager(
        db_path=os.getenv("ECOMREVIEW_SQLITE_PATH"),
        db_backend=os.getenv("ECOMREVIEW_DB_BACKEND", "sqlite"),
        database_url=os.getenv("DATABASE_URL"),
        database_url_ro=os.getenv("DATABASE_URL_RO"),
    )


def build_asymmetric_wilson_chart(aspect_stats: list[dict[str, Any]]) -> go.Figure:
    """Build Plotly horizontal bar chart with asymmetric Wilson 95% CI error bars."""
    df = pd.DataFrame(aspect_stats)
    if df.empty:
        return go.Figure()

    df = df.sort_values("neg_pct", ascending=True)
    labels = [ASPECT_VN_LABELS.get(str(a), str(a)) for a in df["aspect"]]
    neg_pct = df["neg_pct"].tolist()
    err_plus = [round(float(h) - float(p), 1) for p, h in zip(df["neg_pct"], df["ci_high"])]
    err_minus = [round(float(p) - float(low), 1) for p, low in zip(df["neg_pct"], df["ci_low"])]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=labels,
            x=neg_pct,
            orientation="h",
            name="Tỷ lệ phàn nàn tiêu cực (%)",
            marker_color="#ef4444",
            error_x={
                "type": "data",
                "symmetric": False,
                "array": err_plus,
                "arrayminus": err_minus,
                "color": "#1e293b",
                "thickness": 1.8,
                "width": 6,
            },
            text=[f"{p:.1f}% (n={n})" for p, n in zip(df["neg_pct"], df["total"])],
            textposition="auto",
        )
    )
    fig.update_layout(
        title="Tỷ Lệ Phàn Nàn Theo Khía Cạnh Kèm Thanh Sai Số Bất Đối Xứng (Wilson 95% CI)",
        xaxis_title="Tỷ lệ tiêu cực (%) & Khoảng tin cậy Wilson 95%",
        yaxis_title="Khía cạnh đánh giá (ABSA Taxonomy)",
        xaxis={"range": [0, 105]},
        height=400,
        margin={"l": 20, "r": 20, "t": 50, "b": 30},
    )
    return fig


def build_trend_line_chart(trend_stats: list[dict[str, Any]], aspect_name: str) -> go.Figure:
    """Build Plotly line chart displaying sentiment trend over chronological periods."""
    if not trend_stats:
        return go.Figure()

    df = pd.DataFrame(trend_stats)
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["period"],
            y=df["wilson_ci_high"],
            mode="lines",
            line={"width": 0},
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["period"],
            y=df["wilson_ci_low"],
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor="rgba(239, 68, 68, 0.2)",
            name="Dải tin cậy Wilson 95% CI",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["period"],
            y=df["neg_pct"],
            mode="lines+markers+text",
            name=f"Tỷ lệ tiêu cực {aspect_name} (%)",
            line={"color": "#dc2626", "width": 2.5},
            marker={"size": 7, "color": "#991b1b"},
            text=[f"{p:.1f}%" for p in df["neg_pct"]],
            textposition="top center",
        )
    )
    fig.update_layout(
        title=f"Biến Động Tỷ Lệ Tiêu Cực Theo Thời Gian ({aspect_name}) & Dải Tin Cậy Wilson 95%",
        xaxis_title="Kỳ khảo sát (Tháng/Tuần)",
        yaxis_title="Tỷ lệ phàn nàn (%)",
        yaxis={"range": [0, max(100, float(df["wilson_ci_high"].max() or 50) + 10)]},
        height=360,
        margin={"l": 20, "r": 20, "t": 45, "b": 30},
    )
    return fig


def render_page_overview(db: DatabaseManager, scenario_tag: str) -> None:
    """Page 1: Executive Overview with Asymmetric Wilson 95% CI Error Bars & Early Warnings."""
    st.header("📊 Trang 1: Tổng Quan Điều Hành (Executive Overview)")

    # Early Warning Alerts Banner
    alerts = detect_trend_alerts(scenario_tag=scenario_tag, period="month", db=db)
    if alerts:
        for al in alerts:
            alert_type = st.error if al["severity"] == "HIGH" else st.warning
            alert_type(
                f"🚨 **{al['message']}** "
                f"(Cỡ mẫu mới: {al['latest_n']}, Cỡ mẫu nền: {al['baseline_n']})"
            )

    with db.get_connection(read_only=True) as conn:
        row = conn.execute(
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

    total = int(row["total"] or 0)
    pos = int(row["pos"] or 0)
    neg = int(row["neg"] or 0)
    avg_rating = float(row["avg_rating"] or 0.0)
    neg_pct = (neg / total) * 100.0 if total > 0 else 0.0
    ci_low, ci_high = wilson_ci_pct(neg, total)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tổng Số Đánh Giá", f"{total:,}")
    col2.metric("Điểm Đánh Giá TB", f"{avg_rating:.2f} ⭐")
    col3.metric("Tỷ Lệ Hài Lòng", f"{(pos / total * 100):.1f}%" if total else "0%")
    col4.metric(
        "Tỷ Lệ Phàn Nàn",
        f"{neg_pct:.1f}%",
        help=f"Wilson 95% CI: [{ci_low:.1f}%, {ci_high:.1f}%]",
    )

    st.markdown("---")
    aspect_stats = get_aspect_sentiment_stats(scenario_tag=scenario_tag, min_n=3, db=db)
    if aspect_stats:
        fig_aspect = build_asymmetric_wilson_chart(aspect_stats)
        st.plotly_chart(fig_aspect, use_container_width=True)
    else:
        st.info("Chưa đủ dữ liệu để vẽ biểu đồ khía cạnh (cần tối thiểu n >= 3 đánh giá).")

    # Historical Trend Section
    st.subheader("📈 Xu Hướng Biến Động Theo Thời Gian & Cảnh Báo Sớm")
    col_t1, col_t2 = st.columns([1, 2])
    with col_t1:
        aspect_choices = ["Tất cả (Tổng quan)"] + [
            f"{s['aspect']} ({ASPECT_VN_LABELS.get(s['aspect'], s['aspect'])})"
            for s in aspect_stats
        ]
        chosen_asp = st.selectbox("Chọn khía cạnh theo dõi xu hướng:", aspect_choices)
        selected_aspect = chosen_asp.split(" ")[0] if not chosen_asp.startswith("Tất cả") else None
        period_choice = st.radio(
            "Độ mịn thời gian:", ["month (Tháng)", "week (Tuần)"], horizontal=True
        )
        period_val = "week" if "week" in period_choice else "month"

    with col_t2:
        trend_data = get_aspect_trend(
            scenario_tag=scenario_tag,
            aspect=selected_aspect,
            period=period_val,
            min_n=2,
            db=db,
        )
        if trend_data:
            fig_trend = build_trend_line_chart(trend_data, selected_aspect or "Tổng thể")
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("Chưa có đủ mốc thời gian để vẽ đồ thị xu hướng cho khía cạnh này.")

    # Platform Comparison Section
    st.subheader("⚖️ So Sánh Đánh Giá Giữa Shopee & TikTok Shop (z-Test)")
    comp_stats = get_platform_comparison(scenario_tag=scenario_tag, min_n=1, db=db)
    if comp_stats:
        comp_df = pd.DataFrame(
            [
                {
                    "Khía Cạnh": (
                        f"{c['aspect']} ({ASPECT_VN_LABELS.get(c['aspect'], c['aspect'])})"
                    ),
                    "Shopee Neg (%)": f"{c['shopee_neg_pct']:.1f}% (n={c['shopee_total']})",
                    "TikTok Neg (%)": f"{c['tiktok_neg_pct']:.1f}% (n={c['tiktok_total']})",
                    "Chênh Lệch": f"{c['gap_pct']:.1f}pp ({c['higher_platform'].upper()} cao hơn)",
                    "p-value (z-test)": f"{c['p_value']:.4f}",
                    "Ý Nghĩa (p<0.05)": "⭐ CÓ" if c["significant"] else "Không",
                }
                for c in comp_stats
            ]
        )
        st.dataframe(comp_df, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có đủ dữ liệu trên cả 2 sàn để chạy kiểm định so sánh.")


def render_page_insights(db: DatabaseManager, scenario_tag: str) -> None:
    """Page 2: Evidence-Grounded Insights with verbatim customer quotes."""
    st.header("💡 Trang 2: Phát Hiện Cốt Lõi Có Căn Cứ (Verified Insights)")
    with db.get_connection(read_only=True) as conn:
        rows = conn.execute(
            "SELECT * FROM insights WHERE scenario_tag = ? ORDER BY id ASC", (scenario_tag,)
        ).fetchall()

    if not rows:
        st.warning("Chưa có Insights nào được tạo cho kịch bản này. Vui lòng bấm chạy phân tích.")
        return

    st.caption(f"Tổng số {len(rows)} nhận định đã được kiểm thực số liệu qua SQL Aggregator.")
    for r in rows:
        kind = str(r["kind"])
        nums = json.loads(r["numbers"] or "{}") if isinstance(r["numbers"], str) else r["numbers"]
        ev_ids = (
            json.loads(r["evidence_ids"] or "[]")
            if isinstance(r["evidence_ids"], str)
            else r["evidence_ids"]
        )
        asp = str(r["aspect"] or "GENERAL")
        conf = str(r["confidence"]).upper()

        with st.container(border=True):
            badge_html = (
                f"<span style='background:#dbeafe;color:#1e40af;padding:3px 8px;"
                f"border-radius:12px;font-size:12px;'>Độ tin cậy: {conf}</span>"
            )
            st.markdown(
                f"### `[{kind}]` {asp} &nbsp; {badge_html}",
                unsafe_allow_html=True,
            )
            st.markdown(f"**Tuyên bố xác thực:** {r['statement']}")
            st.markdown(
                f"- **Số liệu kiểm chứng:** `Tổng n = {nums.get('total', 0)}` | "
                f"`Tiêu cực = {nums.get('neg_count', nums.get('issue_count', 0))}` | "
                f"`Tỷ lệ = {nums.get('neg_pct', nums.get('issue_pct', 0))}%` | "
                f"`Wilson 95% CI: [{nums.get('ci_low', 0)}% - {nums.get('ci_high', 0)}%]`"
            )

            if ev_ids:
                with st.expander(f"🔍 Trích dẫn dẫn chứng thực tế ({len(ev_ids)} review IDs)"):
                    placeholders = ",".join(["?"] * len(ev_ids))
                    with db.get_connection(read_only=True) as conn:
                        ev_rows = conn.execute(
                            f"SELECT review_id, platform, rating, text_raw FROM reviews "
                            f"WHERE scenario_tag = ? AND review_id IN ({placeholders})",
                            (scenario_tag, *ev_ids),
                        ).fetchall()
                    for ev in ev_rows:
                        plat_str = str(ev["platform"]).upper()
                        st.markdown(
                            f"💬 **`{ev['review_id']}`** ({plat_str} | {ev['rating']} ⭐): "
                            f"_{ev['text_raw']}_"
                        )


def render_page_actions(
    db: DatabaseManager, scenario_tag: str, reviewer_name: str = "shop_owner"
) -> None:
    """Page 3: Action Center, Hybrid Critic R1-R7 Trace, and Human Approval Gate."""
    st.header("🎯 Trang 3: Trung Tâm Kế Hoạch Hành Động (Action Center)")

    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        if st.button("🚀 Kích Hoạt State-Graph (Tạo Đề Xuất Mới)", type="primary"):
            with st.spinner("Đang chạy State-Graph (Planner ⮂ Hybrid Critic R1-R7)..."):
                runner = EcomReviewGraphRunner(db=db, max_retries=2)
                runner.run_scenario(
                    scenario_tag=scenario_tag, min_n=3, max_actions=5, persist_db=True
                )
                st.success("Đã sinh kế hoạch hành động thành công!")
                st.rerun()

    with db.get_connection(read_only=True) as conn:
        rows = conn.execute(
            """
            SELECT a.*, f.decision AS latest_decision, f.decided_by, f.decided_at
            FROM actions a
            LEFT JOIN action_feedback f ON a.id = f.action_id
            WHERE a.scenario_tag = ?
            ORDER BY a.priority_score DESC, a.id ASC
            """,
            (scenario_tag,),
        ).fetchall()

    if not rows:
        st.info("Chưa có hành động nào được đề xuất. Hãy bấm nút phía trên để chạy State-Graph.")
        return

    tab_mkt, tab_ops = st.tabs(
        [
            "📢 Hành Động Marketing (`is_marketing = True`)",
            "🛠️ Hành Động Sản Phẩm / Vận Hành (`is_marketing = False`)",
        ]
    )

    for is_mkt_tab, tab in [(True, tab_mkt), (False, tab_ops)]:
        with tab:
            subset = [r for r in rows if bool(r["is_marketing"]) == is_mkt_tab]
            if not subset:
                st.write("Không có đề xuất nào trong phân nhóm này.")
            for r in subset:
                aid = int(r["id"])
                trace = (
                    json.loads(r["critic_trace"] or "{}")
                    if isinstance(r["critic_trace"], str)
                    else (r["critic_trace"] or {})
                ) or {}
                ev_ids = (
                    json.loads(r["evidence_review_ids"] or "[]")
                    if isinstance(r["evidence_review_ids"], str)
                    else (r["evidence_review_ids"] or [])
                ) or []
                current_status = str(r["latest_decision"] or r["status"]).upper()

                with st.container(border=True):
                    header_md = (
                        f"#### `[{r['action_type']}]` {r['title']} "
                        f"(Priority: **`{r['priority_score']}`** | "
                        f"Trạng thái: **`{current_status}`**)"
                    )
                    st.markdown(header_md)
                    st.markdown(f"- **Việc cần làm (`what_to_do`):** {r['what_to_do']}")
                    st.markdown(f"- **Căn cứ số liệu (`why_rationale`):** {r['why_rationale']}")
                    st.markdown(f"- **Cách làm & Thời hạn (`how_and_when`):** {r['how_and_when']}")
                    st.markdown(f"- **Chỉ số đo lường (`success_metric`):** {r['success_metric']}")

                    c_sc = trace.get("critic_score", 5.0)
                    c_rt = trace.get("retries", 0)
                    reviewer_tag = f" | Người duyệt: `{r['decided_by']}`" if r["decided_by"] else ""
                    st.caption(
                        f"Effort: `{r['effort']}` | Impact: `{r['impact']}` | "
                        f"Evidence IDs: `{', '.join(ev_ids)}` | "
                        f"Critic Score: `{c_sc}/5.0` (Retries: `{c_rt}`){reviewer_tag}"
                    )

                    with st.expander("🛡️ Xem Nhật Ký Kiểm Định Hybrid Critic (R1–R7 Trace JSON)"):
                        st.json(trace)

                    # Intervention Impact Expander
                    with st.expander(
                        "📈 Đo lường hiệu quả trước/sau can thiệp (Intervention Impact)"
                    ):
                        impact_res = get_action_impact(aid, window_days=30, db=db)
                        if impact_res.get("status") == "insufficient_data":
                            note_txt = impact_res.get(
                                "note", "Chưa đủ dữ liệu trước/sau để kiểm định."
                            )
                            st.info(f"ℹ️ {note_txt}")
                        else:
                            st.json(impact_res)

                    edited_txt = st.text_area(
                        "Chỉnh sửa nội dung hành động (nếu cần trước khi duyệt):",
                        value=str(r["what_to_do"]),
                        key=f"edit_{aid}",
                    )
                    rej_reason = st.selectbox(
                        "Lý do từ chối (nếu chọn Reject):",
                        [
                            "NOT_FEASIBLE",
                            "TOO_GENERIC",
                            "WRONG_EVIDENCE",
                            "TOO_COSTLY",
                            "OUT_OF_SCOPE",
                            "OTHER",
                        ],
                        key=f"rej_reason_{aid}",
                    )
                    col_a, col_e, col_r = st.columns(3)
                    if col_a.button("✅ Phê duyệt (Approve)", key=f"btn_app_{aid}"):
                        db.record_action_decision(
                            aid, "APPROVED", note="Approved via UI", decided_by=reviewer_name
                        )
                        st.rerun()
                    if col_e.button("✏️ Sửa & Duyệt (Edit & Approve)", key=f"btn_edt_{aid}"):
                        res_dec = db.record_action_decision(
                            aid,
                            "EDITED",
                            edited_content=edited_txt,
                            note="Edited via UI",
                            decided_by=reviewer_name,
                        )
                        dist_c = res_dec["edit_distance_chars"]
                        st.success(
                            f"Đã lưu chỉnh sửa bởi {reviewer_name} (Edit distance: {dist_c} ký tự)"
                        )
                        st.rerun()
                    if col_r.button("❌ Từ chối (Reject)", key=f"btn_rej_{aid}"):
                        db.record_action_decision(
                            aid,
                            "REJECTED",
                            reason_category=rej_reason,
                            note=f"Rejected via UI ({rej_reason})",
                            decided_by=reviewer_name,
                        )
                        st.rerun()


def render_page_reviews(db: DatabaseManager, scenario_tag: str) -> None:
    """Page 4: Review Explorer & Customer Care Reply Assistant."""
    st.header("💬 Trang 4: Tra Cứu Đánh Giá & Trợ Lý Phản Hồi CSKH (Reply Assistant)")
    col1, col2 = st.columns(2)
    platform_filter = col1.selectbox("Lọc theo Sàn TMĐT", ["Tất cả", "tiktok", "shopee"])
    sentiment_filter = col2.selectbox(
        "Lọc theo Cảm xúc tổng thể", ["Tất cả", "negative", "positive", "neutral"]
    )

    query = "SELECT * FROM reviews WHERE scenario_tag = ?"
    params: list[Any] = [scenario_tag]
    if platform_filter != "Tất cả":
        query += " AND platform = ?"
        params.append(platform_filter)
    if sentiment_filter != "Tất cả":
        query += " AND overall_sentiment = ?"
        params.append(sentiment_filter)
    query += " ORDER BY rating ASC, review_id ASC LIMIT 50"

    with db.get_connection(read_only=True) as conn:
        rows = conn.execute(query, tuple(params)).fetchall()

    for r in rows:
        rid = str(r["review_id"])
        with st.container(border=True):
            st.markdown(
                f"**`{rid}`** | Sàn: `{str(r['platform']).upper()}` | "
                f"Đánh giá: **{r['rating']} ⭐** | Cảm xúc: `{r['overall_sentiment']}`"
            )
            st.write(r["text_raw"])

            # Customer Care Reply Assistant Section
            if str(r["overall_sentiment"]) == "negative" or int(r["rating"] or 5) <= 3:
                reply_data = generate_customer_reply(
                    review_id=rid,
                    scenario_tag=scenario_tag,
                    mode="template",
                    db=db,
                )
                guard_rep = reply_data.get("guardrail_report", {})
                passed_badge = (
                    "🟢 ĐẠT CHUẨN G1-G6" if guard_rep.get("passed") else "🔴 CẦN KIỂM TRA"
                )

                mode_str = reply_data.get("mode_used")
                st.info(
                    f"🤖 **Gợi ý phản hồi CSKH ({passed_badge} | Chế độ: `{mode_str}`):**\n\n"
                    f"{reply_data.get('reply_text')}"
                )
                with st.expander(f"🛡️ Kiểm định Chính sách & An toàn CSKH ({rid})"):
                    st.json(guard_rep)


def render_page_ingest_and_reports(db: DatabaseManager, scenario_tag: str) -> None:
    """Page 5: CSV/Excel Data Ingestion & 1-Click Executive Report Export."""
    st.header("📥 Trang 5: Nhập Dữ Liệu Đánh Giá & Xuất Báo Cáo Tác Nghiệp")

    tab_upload, tab_export = st.tabs(
        ["📤 Tải Lên Tệp Đánh Giá (CSV / Excel)", "📊 Xuất Báo Cáo Điều Hành (Excel / HTML)"]
    )

    with tab_upload:
        st.subheader("1. Tải Lên Danh Sách Đánh Giá Khách Hàng")
        uploaded_file = st.file_uploader(
            "Chọn tệp CSV hoặc Excel (Shopee / TikTok Shop export):",
            type=["csv", "xlsx", "xls"],
        )
        if uploaded_file:
            try:
                if uploaded_file.name.endswith(".csv"):
                    df_up = pd.read_csv(uploaded_file)
                else:
                    df_up = pd.read_excel(uploaded_file)
                st.success(f"Đã đọc thành công {len(df_up):,} dòng dữ liệu từ tệp.")
                st.dataframe(df_up.head(5), use_container_width=True)

                cols = list(df_up.columns)
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                text_col = col_m1.selectbox(
                    "Cột Nội Dung Review:",
                    cols,
                    index=next(
                        (
                            i
                            for i, c in enumerate(cols)
                            if any(k in c.lower() for k in ["text", "comment", "nội dung"])
                        ),
                        0,
                    ),
                )
                rating_col = col_m2.selectbox(
                    "Cột Điểm Đánh Giá (1-5 sao):",
                    cols,
                    index=next(
                        (
                            i
                            for i, c in enumerate(cols)
                            if any(k in c.lower() for k in ["rating", "sao", "score"])
                        ),
                        0,
                    ),
                )
                platform_col = col_m3.selectbox(
                    "Cột Sàn TMĐT:",
                    ["Mặc định TikTok"] + cols,
                )
                method_choice = col_m4.selectbox(
                    "Mô hình ABSA phân tích:",
                    ["a1_gemini_v2", "b1_rule", "b2_tfidf", "b3_visobert"],
                )

                if st.button("🚀 Bắt Đầu Làm Sạch & Phân Tích Dữ Liệu", type="primary"):
                    with st.spinner("Đang xử lý, khử khuẩn PII và phân tích ABSA..."):
                        review_items = []
                        for idx, row_item in df_up.iterrows():
                            rid = (
                                str(row_item.get("review_id") or row_item.get("id"))
                                if "review_id" in row_item or "id" in row_item
                                else f"up_{idx:04d}"
                            )
                            plat_val = (
                                str(row_item[platform_col])
                                if platform_col != "Mặc định TikTok" and platform_col in row_item
                                else "tiktok"
                            )
                            review_items.append(
                                {
                                    "review_id": rid,
                                    "platform": plat_val,
                                    "rating": int(row_item[rating_col])
                                    if rating_col in row_item and pd.notna(row_item[rating_col])
                                    else 5,
                                    "text": str(row_item[text_col]),
                                }
                            )
                        ingest_res = ingest_review_batch(
                            db=db,
                            reviews=review_items,
                            scenario_tag=scenario_tag,
                            analyzer_method=method_choice,
                        )
                        st.success(
                            f"Đã nạp thành công {ingest_res['inserted_count']} đánh giá "
                            f"vào kịch bản `{scenario_tag}`!"
                        )
                        st.rerun()
            except Exception as e:
                st.error(f"Lỗi khi xử lý tệp: {e}")

    with tab_export:
        st.subheader("2. Xuất Báo Cáo Tác Nghiệp Chuẩn Mực")
        st.write(
            "Báo cáo được trích xuất tự động từ cơ sở dữ liệu, bao gồm các chỉ số KPI, "
            "phân tích sai số Wilson 95% CI, toàn bộ nhận định Insights và hành động đã kiểm định."
        )

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.markdown("#### 📗 Tệp Excel Tổng Hợp (.xlsx)")
            st.caption(
                "Gồm 6 Sheet: KPI, 8 Khía Cạnh, Insights, Action Plan, Cảnh Báo, So Sánh Sàn."
            )
            xlsx_bytes = build_excel_report(scenario_tag=scenario_tag, db=db)
            st.download_button(
                label="📥 Tải Xuống Báo Cáo Excel (.xlsx)",
                data=xlsx_bytes,
                file_name=f"EcomReview_BaoCao_{scenario_tag}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        with col_e2:
            st.markdown("#### 📄 Báo Cáo Trình Duyệt / In Ra PDF (.html)")
            st.caption("Trang báo cáo tinh gọn có sẵn nút in trực tiếp ra tệp PDF chuẩn trang in.")
            html_content = build_html_report(scenario_tag=scenario_tag, db=db)
            st.download_button(
                label="📥 Tải Xuống Báo Cáo HTML (In Ra PDF)",
                data=html_content.encode("utf-8"),
                file_name=f"EcomReview_BaoCao_{scenario_tag}.html",
                mime="text/html",
                use_container_width=True,
            )


def main() -> None:
    """Main Streamlit entrypoint."""
    st.set_page_config(
        page_title="EcomReview AI — Raincoat SME Decision Intelligence",
        page_icon="🌧️",
        layout="wide",
    )
    db = get_db()

    st.sidebar.title("🌧️ EcomReview AI")
    st.sidebar.caption("Hệ thống ABSA & Hoạch định Hành động có Căn cứ cho SMEs")

    with db.get_connection(read_only=True) as conn:
        scen_rows = conn.execute(
            "SELECT DISTINCT scenario_tag FROM reviews ORDER BY scenario_tag ASC"
        ).fetchall()
    scenarios = [str(r["scenario_tag"]) for r in scen_rows] or ["real_shop"]
    default_idx = scenarios.index("real_shop") if "real_shop" in scenarios else 0
    scenario_tag = st.sidebar.selectbox(
        "Chọn Kịch bản Dữ liệu (`scenario_tag`):", scenarios, index=default_idx
    )

    reviewer_name = st.sidebar.text_input(
        "👤 Tên Người Duyệt (Reviewer ID):",
        value="Chủ Shop Áo Mưa",
        help="Ghi nhận vào nhật ký kiểm toán Human Approval Gate khi phê duyệt/từ chối hành động.",
    )

    page = st.sidebar.radio(
        "Điều hướng 5 Trang Chức Năng:",
        [
            "1. 📊 Tổng Quan Điều Hành & Cảnh Báo",
            "2. 💡 Nhận Định Có Căn Cứ (Insights)",
            "3. 🎯 Trung Tâm Hành Động & Critic",
            "4. 💬 Tra Cứu Đánh Giá & Trợ Lý CSKH",
            "5. 📥 Nhập Dữ Liệu & Xuất Báo Cáo",
        ],
    )

    if page.startswith("1."):
        render_page_overview(db, scenario_tag)
    elif page.startswith("2."):
        render_page_insights(db, scenario_tag)
    elif page.startswith("3."):
        render_page_actions(db, scenario_tag, reviewer_name=reviewer_name)
    elif page.startswith("4."):
        render_page_reviews(db, scenario_tag)
    else:
        render_page_ingest_and_reports(db, scenario_tag)


if __name__ == "__main__":
    main()

# CreBy: MenBoyBMN
