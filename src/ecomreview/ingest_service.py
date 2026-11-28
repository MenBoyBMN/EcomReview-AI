"""Review ingestion service for the EcomReview AI FastAPI Backend."""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import os
import re
import unicodedata
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import openpyxl

from ecomreview.analyze.factory import get_analyzer
from ecomreview.billing.quota_service import (
    QuotaExceededError,
    check_and_resolve_analyzer_for_quota,
    record_batch_usage,
)
from ecomreview.db.database import DatabaseManager
from ecomreview.normalize import normalize_social_text
from ecomreview.schemas import AspectOpinion, Polarity
from ecomreview.security import scrub_pii

logger = logging.getLogger(__name__)

MAX_UPLOAD_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_UPLOAD_ROWS = 1000
MAX_ASYNC_UPLOAD_ROWS = 5000
DEFAULT_ANALYSIS_WORKERS = 6
DEFAULT_DB_BATCH_SIZE = 100


def _resolve_int_env(var_name: str, default: int, low: int = 1, high: int = 1000) -> int:
    raw = os.getenv(var_name, "").strip()
    if raw.isdigit():
        return max(low, min(high, int(raw)))
    return default


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
    },
    "variation": {
        "variation",
        "phan loai",
        "phan loai hang",
        "variant",
        "model name",
        "mau size",
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
        raw_prod = str(_cell(row, "product") or "").strip()
        raw_var = str(_cell(row, "variation") or "").strip()
        product_val = raw_prod or raw_var or default_product
        variation_val = raw_var
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
                "variation": variation_val,
                "rating": rating_val,
                "text": text_val,
                "created_at": created_val,
                "source": f"file_{suffix.lstrip('.')}",
            }
        )

    return valid_reviews, skipped_rows


def detect_review_anomalies(
    text_raw: str,
    norm_text: str,
    rating: int,
    opinions: list[dict[str, Any]],
    dup_count: int = 1,
) -> list[str]:
    """Flag spam, seeding duplicates, and hidden complaints in 4-5 star reviews."""
    flags: list[str] = []
    raw_s = (text_raw or "").strip()
    if re.search(r"(.)\1{5,}", raw_s):
        flags.append("SPAM_REPEATED_CHARS")
    elif len(raw_s) >= 8:
        non_space = [ch for ch in raw_s if not ch.isspace()]
        if non_space and (sum(1 for ch in non_space if ch.isalpha()) / len(non_space)) < 0.30:
            flags.append("SPAM_REPEATED_CHARS")

    if len((norm_text or "").strip()) >= 20 and dup_count >= 3:
        flags.append("SEEDING_DUPLICATE")

    if int(rating) >= 4 and any(
        str(op.get("polarity", "")).lower() == "negative" for op in opinions
    ):
        flags.append("HIDDEN_COMPLAINT")

    return flags


def ingest_review_batch(
    db: DatabaseManager,
    reviews: list[dict[str, Any]],
    scenario_tag: str = "real_shop",
    analyzer_method: str = "a1_gemini_v2",
    progress_callback: Callable[[int, int], None] | None = None,
    max_workers: int | None = None,
) -> dict[str, Any]:
    """Process, sanitize, analyze in parallel, and bulk-upsert a batch of reviews.

    Args:
        db: DatabaseManager instance.
        reviews: List of review dictionaries containing text, platform, rating, etc.
        scenario_tag: Target scenario partition.
        analyzer_method: Method identifier ('a1_gemini_v2', 'b1_rule', etc.).
        progress_callback: Optional callback invoked with (processed_count, total_count).
        max_workers: Optional bounded worker thread count for LLM/rule ABSA extraction.

    Returns:
        Summary dict containing inserted_count and analyzer_used.
    """
    effective_method = analyzer_method
    quota_fallback = False
    try:
        effective_method, quota_fallback, _ = check_and_resolve_analyzer_for_quota(
            db=db,
            scenario_tag=scenario_tag,
            requested_method=analyzer_method,
            batch_size=len(reviews),
        )
    except QuotaExceededError:
        raise
    except Exception as exc:
        logger.debug("Quota check skipped for %s: %s", scenario_tag, exc)

    analyzer = get_analyzer(effective_method)
    actual_method = effective_method
    fallback_triggered = False

    seen_batch_sigs: dict[str, int] = {}
    prepared: list[dict[str, Any]] = []
    need_analysis_indices: list[int] = []

    for item in reviews:
        raw_text = str(item.get("text") or item.get("text_raw") or "").strip()
        if not raw_text:
            continue

        clean_raw = scrub_pii(raw_text)
        norm_txt = normalize_social_text(clean_raw, enable=True)
        platform = str(item.get("platform") or "tiktok").lower()
        shop = str(item.get("shop") or "shop_a")
        product = str(item.get("product") or "ao_mua_da_ca")
        variation = str(item.get("variation") or "").strip()[:160]
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
            prepared.append(
                {
                    "review_id": review_id,
                    "scenario_tag": scenario_tag,
                    "platform": platform,
                    "shop": shop,
                    "product": product,
                    "variation": variation,
                    "rating": rating,
                    "text_raw": clean_raw,
                    "text_norm": norm_txt,
                    "source": str(item.get("source") or "upload"),
                    "overall_sentiment": ov_sent,
                    "informative": bool(item.get("informative", True)),
                    "opinions": ops,
                    "analyzer_method": analyzer_method,
                    "created_at": str(created_at) if created_at else None,
                    "used_fallback": False,
                }
            )
        else:
            idx = len(prepared)
            prepared.append(
                {
                    "review_id": review_id,
                    "scenario_tag": scenario_tag,
                    "platform": platform,
                    "shop": shop,
                    "product": product,
                    "variation": variation,
                    "rating": rating,
                    "text_raw": clean_raw,
                    "text_norm": norm_txt,
                    "source": str(item.get("source") or "upload"),
                    "overall_sentiment_override": item.get("overall_sentiment"),
                    "overall_sentiment": "neutral",
                    "informative": True,
                    "opinions": [],
                    "analyzer_method": analyzer_method,
                    "created_at": str(created_at) if created_at else None,
                    "used_fallback": False,
                }
            )
            need_analysis_indices.append(idx)

    def _analyze_one(rec_idx: int) -> tuple[int, dict[str, Any]]:
        rec = prepared[rec_idx]
        res = analyzer.analyze_review(rec["text_raw"])
        used_fb = (
            bool(getattr(analyzer, "last_used_fallback", False))
            if hasattr(analyzer, "last_used_fallback")
            else bool(getattr(analyzer, "quota_exhausted", False))
        )
        fb_flag = bool(effective_method.startswith("a1") and used_fb)
        item_method = f"{effective_method}+b1_fallback" if fb_flag else effective_method
        ov_sent = rec["overall_sentiment_override"] or (
            res.overall_sentiment.value
            if isinstance(res.overall_sentiment, Polarity)
            else str(res.overall_sentiment)
        )
        ops = [
            {
                "aspect": op.aspect.value if hasattr(op.aspect, "value") else str(op.aspect),
                "polarity": op.polarity.value
                if hasattr(op.polarity, "value")
                else str(op.polarity),
                "evidence": op.evidence,
                "evidence_ok": getattr(op, "evidence_ok", True),
            }
            for op in res.opinions
        ]
        return rec_idx, {
            "overall_sentiment": ov_sent,
            "informative": bool(res.informative),
            "opinions": ops,
            "analyzer_method": item_method,
            "used_fallback": fb_flag,
        }

    if need_analysis_indices:
        configured_workers = (
            max_workers
            if max_workers is not None
            else _resolve_int_env("ECOMREVIEW_ANALYSIS_WORKERS", DEFAULT_ANALYSIS_WORKERS, 1, 16)
        )
        eff_workers = max(1, min(16, configured_workers, len(need_analysis_indices)))
        if eff_workers > 1 and len(need_analysis_indices) > 1:
            with ThreadPoolExecutor(max_workers=eff_workers) as pool:
                for rec_idx, patch in pool.map(_analyze_one, need_analysis_indices):
                    prepared[rec_idx].update(patch)
                    if patch["used_fallback"]:
                        fallback_triggered = True
        else:
            for rec_idx in need_analysis_indices:
                _, patch = _analyze_one(rec_idx)
                prepared[rec_idx].update(patch)
                if patch["used_fallback"]:
                    fallback_triggered = True

    norm_counts: dict[str, int] = {}
    for rec in prepared:
        key_n = str(rec.get("text_norm") or "").strip().lower()
        if key_n:
            norm_counts[key_n] = norm_counts.get(key_n, 0) + 1

    for rec in prepared:
        key_n = str(rec.get("text_norm") or "").strip().lower()
        rec["anomaly_flags"] = detect_review_anomalies(
            text_raw=str(rec.get("text_raw") or ""),
            norm_text=key_n,
            rating=int(rec.get("rating") or 5),
            opinions=list(rec.get("opinions") or []),
            dup_count=norm_counts.get(key_n, 1),
        )

    batch_size = _resolve_int_env("ECOMREVIEW_DB_BATCH_SIZE", DEFAULT_DB_BATCH_SIZE, 10, 500)
    inserted = 0
    total_prepared = len(prepared)
    for start in range(0, total_prepared, batch_size):
        chunk = prepared[start : start + batch_size]
        inserted += db.bulk_upsert_reviews_and_opinions(chunk, chunk_size=batch_size)
        if progress_callback is not None:
            progress_callback(inserted, len(reviews))

    if fallback_triggered:
        actual_method = f"{effective_method}+b1_fallback"
    elif quota_fallback:
        actual_method = "b1_rule+quota_fallback"

    llm_used_cnt = 0
    rule_used_cnt = 0
    for rec in prepared:
        rec_m = str(rec.get("analyzer_method") or "")
        if rec.get("used_fallback") or not rec_m.startswith("a1"):
            rule_used_cnt += 1
        else:
            llm_used_cnt += 1
    if inserted > 0:
        record_batch_usage(
            db=db,
            scenario_tag=scenario_tag,
            llm_count=llm_used_cnt,
            rule_count=rule_used_cnt,
        )

    return {
        "scenario_tag": scenario_tag,
        "inserted_count": inserted,
        "analyzer_method": actual_method if inserted > 0 else effective_method,
        "quota_fallback": quota_fallback,
    }


# CreBy: MenBoyBMN
