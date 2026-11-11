"""Streamlit 4-Page Executive Dashboard for EcomReview AI.

Pages:
1. Executive Overview (KPIs + Plotly Asymmetric Wilson 95% CI Error Bars + Platform Gap)
2. Evidence-Grounded Insights (5 Insight Categories + Number Verification Badge + Verbatim Quotes)
3. Action Center & Critic Trace (Marketing vs Product/Ops Tabs + R1-R7 Trace + Human Approval Gate)
4. Review Explorer & Reply Assistant (ABSA Filter + Automated CSKH Reply Drafts)
"""

from __future__ import annotations

import json
import os
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ecomreview.agent.graph_runner import EcomReviewGraphRunner
from ecomreview.agent.insight_engine import ASPECT_VN_LABELS
from ecomreview.agent.tools_aggregator import (
    get_aspect_sentiment_stats,
    get_platform_gap_stats,
    wilson_ci_pct,
)
from ecomreview.db.database import DatabaseManager


def get_db() -> DatabaseManager:
    """Return configured DatabaseManager instance."""
    return DatabaseManager(os.getenv("ECOMREVIEW_SQLITE_PATH"))


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
        height=420,
        margin={"l": 20, "r": 20, "t": 50, "b": 30},
    )
    return fig


def render_page_overview(db: DatabaseManager, scenario_tag: str) -> None:
    """Page 1: Executive Overview with Asymmetric Wilson 95% CI Error Bars."""
    st.header("📊 Trang 1: Tổng Quan Điều Hành (Executive Overview)")
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
    neg_pct = round((neg / total) * 100.0, 1) if total else 0.0
    ci_low, ci_high = wilson_ci_pct(neg, total)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Tổng số Đánh giá",
        f"{total}",
        f"Shopee: {row['shopee'] or 0} | TikTok: {row['tiktok'] or 0}",
    )
    c2.metric("Điểm Sao Trung Bình", f"{avg_rating:.2f} ⭐")
    c3.metric("Tỷ lệ Tích cực", f"{(pos / total * 100) if total else 0:.1f}%", f"{pos} đánh giá")
    c4.metric(
        "Tỷ lệ Phàn nàn (Wilson 95% CI)",
        f"{neg_pct:.1f}%",
        f"[{ci_low:.1f}% – {ci_high:.1f}%]",
        delta_color="inverse",
    )

    stats = get_aspect_sentiment_stats(scenario_tag=scenario_tag, min_n=3, db=db)
    if stats:
        fig = build_asymmetric_wilson_chart(stats)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(pd.DataFrame(stats), use_container_width=True)
    else:
        st.info("Chưa có đủ dữ liệu cho kịch bản này.")

    gaps = get_platform_gap_stats(scenario_tag=scenario_tag, min_n=3, db=db)
    if gaps:
        st.subheader("🔄 So Sánh Chênh Lệch Giữa Shopee & TikTok Shop")
        st.dataframe(pd.DataFrame(gaps), use_container_width=True)


def render_page_insights(db: DatabaseManager, scenario_tag: str) -> None:
    """Page 2: Evidence-Grounded Insights with verbatim customer quotes."""
    st.header("💡 Trang 2: Nhận Định Kinh Doanh Có Căn Cứ (Evidence-Grounded Insights)")
    with db.get_connection(read_only=True) as conn:
        rows = conn.execute(
            "SELECT * FROM insights WHERE scenario_tag = ? ORDER BY id ASC",
            (scenario_tag,),
        ).fetchall()

    if not rows:
        st.warning("Chưa có Insights cho kịch bản này. Hãy nhấn nút Chạy State-Graph ở thanh bên.")
        return

    for r in rows:
        nums = json.loads(r["numbers"] or "{}")
        ev_ids = json.loads(r["evidence_ids"] or "[]")
        with st.container(border=True):
            st.markdown(
                f"### `[{r['kind']}]` Khía cạnh: **{r['aspect']}** "
                f"— Độ tin cậy: `{str(r['confidence']).upper()}` "
                f"✅ *Verified SQL Numbers*"
            )
            st.write(r["statement"])
            st.caption(f"Số liệu gốc SQL (`numbers`): `{json.dumps(nums, ensure_ascii=False)}`")
            with st.expander(
                f"🔎 Xem {len(ev_ids)} Đánh Giá Bằng Chứng Nguyên Văn ({', '.join(ev_ids)})"
            ):
                with db.get_connection(read_only=True) as conn:
                    placeholders = ",".join("?" for _ in ev_ids)
                    revs = conn.execute(
                        f"SELECT review_id, platform, rating, text_raw FROM reviews "
                        f"WHERE scenario_tag = ? AND review_id IN ({placeholders})",
                        (scenario_tag, *ev_ids),
                    ).fetchall()
                for rv in revs:
                    st.markdown(
                        f"- **`{rv['review_id']}`** ({rv['platform'].upper()}, {rv['rating']}⭐): "
                        f'*"{rv["text_raw"]}"*'
                    )


def render_page_actions(db: DatabaseManager, scenario_tag: str) -> None:
    """Page 3: Action Center, Hybrid Critic R1-R7 Trace, and Human Approval Gate."""
    st.header("🎯 Trang 3: Trung Tâm Hành Động & Kiểm Định Hybrid Critic (R1–R7)")

    if st.button("🚀 Chạy Lại Vòng Lặp Planner ⇄ Hybrid Critic (State-Graph)", type="primary"):
        active_engine = st.session_state.get("engine_mode", "gemini")
        runner = EcomReviewGraphRunner(db=db, max_retries=2)
        res = runner.run_scenario(scenario_tag=scenario_tag, min_n=3, persist_db=True)
        st.success(
            f"Đã hoàn tất State-Graph ({active_engine.upper()}) trong {res['duration_ms']} ms | "
            f"Critic Passed: {res['final_critic_passed']} (Score: {res['final_critic_score']}/5.0)"
        )

    with db.get_connection(read_only=True) as conn:
        rows = conn.execute(
            "SELECT * FROM actions WHERE scenario_tag = ? ORDER BY priority_score DESC, id ASC",
            (scenario_tag,),
        ).fetchall()

    if not rows:
        st.info("Chưa có đề xuất hành động nào. Hãy nhấn nút Chạy State-Graph phía trên.")
        return

    tab_mkt, tab_ops = st.tabs(
        [
            "📣 Hành Động Marketing (`is_marketing = True`)",
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
                trace = json.loads(r["critic_trace"] or "{}")
                ev_ids = json.loads(r["evidence_review_ids"] or "[]")
                with st.container(border=True):
                    st.markdown(
                        f"#### `[{r['action_type']}]` {r['title']} "
                        f"(Priority: **`{r['priority_score']}`** | "
                        f"Trạng thái: **`{r['status']}`**)"
                    )
                    st.markdown(f"- **Việc cần làm (`what_to_do`):** {r['what_to_do']}")
                    st.markdown(f"- **Căn cứ số liệu (`why_rationale`):** {r['why_rationale']}")
                    st.markdown(f"- **Cách làm & Thời hạn (`how_and_when`):** {r['how_and_when']}")
                    st.markdown(f"- **Chỉ số đo lường (`success_metric`):** {r['success_metric']}")
                    c_sc = trace.get("critic_score", 5.0)
                    c_rt = trace.get("retries", 0)
                    st.caption(
                        f"Effort: `{r['effort']}` | Impact: `{r['impact']}` | "
                        f"Evidence IDs: `{', '.join(ev_ids)}` | "
                        f"Critic Score: `{c_sc}/5.0` (Retries: `{c_rt}`)"
                    )
                    with st.expander("🛡️ Xem Nhật Ký Kiểm Định Hybrid Critic (R1–R7 Trace JSON)"):
                        st.json(trace)

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
                        db.record_action_decision(aid, "APPROVED", note="Approved via UI")
                        st.rerun()
                    if col_e.button("✏️ Sửa & Duyệt (Edit & Approve)", key=f"btn_edt_{aid}"):
                        res_dec = db.record_action_decision(
                            aid, "EDITED", edited_content=edited_txt, note="Edited via UI"
                        )
                        dist_c = res_dec["edit_distance_chars"]
                        st.success(f"Đã lưu chỉnh sửa (Edit distance: {dist_c} ký tự)")
                        st.rerun()
                    if col_r.button("❌ Từ chối (Reject)", key=f"btn_rej_{aid}"):
                        db.record_action_decision(
                            aid,
                            "REJECTED",
                            reason_category=rej_reason,
                            note=f"Rejected via UI ({rej_reason})",
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
        with st.container(border=True):
            st.markdown(
                f"**`{r['review_id']}`** | Sàn: `{str(r['platform']).upper()}` | "
                f"Đánh giá: **{r['rating']} ⭐** | Cảm xúc: `{r['overall_sentiment']}`"
            )
            st.write(r["text_raw"])
            if str(r["overall_sentiment"]) == "negative" or int(r["rating"] or 5) <= 3:
                reply_draft = (
                    f"Dạ Shop Áo Mưa xin chân thành cáo lỗi cùng Quý khách về trải nghiệm "
                    f"chưa trọn vẹn ở đơn hàng ({r['review_id']}). Shop đã ghi nhận phản hồi "
                    f"và xin phép hỗ trợ bảo hành đổi mới 1-1 miễn phí qua cổng Chat của sàn "
                    f"trong vòng 24h ạ!"
                )
                st.info(f"🤖 **Gợi ý phản hồi CSKH chuẩn mực:**\n\n{reply_draft}")


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

    from ecomreview.llm_provider import EngineMode, check_ollama_health

    engine_choice = st.sidebar.selectbox(
        "AI Engine Backend (Addon 11):",
        [
            "Cloud API: Gemini Flash (Default)",
            "Local AI: Ollama Qwen2.5-7B (Offline)",
        ],
    )
    if "Ollama" in engine_choice:
        st.session_state["engine_mode"] = EngineMode.OLLAMA_LOCAL.value
        health = check_ollama_health(timeout_sec=0.8)
        if health["online"]:
            st.sidebar.success(f"🟢 Ollama Online ({health['base_url']})")
        else:
            st.sidebar.warning(
                "🟡 Ollama chưa bật tại localhost:11434 — tự động dùng Cache/Fallback an toàn."
            )
    else:
        st.session_state["engine_mode"] = EngineMode.GEMINI_CLOUD.value

    page = st.sidebar.radio(
        "Điều hướng 4 Trang Chức Năng:",
        [
            "1. Tổng Quan Điều Hành",
            "2. Nhận Định Có Căn Cứ (Insights)",
            "3. Trung Tâm Hành Động & Critic",
            "4. Tra Cứu Review & Trợ Lý CSKH",
        ],
    )

    if page.startswith("1."):
        render_page_overview(db, scenario_tag)
    elif page.startswith("2."):
        render_page_insights(db, scenario_tag)
    elif page.startswith("3."):
        render_page_actions(db, scenario_tag)
    else:
        render_page_reviews(db, scenario_tag)


if __name__ == "__main__":
    main()

# CreBy: MenBoyBMN
