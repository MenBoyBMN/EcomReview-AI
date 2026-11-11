# ruff: noqa: E501
"""Automated 1080p Demo Video Generator for EcomReview AI (Task 9.5).

Renders the 7-scene presentation and dashboard walkthrough (5m30s = 330 seconds,
1920x1080 Full HD, H.264 MP4) with embedded experiment charts and Vietnamese subtitles
into `demo/EcomReview_AI_Demo.mp4`.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

SCENES: list[dict[str, Any]] = [
    {
        "scene_id": 1,
        "duration_sec": 45,
        "header": "CẢNH 1/7: TỔNG QUAN ĐỀ TÀI & BÀI TOÁN THỰC TIỄN TRÊN SHOPEE / TIKTOK SHOP",
        "title": "EcomReview AI: Hệ Thống AI Agent Phân Tích Đánh Giá Tiếng Việt & Đề Xuất Marketing Cho SME",
        "bullets": [
            "• Bài toán thực tế: Chủ shop Áo mưa nhỏ (SME) quá tải trước hàng trăm đánh giá Teencode, Emoji và Phàn nàn ẩn.",
            "• 8 Khía cạnh chuyên sâu: WATERPROOF, MATERIAL_DURABILITY, FIT_SIZE, COMFORT_USABILITY, PRICE_VALUE, SHIPPING, SERVICE, DESIGN.",
            "• Mục tiêu kép: Chuẩn nghiên cứu khoa học (RQ1, RQ2, RQ3, Bootstrap 95% CI, Kappa = 0.8780) + Hệ thống Full-Stack Docker 1-Click.",
            "• Nguyên tắc bất biến #1: Zero Numeric Hallucination — 100% số liệu và Wilson 95% CI được tính bằng SQL trước khi qua LLM.",
        ],
        "subtitle": (
            "Xin chào Hội đồng chấm đồ án. EcomReview AI tự động phân tích phản hồi khách hàng tiếng Việt "
            "theo 8 khía cạnh ngành Áo mưa và lập kế hoạch hành động có căn cứ xác thực 100% cho doanh nghiệp nhỏ."
        ),
        "chart_path": "docs/report/figures/rq1_comparison.png",
    },
    {
        "scene_id": 2,
        "duration_sec": 45,
        "header": "CẢNH 2/7: KIẾN TRÚC ĐỒ THỊ TRẠNG THÁI THUẦN PYTHON & PHÒNG THỦ 4 LỚP",
        "title": "Pure Python State-Graph: SQL Aggregator -> InsightEngine -> Planner <-> HybridCritic (R1–R7)",
        "bullets": [
            "• Bảo mật 4 lớp chống Prompt Injection: Ẩn danh PII (scrub_pii) -> Bọc thẻ <customer_review> -> Pydantic v2 -> DB Read-Only.",
            "• Hậu kiểm số học kép: Hàm verify_numbers_in_statement() ở InsightEngine + Luật R2 ở HybridCritic (sai số số học = 0.0%).",
            "• Bộ phản biện lai 7 Luật Python (R1–R7): Chặn đứng 100% lỗi bịa mã review (R1), quá đà 'chống thấm 100%' (R4), mua chuộc 5 sao (R7).",
            "• Cơ chế Deterministic Auto-Repair: Tự động phục hồi và đồng bộ xác định, đảm bảo 100% kế hoạch đạt điểm Critic 5.0/5.0.",
        ],
        "subtitle": (
            "Hệ thống vận hành trên kiến trúc Pure Python State-Graph không phụ thuộc framework nặng, "
            "tích hợp 4 lớp bảo mật và bộ phản biện lai HybridCritic kiểm định 7 quy tắc R1 đến R7."
        ),
        "chart_path": "docs/report/figures/rq3_critic_ablation.png",
    },
    {
        "scene_id": 3,
        "duration_sec": 50,
        "header": "CẢNH 3/7: STREAMLIT DASHBOARD TRANG 1 — TỔNG QUAN & WILSON 95% CI",
        "title": "Trực Quan Hóa Bất Đối Xứng Wilson 95% CI & Phát Hiện Phàn Nàn Ẩn (real_shop = 150 Reviews)",
        "bullets": [
            "• Biểu đồ Plotly Asymmetric Error Bars: Phản ánh trung thực biên độ bất định thống kê khi cỡ mẫu từng khía cạnh khác nhau.",
            "• TOP_PAIN phát hiện tự động: WATERPROOF (50.0% tiêu cực, 95% CI: [29.0% - 71.0%]) & MATERIAL_DURABILITY (17.8% tiêu cực).",
            "• HIDDEN_COMPLAINT: Phát hiện 23 phàn nàn ẩn (17.0%) nằm lẫn bên trong 135 đánh giá 4–5 sao mà chủ shop thường bỏ sót.",
            "• PLATFORM_GAP: Phát hiện chênh lệch trải nghiệm 47.3% giữa Shopee (55.6% tiêu cực) và TikTok Shop (8.3% tiêu cực).",
        ],
        "subtitle": (
            "Trên Trang 1 của Dashboard với 150 đánh giá thực tế, hệ thống vẽ thanh sai số bất đối xứng Wilson 95% CI "
            "và bóc tách tự động 23 phàn nàn ẩn (17.0%) nằm trong nhóm đánh giá 4–5 sao."
        ),
        "chart_path": "docs/report/figures/rq2_ablation.png",
    },
    {
        "scene_id": 4,
        "duration_sec": 45,
        "header": "CẢNH 4/7: STREAMLIT DASHBOARD TRANG 2 — KHÁM PHÁ ĐÁNH GIÁ & BẰNG CHỨNG GỐC",
        "title": "Truy Vết Nguyên Văn Tiếng Nói Khách Hàng & Chọn Lọc Bằng Chứng Đa Dạng (Jaccard <= 0.70)",
        "bullets": [
            "• Lọc đa chiều theo Kịch bản (real_shop, S1..S10), Khía cạnh (8 Aspects) và Cực tính cảm xúc (Positive / Negative / Neutral).",
            "• Bộ chọn bằng chứng thông minh (evidence_selector.py): Loại bỏ bình luận trùng lặp bằng khoảng cách từ vựng Jaccard <= 0.70.",
            "• Minh chứng thực tế WATERPROOF: Mã review tts_0053, tts_0024, tts_0179, tts_0096 phản ánh nước ngấm đường may đáy quần.",
            "• Độ trung thực trích dẫn (Quote Fidelity): Đạt 97.4% trực tiếp từ A1-v2 và 100.0% sau bước hậu kiểm _post_validate_evidence.",
        ],
        "subtitle": (
            "Tại Trang 2, mọi nhận định đều gắn liền với các mã đánh giá thực tế và đoạn trích dẫn nguyên văn "
            "đã được ẩn danh số điện thoại PII và lọc chống trùng lặp Jaccard."
        ),
        "chart_path": "docs/report/figures/rq1_comparison.png",
    },
    {
        "scene_id": 5,
        "duration_sec": 50,
        "header": "CẢNH 5/7: STREAMLIT DASHBOARD TRANG 3 — KẾ HOẠCH HÀNH ĐỘNG & CỔNG DUYỆT HITL",
        "title": "Phân Tách Hành Động Marketing vs Vận Hành & Cổng Phê Duyệt Human-in-the-Loop",
        "bullets": [
            "• Nhóm Marketing (is_marketing=True): Sản xuất video test vải dù tổ ong (act_001), Infographic gài nẹp chắn nước 2 lớp (act_003).",
            "• Nhóm Sản phẩm/Vận hành (is_marketing=False): Phơi khử mùi nhựa PVC 24h tại kho (act_004), Gia cố keo ép nhiệt đáy quần (act_005).",
            "• Đầy đủ 4 thành phần bắt buộc: What to do, Why rationale (khớp 100% SQL), How & When (mốc 24h/48h/3 ngày) và KPI đo lường.",
            "• Cổng duyệt trực tiếp (Approve / Edit / Reject): Tự động tính khoảng cách chỉnh sửa edit_distance_chars và lưu bảng action_feedback.",
        ],
        "subtitle": (
            "Tại Trang 3, chủ shop xem xét từng đề xuất đã gắn kèm ít nhất 2 mã review bằng chứng thật "
            "và thực hiện phê duyệt Approve, chỉnh sửa Edit hoặc từ chối Reject ngay trên giao diện."
        ),
        "chart_path": "docs/report/figures/rq3_critic_ablation.png",
    },
    {
        "scene_id": 6,
        "duration_sec": 45,
        "header": "CẢNH 6/7: TRANG 4 (NẠP DỮ LIỆU & TRACE KIỂM ĐỊNH) & FASTAPI 10 ENDPOINTS",
        "title": "Minh Bạch Hóa Vết Thực Thi HybridCritic R1–R7 & Kiến Trúc OpenAPI 3.1 (< 150ms)",
        "bullets": [
            "• 10 RESTful Endpoints chuẩn OpenAPI 3.1 (/api/v1/health, /reviews/upload, /analyze/run, /stats/overview, /actions/generate...).",
            "• Quan sát trực tiếp Trace JSON trên Trang 4: Vòng 0 phát hiện lệch chỉ mục R2 -> Auto-Repair sửa thành công đạt 5.0/5.0.",
            "• Chế độ bảo hiểm DEMO_CACHE_MODE=true & Cache SHA-256: Chạy mượt mà 100% trên máy sạch không cần Internet hay API Key.",
            "• Mở rộng Local AI (Addon 11): Công tắc chuyển đổi trực tiếp giữa Cloud Gemini Flash và Local Ollama Qwen2.5-7B ngay trên Sidebar.",
        ],
        "subtitle": (
            "Trang 4 và tài liệu Swagger 10 Endpoints cho phép kiểm tra trực tiếp nhật ký Trace JSON của HybridCritic "
            "cùng công tắc chuyển đổi linh hoạt giữa Cloud Gemini Flash và Local AI Ollama."
        ),
        "chart_path": "docs/report/figures/error_pareto.png",
    },
    {
        "scene_id": 7,
        "duration_sec": 50,
        "header": "CẢNH 7/7: TỔNG KẾT KẾT QUẢ NGHIÊN CỨU (RQ1, RQ2, RQ3) & GIÁ TRỊ THỰC TIỄN",
        "title": "Hoàn Thành 12/12 Yêu Cầu Đề Bài — Tiết Kiệm 95% Thời Gian Cho Doanh Nghiệp Nhỏ",
        "bullets": [
            "• Kết quả RQ1: A1-v2 đạt Overall F1 = 0.8248 [0.7324 - 0.8983], Aspect Det F1 = 0.9066 (vượt B1, B2, B3 với p < 0.0001).",
            "• Kết quả RQ2: Chuẩn hóa giúp B3 tăng +12.05% và B2 tăng +17.69% trên lát cắt Emoji; FIX_01 triệt tiêu 100% lỗi từ ghép.",
            "• Kết quả RQ3: P1-Full đạt 100% trên cả 5 chỉ số Groundedness, thắng 10/10 kịch bản chấm mù A/B (Rubric 4.98/5.0 vs P0 2.17/5.0).",
            "• Khả thi vận hành (Case Study): Tỷ lệ chấp nhận đề xuất đạt 96.55% (28/29 hành động), giảm thời gian từ ~2–3 giờ xuống ~5 phút.",
        ],
        "subtitle": (
            "Tổng kết lại, EcomReview AI đã hoàn thành trọn vẹn 12/12 yêu cầu học thuật và kỹ thuật, "
            "đạt tỷ lệ chấp nhận 96.55% và giúp chủ shop SME rút ngắn 95% thời gian phân tích đánh giá. Xin cảm ơn!"
        ),
        "chart_path": "docs/report/figures/error_pareto.png",
    },
]


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf"]
        if bold
        else ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"]
    )
    for fp in candidates:
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def _render_scene_frame(scene: dict[str, Any], out_png: Path) -> None:
    """Render a 1920x1080 Full HD presentation slide with embedded chart and subtitle bar."""
    img = Image.new("RGB", (1920, 1080), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    # Top banner
    draw.rectangle([0, 0, 1920, 88], fill=(30, 58, 138))
    draw.text(
        (50, 24),
        str(scene["header"]),
        fill=(255, 255, 255),
        font=_load_font(28, bold=True),
    )
    draw.text(
        (1580, 28),
        "EcomReview AI v1.0 | FastAPI + Streamlit",
        fill=(191, 219, 254),
        font=_load_font(18, bold=True),
    )

    # Main content card (left side) and Chart card (right side)
    draw.rounded_rectangle(
        [40, 115, 1060, 895], radius=18, fill=(30, 41, 59), outline=(59, 130, 246), width=2
    )
    draw.rounded_rectangle(
        [1085, 115, 1880, 895], radius=18, fill=(255, 255, 255), outline=(59, 130, 246), width=2
    )

    # Title in left card
    f_title = _load_font(27, bold=True)
    title_words = str(scene["title"]).split()
    lines: list[str] = []
    cur = ""
    for w in title_words:
        if len(cur + " " + w) <= 58:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    y_cursor = 145
    for ln in lines:
        draw.text((70, y_cursor), ln, fill=(96, 165, 250), font=f_title)
        y_cursor += 38

    draw.line([(70, y_cursor + 10), (1030, y_cursor + 10)], fill=(71, 85, 105), width=2)
    y_cursor += 35

    # Bullets
    f_bullet = _load_font(22, bold=False)
    for b_text in scene["bullets"]:
        b_words = str(b_text).split()
        b_lines: list[str] = []
        b_cur = ""
        for bw in b_words:
            if len(b_cur + " " + bw) <= 68:
                b_cur = (b_cur + " " + bw).strip()
            else:
                b_lines.append(b_cur)
                b_cur = "   " + bw
        if b_cur:
            b_lines.append(b_cur)

        for bln in b_lines:
            draw.text((70, y_cursor), bln, fill=(241, 245, 249), font=f_bullet)
            y_cursor += 33
        y_cursor += 20

    # Embed chart on right card
    c_path = Path(str(scene["chart_path"]))
    if c_path.exists():
        c_img = Image.open(c_path).convert("RGB")
        c_img.thumbnail((765, 740))
        cx = 1085 + (795 - c_img.width) // 2
        cy = 115 + (780 - c_img.height) // 2
        img.paste(c_img, (cx, cy))

    # Bottom Subtitle Bar
    draw.rectangle([0, 920, 1920, 1080], fill=(9, 14, 26))
    draw.line([(0, 920), (1920, 920)], fill=(245, 158, 11), width=3)
    f_sub = _load_font(23, bold=True)
    sub_words = str(scene["subtitle"]).split()
    s_lines: list[str] = []
    s_cur = ""
    for sw in sub_words:
        if len(s_cur + " " + sw) <= 115:
            s_cur = (s_cur + " " + sw).strip()
        else:
            s_lines.append(s_cur)
            s_cur = sw
    if s_cur:
        s_lines.append(s_cur)

    sy = 948
    for sln in s_lines:
        draw.text(
            (70, sy), f"💬 {sln}" if sy == 948 else f"    {sln}", fill=(254, 240, 138), font=f_sub
        )
        sy += 36

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png, format="PNG")


def build_demo_video(output_mp4: str | Path = "demo/EcomReview_AI_Demo.mp4") -> dict[str, Any]:
    """Render 7 Full HD scene images and encode a 5m30s H.264 MP4 video using ffmpeg."""
    out_path = Path(output_mp4)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frames_dir = out_path.parent / "scenes"
    frames_dir.mkdir(parents=True, exist_ok=True)

    concat_lines: list[str] = []
    total_sec = 0
    last_png: Path | None = None

    for sc in SCENES:
        sid = int(sc["scene_id"])
        dur = int(sc["duration_sec"])
        total_sec += dur
        png_path = frames_dir / f"scene_{sid:02d}.png"
        _render_scene_frame(sc, png_path)
        concat_lines.append(f"file '{png_path.resolve().as_posix()}'")
        concat_lines.append(f"duration {dur}")
        last_png = png_path

    if last_png is not None:
        concat_lines.append(f"file '{last_png.resolve().as_posix()}'")

    concat_file = frames_dir / "scenes_concat.txt"
    concat_file.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")

    ffmpeg_bin = (
        shutil.which("ffmpeg") or "C:/Users/ASUS/AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe"
    )
    cmd = [
        ffmpeg_bin,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-vf",
        "fps=1,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "26",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    return {
        "video_path": str(out_path),
        "duration_seconds": total_sec,
        "scenes_count": len(SCENES),
        "size_bytes": out_path.stat().st_size,
    }


if __name__ == "__main__":
    info = build_demo_video()
    print(info)

# CreBy: MenBoyBMN
