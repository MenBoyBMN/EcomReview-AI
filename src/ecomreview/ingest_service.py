"""Review ingestion service for the EcomReview AI FastAPI Backend."""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

import openpyxl

from ecomreview.analyze.factory import get_analyzer
from ecomreview.db.database import DatabaseManager
from ecomreview.normalize import normalize_social_text
from ecomreview.schemas import AspectOpinion, Polarity
from ecomreview.security import scrub_pii

logger = logging.getLogger(__name__)

MAX_UPLOAD_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_UPLOAD_ROWS = 1000
MAX_ASYNC_UPLOAD_ROWS = 5000

_COLUMN_ALIASES: dict[str, set[str]] = {
    "review_id": {
        "review_id",
        "id",
        "ma danh gia",
        "ma don hang",
        "order_id",
        "order id",
        "order sn",
        "order number",
        "review id",
        "comment id",
    },
    "text": {
        "text",
        "text_raw",
        "comment",
        "binh luan",
        "noi dung",
        "noi dung danh gia",
        "danh gia",
        "danh gia cua nguoi mua",
        "review",
        "review text",
        "review content",
        "buyer comment",
        "content",
    },
    "rating": {
        "rating",
        "star",
        "stars",
        "so sao",
        "danh gia sao",
        "diem",
        "diem danh gia",
        "score",
        "buyer rating",
        "rating star",
        "product rating",
    },
    "platform": {"platform", "san", "kenh", "channel", "kenh ban"},
    "shop": {"shop", "gian hang", "store", "shop name", "ten shop"},
    "product": {
        "product",
        "ten san pham",
        "san pham",
        "sku",
        "product name",
        "item name",
        "phan loai hang",
        "variation",
    },
    "created_at": {
        "created_at",
        "date",
        "ngay",
        "ngay danh gia",
        "thoi gian",
        "thoi gian danh gia",
        "review time",
        "review date",
        "create time",
    },
}


def _normalize_header(raw: Any) -> str:
    """Normalize spreadsheet/CSV column header to lowercase ASCII tokens."""
    txt = str(raw or "").strip().lower().replace("_", " ")
    txt = unicodedata.normalize("NFD", txt)
    txt = "".join(ch for ch in txt if unicodedata.category(ch) != "Mn")
    txt = txt.replace("đ", "d")
    return re.sub(r"\s+", " ", txt)


def _map_headers(headers: list[Any]) -> dict[str, int]:
    """Map canonical review fields to 0-based column indices."""
    col_map: dict[str, int] = {}
    for idx, h in enumerate(headers):
        norm_h = _normalize_header(h)
        if not norm_h:
            continue
        for canonical, aliases in _COLUMN_ALIASES.items():
            norm_aliases = {a.replace("_", " ") for a in aliases}
            if norm_h in norm_aliases and canonical not in col_map:
                col_map[canonical] = idx
                break
    return col_map


def _parse_rating(raw_val: Any) -> int | None:
    """Parse integer rating 1..5 from int/float/string (e.g. '5 sao')."""
    if isinstance(raw_val, bool):
        return None
    if raw_val is None or str(raw_val).strip() == "":
        return 5
    txt = str(raw_val).strip()
    try:
        fval = float(txt)
        if 1.0 <= fval <= 5.0:
            return round(fval)
        return None
    except ValueError:
        m = re.match(r"^([1-5])(?:\s*sao)?$", txt, re.IGNORECASE)
        return int(m.group(1)) if m else None


def parse_review_file(
    filename: str,
    content: bytes,
    default_platform: str = "shopee",
    default_shop: str = "shop_aomua",
    default_product: str = "ao_mua_da_ca",
    max_rows: int = MAX_UPLOAD_ROWS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse an uploaded .csv or .xlsx review batch into valid records and skipped rows."""
    if len(content) > MAX_UPLOAD_FILE_BYTES:
        raise ValueError("Kích thước tệp vượt quá giới hạn 5 MB.")

    suffix = Path(filename or "").suffix.lower()
    stem = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(filename or "upload").stem)[:24] or "upload"

    raw_rows: list[list[Any]] = []
    if suffix == ".csv":
        decoded = ""
        for enc in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
            try:
                decoded = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if not decoded.strip():
            raise ValueError("Tệp CSV rỗng hoặc không thể giải mã ký tự.")
        reader = csv.reader(io.StringIO(decoded))
        raw_rows = [list(r) for r in reader]
    elif suffix == ".xlsx":
        try:
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:
            raise ValueError(f"Không thể đọc tệp Excel (.xlsx): {exc}") from exc
        try:
            ws = wb.active
            if ws is None:
                raise ValueError("Tệp Excel không có sheet dữ liệu hợp lệ.")
            raw_rows = [list(r) for r in ws.iter_rows(values_only=True)]
        finally:
            wb.close()
    else:
        raise ValueError("Định dạng không được hỗ trợ. Chỉ chấp nhận tệp .csv hoặc .xlsx.")

    non_empty_rows = [r for r in raw_rows if any(c is not None and str(c).strip() for c in r)]
    if len(non_empty_rows) < 2:
        raise ValueError("Tệp phải có ít nhất 1 dòng tiêu đề và 1 dòng dữ liệu đánh giá.")

    col_map = _map_headers(non_empty_rows[0])
    if "text" not in col_map:
        raise ValueError(
            "Không tìm thấy cột nội dung đánh giá (hỗ trợ: text, binh_luan, noi_dung, comment)."
        )

    data_rows = non_empty_rows[1:]
    if len(data_rows) > max_rows:
        raise ValueError(f"Số lượng dòng vượt quá giới hạn tối đa {max_rows} dòng/lần tải.")

    valid_reviews: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []

    def _cell(row: list[Any], field: str) -> Any:
        idx = col_map.get(field)
        return row[idx] if idx is not None and idx < len(row) else None

    seen_content_counts: dict[str, int] = {}
    for row_idx, row in enumerate(data_rows, start=2):
        text_val = str(_cell(row, "text") or "").strip()
        if not text_val:
            skipped_rows.append({"row": row_idx, "reason": "Nội dung bình luận trống"})
            continue

        rating_val = _parse_rating(_cell(row, "rating"))
        if rating_val is None:
            skipped_rows.append({"row": row_idx, "reason": "Số sao (rating) không hợp lệ (1-5)"})
            continue

        platform_val = str(_cell(row, "platform") or default_platform).strip().lower()
        shop_val = str(_cell(row, "shop") or default_shop).strip() or default_shop
        product_val = str(_cell(row, "product") or default_product).strip() or default_product
        created_raw = _cell(row, "created_at")
        created_str = str(created_raw).strip() if created_raw is not None else ""
        created_val = created_str[:10] if created_str else None

        raw_rid = _cell(row, "review_id")
        if raw_rid is not None and str(raw_rid).strip():
            review_id = str(raw_rid).strip()
        else:
            sig = f"{platform_val}|{rating_val}|{created_val or ''}|{text_val}"
            occ = seen_content_counts.get(sig, 0)
            seen_content_counts[sig] = occ + 1
            dedup_input = sig if occ == 0 else f"{sig}#{occ}"
            review_id = f"{stem}_{hashlib.sha256(dedup_input.encode('utf-8')).hexdigest()[:8]}"

        valid_reviews.append(
            {
                "review_id": review_id,
                "platform": platform_val,
                "shop": shop_val,
                "product": product_val,
                "rating": rating_val,
                "text": text_val,
                "created_at": created_val,
                "source": f"file_{suffix.lstrip('.')}",
            }
        )

    return valid_reviews, skipped_rows


def ingest_review_batch(
    db: DatabaseManager,
    reviews: list[dict[str, Any]],
    scenario_tag: str = "real_shop",
    analyzer_method: str = "a1_gemini_v2",
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Process, sanitize, analyze, and upsert a batch of customer reviews into database.

    Args:
        db: DatabaseManager instance.
        reviews: List of review dictionaries containing text, platform, rating, etc.
        scenario_tag: Target scenario partition.
        analyzer_method: Method identifier ('a1_gemini_v2', 'b1_rule', etc.).

    Returns:
        Summary dict containing inserted_count and analyzer_used.
    """
    analyzer = get_analyzer(analyzer_method)
    inserted = 0
    actual_method = analyzer_method
    fallback_triggered = False

    seen_batch_sigs: dict[str, int] = {}
    for item in reviews:
        raw_text = str(item.get("text") or item.get("text_raw") or "").strip()
        if not raw_text:
            continue

        clean_raw = scrub_pii(raw_text)
        norm_txt = normalize_social_text(clean_raw, enable=True)
        platform = str(item.get("platform") or "tiktok").lower()
        shop = str(item.get("shop") or "shop_a")
        product = str(item.get("product") or "ao_mua_da_ca")
        parsed_rating = _parse_rating(item.get("rating"))
        rating = parsed_rating if parsed_rating is not None else 5
        created_at = item.get("created_at")

        raw_rid = item.get("review_id")
        if raw_rid is not None and str(raw_rid).strip() and str(raw_rid).strip().lower() != "none":
            review_id = str(raw_rid).strip()
        else:
            sig = f"{platform}|{rating}|{clean_raw}"
            occ = seen_batch_sigs.get(sig, 0)
            seen_batch_sigs[sig] = occ + 1
            dedup_key = sig if occ == 0 else f"{sig}#{occ}"
            review_id = f"rev_{hashlib.sha256(dedup_key.encode('utf-8')).hexdigest()[:10]}"

        opinions = item.get("opinions")
        item_method = analyzer_method
        if opinions:
            ops: list[dict[str, Any]] = []
            raw_lower = clean_raw.lower()
            norm_lower = norm_txt.lower()
            for op in opinions:
                if not isinstance(op, dict):
                    continue
                ev_str = scrub_pii(str(op.get("evidence") or clean_raw[:30])).strip()
                validated_op = AspectOpinion.model_validate(
                    {
                        "aspect": str(op.get("aspect", "GENERAL")).upper(),
                        "polarity": str(op.get("polarity", "neutral")).lower(),
                        "evidence": ev_str or clean_raw[:30],
                    }
                )
                ev_lower = validated_op.evidence.strip().lower()
                ev_ok = bool(ev_lower and (ev_lower in raw_lower or ev_lower in norm_lower))
                ops.append(
                    {
                        "aspect": validated_op.aspect.value,
                        "polarity": validated_op.polarity.value,
                        "evidence": validated_op.evidence,
                        "evidence_ok": ev_ok,
                    }
                )
            if item.get("overall_sentiment"):
                ov_sent = str(item.get("overall_sentiment")).lower()
            elif rating <= 2:
                ov_sent = "negative"
            elif rating == 3:
                ov_sent = "neutral"
            else:
                ov_sent = "positive"
            info_flag = bool(item.get("informative", True))
        else:
            res = analyzer.analyze_review(clean_raw)
            # Track fallback if analyzer was a1 (Gemini or Ollama) and fell back to B1 rule
            used_fb = (
                bool(getattr(analyzer, "last_used_fallback", False))
                if hasattr(analyzer, "last_used_fallback")
                else bool(getattr(analyzer, "quota_exhausted", False))
            )
            if analyzer_method.startswith("a1") and used_fb:
                item_method = f"{analyzer_method}+b1_fallback"
                fallback_triggered = True

            ov_sent = item.get("overall_sentiment") or (
                res.overall_sentiment.value
                if isinstance(res.overall_sentiment, Polarity)
                else str(res.overall_sentiment)
            )
            info_flag = bool(res.informative)
            ops = [
                {
                    "aspect": op.aspect.value if hasattr(op.aspect, "value") else str(op.aspect),
                    "polarity": (
                        op.polarity.value if hasattr(op.polarity, "value") else str(op.polarity)
                    ),
                    "evidence": op.evidence,
                    "evidence_ok": getattr(op, "evidence_ok", True),
                }
                for op in res.opinions
            ]

        db.upsert_review_and_opinions(
            review_id=review_id,
            platform=platform,
            shop=shop,
            product=product,
            rating=rating,
            text_raw=clean_raw,
            text_norm=norm_txt,
            source=str(item.get("source") or "upload"),
            scenario_tag=scenario_tag,
            overall_sentiment=ov_sent,
            informative=info_flag,
            opinions=ops,
            analyzer_method=item_method,
            created_at=str(created_at) if created_at else None,
        )
        inserted += 1
        if progress_callback is not None:
            progress_callback(inserted, len(reviews))

    if fallback_triggered:
        actual_method = f"{analyzer_method}+b1_fallback"

    return {
        "scenario_tag": scenario_tag,
        "inserted_count": inserted,
        "analyzer_method": actual_method if inserted > 0 else analyzer_method,
    }


# CreBy: MenBoyBMN
