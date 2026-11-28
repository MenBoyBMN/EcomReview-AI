"""Customer Care Reply Assistant with Deterministic Guardrails (G1 - G6)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from ecomreview.agent.playbook_loader import load_shop_playbook
from ecomreview.db.database import DatabaseManager
from ecomreview.schemas import ReplyDraft, ReplyGuardrailReport
from ecomreview.security import EMAIL_RE, LINK_RE, PHONE_RE, wrap_untrusted_review

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PLAYBOOK_PATH = _PROJECT_ROOT / "knowledge" / "playbook_aomua.yaml"
PROMPT_PATH = _PROJECT_ROOT / "prompts" / "reply_v1.md"

MONEY_PROMISE_RE = re.compile(
    r"\b\d+(?:[.,]\d{3})*\s?(?:(?:k|đ|đồng|vnđ|vnd|nghìn|ngàn|triệu|percent)\b|%)",
    re.IGNORECASE,
)

ASPECT_KEYWORDS: dict[str, list[str]] = {
    "WATERPROOF": ["thấm", "nước", "mưa", "đường may", "ướt", "dột", "seam"],
    "MATERIAL_DURABILITY": ["vải", "chất liệu", "bền", "rách", "khóa", "nút", "dày", "mỏng"],
    "FIT_SIZE": ["size", "kích", "cỡ", "rộng", "chật", "dài", "ngắn", "balo"],
    "COMFORT_USABILITY": ["tiện", "gấp", "bí", "mũ", "kính", "thoáng", "vướng"],
    "PRICE_VALUE": ["giá", "tiền", "đắt", "rẻ", "đáng"],
    "PACKAGING_SHIPPING": ["giao", "ship", "đóng gói", "hộp", "túi", "vận chuyển"],
    "CUSTOMER_SERVICE": ["tư vấn", "cskh", "chăm sóc", "hỗ trợ", "tin nhắn", "thái độ"],
    "ACCESSIBILITY_DESIGN": ["màu", "mẫu", "kiểu", "đẹp", "dáng"],
    "GENERAL": ["phản hồi", "góp ý", "ghi nhận", "trải nghiệm", "hỗ trợ"],
}

ASPECT_SHORT_PHRASES: dict[str, str] = {
    "WATERPROOF": "chống thấm nước",
    "MATERIAL_DURABILITY": "chất liệu vải & độ bền",
    "FIT_SIZE": "kích cỡ size",
    "COMFORT_USABILITY": "độ tiện dụng thoáng khí",
    "PRICE_VALUE": "giá cả",
    "PACKAGING_SHIPPING": "đóng gói & giao hàng",
    "CUSTOMER_SERVICE": "chăm sóc hỗ trợ",
    "ACCESSIBILITY_DESIGN": "màu sắc & kiểu dáng",
    "GENERAL": "trải nghiệm chung",
}


def load_playbook(playbook_path: str | Path = DEFAULT_PLAYBOOK_PATH) -> dict[str, Any]:
    """Load playbook YAML configuration."""
    path = Path(playbook_path)
    if path.exists():
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            logger.warning("Failed to load playbook %s: %s", path, e)
    return {}


def check_reply_guardrails(
    reply_text: str,
    negative_aspects: list[str] | None = None,
    playbook_path: str | Path = DEFAULT_PLAYBOOK_PATH,
    extra_overclaim_keywords: list[str] | None = None,
) -> ReplyGuardrailReport:
    """Verify customer service reply against 6 strict safety guardrails.

    G1: No Overclaiming ("chống thấm 100%", etc.)
    G2: Platform Policy Compliance (no review bribery, no off-platform payments/Zalo)
    G3: PII & Link Safety (no phones, emails, or links)
    G4: Length bounds (40 <= chars <= 600)
    G5: Negative aspect coverage (addresses customer concerns)
    G6: No unauthorized monetary promises
    """
    violations: list[str] = []
    text_clean = reply_text.strip()
    text_lower = text_clean.lower()
    playbook = load_playbook(playbook_path)
    guardrails = playbook.get("guardrails", {})

    # G1: No Overclaiming
    overclaim_kws = list(
        guardrails.get(
            "overclaim_keywords",
            [
                "chống thấm 100%",
                "chống nước tuyệt đối",
                "không bao giờ thấm",
                "vĩnh viễn không rách",
                "bảo hành trọn đời",
            ],
        )
    )
    existing_oc = {str(k).lower() for k in overclaim_kws}
    for extra_kw in extra_overclaim_keywords or []:
        kw_s = str(extra_kw).strip()
        if kw_s and kw_s.lower() not in existing_oc:
            overclaim_kws.append(kw_s)
            existing_oc.add(kw_s.lower())
    for kw in overclaim_kws:
        if kw.lower() in text_lower:
            violations.append(f"G1 (Overclaim): Chứa cụm từ cam kết quá mức '{kw}'.")

    # G2: Platform Policy Compliance
    default_prohibited = [
        "tặng tiền đổi 5 sao",
        "hoàn tiền nếu đánh giá 5 sao",
        "xóa đánh giá 1 sao",
        "chuyển khoản ngoài sàn",
        "zalo cá nhân",
    ]
    prohibited_kws = list(default_prohibited)
    existing_prohibited_lower = {k.lower() for k in prohibited_kws}
    for kw in guardrails.get("prohibited_policy_keywords", []):
        kw_s = str(kw)
        if kw_s.lower() not in existing_prohibited_lower:
            prohibited_kws.append(kw_s)
            existing_prohibited_lower.add(kw_s.lower())
    for kw in prohibited_kws:
        if kw.lower() in text_lower:
            violations.append(
                f"G2 (Platform Policy): Chứa điều khoản vi phạm chính sách sàn '{kw}'."
            )

    # G3: PII & External Links
    if PHONE_RE.search(text_clean):
        violations.append("G3 (PII Leak): Chứa số điện thoại cá nhân trong phản hồi.")
    if EMAIL_RE.search(text_clean):
        violations.append("G3 (PII Leak): Chứa địa chỉ email trong phản hồi.")
    if LINK_RE.search(text_clean):
        violations.append("G3 (External Link): Chứa đường dẫn liên kết ngoài sàn.")

    # G4: Length bounds
    if len(text_clean) < 40 or len(text_clean) > 600:
        violations.append(
            f"G4 (Length): Độ dài phản hồi ({len(text_clean)} ký tự) "
            "nằm ngoài khoảng cho phép 40-600 ký tự."
        )

    # G5: Negative Aspect Coverage
    if negative_aspects:
        unaddressed = []
        for asp in negative_aspects:
            kws = ASPECT_KEYWORDS.get(asp, [asp.lower()])
            if not any(k in text_lower for k in kws):
                unaddressed.append(asp)
        if unaddressed:
            violations.append(
                f"G5 (Aspect Coverage): Phản hồi chưa đề cập trực diện đến các vấn đề "
                f"khách hàng phàn nàn: {', '.join(unaddressed)}."
            )

    # G6: No specific monetary promises
    if MONEY_PROMISE_RE.search(text_clean):
        violations.append(
            "G6 (Unauthorized Money Promise): Tự ý hứa hẹn bồi thường tiền tệ cụ thể."
        )

    return ReplyGuardrailReport(passed=len(violations) == 0, violations=violations)


def build_template_reply(
    negative_aspects: list[str],
    review_id: str = "",
    playbook_path: str | Path = DEFAULT_PLAYBOOK_PATH,
    brand_voice: dict[str, Any] | None = None,
) -> str:
    """Deterministically assemble an empathetic, policy-compliant reply from playbook templates."""
    playbook = load_playbook(playbook_path)
    templates = playbook.get("reply_templates", {})
    greeting = templates.get(
        "greeting",
        "Dạ Shop Áo Mưa xin chân thành cảm ơn Quý khách đã gửi phản hồi cho đơn hàng.",
    )
    bv = dict(brand_voice or {})
    sig = str(bv.get("shop_signature") or "").strip()
    if sig and not any(rx.search(sig) for rx in (PHONE_RE, EMAIL_RE, LINK_RE)):
        greeting = f"Dạ {sig} xin chân thành cảm ơn Quý khách đã tin tưởng ủng hộ sản phẩm."
    closing = templates.get(
        "closing",
        "Shop chúc Quý khách luôn có những chuyến đi bình an và an tâm trong mùa mưa này ạ!",
    )
    return_policy = str(bv.get("return_policy") or "").strip()
    if (
        return_policy
        and len(return_policy) <= 140
        and not any(
            rx.search(return_policy) for rx in (PHONE_RE, EMAIL_RE, LINK_RE, MONEY_PROMISE_RE)
        )
    ):
        closing = f"{return_policy.rstrip('.')}. {closing}".strip()
    handlers = templates.get("aspect_handlers", {})

    body_sentences: list[str] = []
    chosen_aspects: list[str] = []
    skipped_aspects: list[str] = []
    if negative_aspects:
        for asp in negative_aspects:
            if asp in handlers and handlers[asp] not in body_sentences:
                joined_body = " ".join(body_sentences + [handlers[asp]])
                cand_text = f"{greeting} {joined_body} {closing}".strip()
                if len(cand_text) <= 580:
                    body_sentences.append(handlers[asp])
                    chosen_aspects.append(asp)
                else:
                    skipped_aspects.append(asp)

    if skipped_aspects:
        while True:
            phrases = [ASPECT_SHORT_PHRASES.get(a, a.lower()) for a in skipped_aspects]
            extra_note = f"Shop cũng ghi nhận góp ý về {', '.join(phrases)} để cải thiện ngay ạ."
            cand_with_extra = (
                f"{greeting} {' '.join(body_sentences)} {extra_note} {closing}".strip()
            )
            if len(cand_with_extra) <= 600:
                body_sentences.append(extra_note)
                break
            if not body_sentences:
                max_note_len = max(40, 590 - len(greeting) - len(closing))
                if len(extra_note) > max_note_len:
                    extra_note = extra_note[: max_note_len - 3].rstrip() + "..."
                body_sentences.append(extra_note)
                break
            body_sentences.pop()
            skipped_aspects.insert(0, chosen_aspects.pop())

    if not body_sentences:
        body_sentences.append(
            handlers.get(
                "GENERAL",
                "Shop đã ghi nhận phản hồi và luôn sẵn sàng hỗ trợ Quý khách "
                "qua cổng Chat chính thức của sàn trong vòng 24h.",
            )
        )

    res_text = f"{greeting} {' '.join(body_sentences)} {closing}".strip()
    if len(res_text) > 600:
        res_text = res_text[:595].rstrip() + "..."
    return res_text


def generate_customer_reply(
    review_id: str,
    scenario_tag: str = "real_shop",
    mode: str = "template",
    db: DatabaseManager | None = None,
    playbook_path: str | Path = DEFAULT_PLAYBOOK_PATH,
    llm_client: Any | None = None,
) -> dict[str, Any]:
    """Generate and verify customer service reply draft for a given review."""
    db_mgr = db or DatabaseManager()
    with db_mgr.get_connection(read_only=True) as conn:
        r_row = conn.execute(
            "SELECT * FROM reviews WHERE review_id = ? AND scenario_tag = ?",
            (review_id, scenario_tag),
        ).fetchone()
        if not r_row:
            return {"status": "error", "message": f"Review {review_id} not found."}

        op_rows = conn.execute(
            "SELECT aspect, polarity FROM opinions WHERE review_id = ? AND scenario_tag = ?",
            (review_id, scenario_tag),
        ).fetchall()

    neg_aspects = [str(o["aspect"]) for o in op_rows if str(o["polarity"]).lower() == "negative"]
    raw_text = str(r_row["text_raw"])
    rating = int(r_row["rating"] or 5)
    platform = str(r_row["platform"])

    actual_mode = mode
    reply_text = ""
    addressed: list[str] = list(neg_aspects)

    eff_playbook_path: Path = Path(playbook_path)
    brand_voice: dict[str, Any] = {}
    extra_overclaim: list[str] = []
    if eff_playbook_path == DEFAULT_PLAYBOOK_PATH:
        loaded_pb = load_shop_playbook(db=db_mgr, scenario_tag=scenario_tag)
        if loaded_pb.get("_resolved_path"):
            eff_playbook_path = Path(loaded_pb["_resolved_path"])
        shop_prof = loaded_pb.get("shop_profile") or {}
        brand_voice = dict(shop_prof.get("brand_voice") or {})
        extra_overclaim = list(brand_voice.get("custom_overclaim_keywords") or [])

    if mode == "llm":
        try:
            from ecomreview.llm_provider import get_default_llm_client

            client = llm_client or get_default_llm_client()
            system_prompt = (
                PROMPT_PATH.read_text(encoding="utf-8")
                if PROMPT_PATH.exists()
                else "Bạn là trợ lý CSKH gian hàng TMĐT."
            )
            bv_lines = []
            if brand_voice.get("shop_signature"):
                bv_lines.append(f"- Xưng hô / Tên shop: {brand_voice['shop_signature']}")
            if brand_voice.get("tone"):
                bv_lines.append(f"- Giọng văn: {brand_voice['tone']}")
            if brand_voice.get("return_policy"):
                bv_lines.append(f"- Chính sách đổi trả: {brand_voice['return_policy']}")
            if brand_voice.get("cskh_notes"):
                bv_lines.append(f"- Lưu ý CSKH riêng: {brand_voice['cskh_notes']}")
            bv_block = ("\nHồ sơ Brand Voice:\n" + "\n".join(bv_lines)) if bv_lines else ""

            asp_str = ", ".join(neg_aspects) if neg_aspects else "Không có (đánh giá chung)"
            user_prompt = (
                f"Đánh giá của khách ({platform.upper()}, {rating} sao):\n"
                f"{wrap_untrusted_review(raw_text)}\n\n"
                f"Các khía cạnh bị chê: {asp_str}.{bv_block}\n"
                f"Hãy tạo bản nháp phản hồi CSKH chuẩn mực thỏa mãn các quy tắc G1-G6."
            )
            draft: ReplyDraft = client.generate_structured(
                prompt=user_prompt,
                schema_cls=ReplyDraft,
                system_instruction=system_prompt,
                raw_review_for_fallback=raw_text,
            )
            reply_text = draft.reply_text.strip()
            addressed = [
                a.value if hasattr(a, "value") else str(a) for a in draft.addressed_aspects
            ]
            report = check_reply_guardrails(
                reply_text,
                neg_aspects,
                playbook_path=eff_playbook_path,
                extra_overclaim_keywords=extra_overclaim,
            )

            if not report.passed:
                logger.warning(
                    "LLM reply violated guardrails %s. Retrying once...", report.violations
                )
                user_prompt += f"\n\nLưu ý sửa các lỗi sau: {'; '.join(report.violations)}"
                retry_draft: ReplyDraft = client.generate_structured(
                    prompt=user_prompt,
                    schema_cls=ReplyDraft,
                    system_instruction=system_prompt,
                    raw_review_for_fallback=raw_text,
                )
                retry_report = check_reply_guardrails(
                    retry_draft.reply_text,
                    neg_aspects,
                    playbook_path=eff_playbook_path,
                    extra_overclaim_keywords=extra_overclaim,
                )
                if retry_report.passed:
                    reply_text = retry_draft.reply_text.strip()
                    report = retry_report
                    addressed = [
                        a.value if hasattr(a, "value") else str(a)
                        for a in retry_draft.addressed_aspects
                    ]
                else:
                    logger.warning("Retry still violated guardrails. Falling back to template.")
                    reply_text = build_template_reply(
                        neg_aspects, review_id, eff_playbook_path, brand_voice=brand_voice
                    )
                    actual_mode = "llm+template_fallback"
                    addressed = list(neg_aspects)
                    report = check_reply_guardrails(
                        reply_text,
                        neg_aspects,
                        playbook_path=eff_playbook_path,
                        extra_overclaim_keywords=extra_overclaim,
                    )
        except Exception as e:
            logger.warning("LLM reply generation failed: %s. Using template fallback.", e)
            reply_text = build_template_reply(
                neg_aspects, review_id, eff_playbook_path, brand_voice=brand_voice
            )
            actual_mode = "template_fallback"
            addressed = list(neg_aspects)
            report = check_reply_guardrails(
                reply_text,
                neg_aspects,
                playbook_path=eff_playbook_path,
                extra_overclaim_keywords=extra_overclaim,
            )
    else:
        reply_text = build_template_reply(
            neg_aspects, review_id, eff_playbook_path, brand_voice=brand_voice
        )
        report = check_reply_guardrails(
            reply_text,
            neg_aspects,
            playbook_path=eff_playbook_path,
            extra_overclaim_keywords=extra_overclaim,
        )

    return {
        "review_id": review_id,
        "scenario_tag": scenario_tag,
        "platform": platform,
        "rating": rating,
        "negative_aspects": neg_aspects,
        "reply_text": reply_text,
        "addressed_aspects": addressed,
        "mode_used": actual_mode,
        "guardrail_report": report.model_dump(),
    }


FIVE_STAR_TEMPLATES: tuple[str, ...] = (
    (
        "Dạ Shop xin chân thành cảm ơn Quý khách đã tin tưởng ủng hộ và dành đánh giá 5 sao "
        "tuyệt vời cho sản phẩm ạ. Chúc Quý khách luôn có trải nghiệm sử dụng thật hài lòng!"
    ),
    (
        "Shop cảm ơn Quý khách rất nhiều vì phản hồi tích cực và sự đồng hành cùng gian hàng. "
        "Rất mong tiếp tục được phục vụ Quý khách trong những đơn hàng tiếp theo ạ!"
    ),
    (
        "Dạ lời khen 5 sao của Quý khách là động lực rất lớn để đội ngũ Shop nâng cao chất lượng "
        "mỗi ngày. Cần hỗ trợ thêm thông tin, Quý khách cứ nhắn qua chat sàn nhé ạ!"
    ),
    (
        "Shop xin cảm ơn Quý khách đã hài lòng với sản phẩm và dịch vụ giao nhận của đơn hàng. "
        "Chúc Quý khách thật nhiều sức khỏe và luôn an tâm khi mua sắm tại gian hàng ạ!"
    ),
)


def build_five_star_reply(review_id: str, product: str = "") -> str:
    """Select a natural, G1-G6 compliant thank-you template deterministically per review_id."""
    idx = sum(ord(ch) for ch in (review_id or "0")) % len(FIVE_STAR_TEMPLATES)
    return FIVE_STAR_TEMPLATES[idx]


def auto_reply_eligible_five_star_reviews(
    db: DatabaseManager,
    scenario_tag: str,
    review_ids: list[str] | None = None,
    limit: int = 50,
    actor: str = "auto_reply_5star",
    playbook_path: str | Path = DEFAULT_PLAYBOOK_PATH,
) -> dict[str, Any]:
    """Auto-reply only clean 5-star reviews (no negative opinions/anomalies) passing G1-G6."""
    safe_limit = max(1, min(100, int(limit)))
    with db.get_connection(read_only=True) as conn:
        if review_ids:
            clean_ids = [str(r).strip() for r in review_ids if str(r).strip()][:safe_limit]
            if not clean_ids:
                return {
                    "scenario_tag": scenario_tag,
                    "replied_count": 0,
                    "skipped_count": 0,
                    "created_reply_ids": [],
                    "drafted_ids": [],
                }
            ph = ", ".join("?" for _ in clean_ids)
            rows = conn.execute(
                f"SELECT review_id, product, rating, anomaly_flags "
                f"FROM reviews WHERE scenario_tag = ? AND rating = 5 AND review_id IN ({ph})",
                (scenario_tag, *clean_ids),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT review_id, product, rating, anomaly_flags "
                "FROM reviews WHERE scenario_tag = ? AND rating = 5 "
                "ORDER BY imported_at DESC LIMIT ?",
                (scenario_tag, safe_limit * 2),
            ).fetchall()

        if not rows:
            return {
                "scenario_tag": scenario_tag,
                "replied_count": 0,
                "skipped_count": 0,
                "created_reply_ids": [],
                "drafted_ids": [],
            }

        cand_ids = [str(r["review_id"]) for r in rows]
        ph = ", ".join("?" for _ in cand_ids)
        neg_rows = conn.execute(
            f"SELECT DISTINCT review_id FROM opinions "
            f"WHERE scenario_tag = ? AND polarity = 'negative' AND review_id IN ({ph})",
            (scenario_tag, *cand_ids),
        ).fetchall()
        neg_rids = {str(nr["review_id"]) for nr in neg_rows}

        replied_rows = conn.execute(
            f"SELECT DISTINCT review_id FROM review_replies "
            f"WHERE scenario_tag = ? AND status IN ('APPROVED', 'SENT') "
            f"AND review_id IN ({ph})",
            (scenario_tag, *cand_ids),
        ).fetchall()
        already_replied = {str(rr["review_id"]) for rr in replied_rows}

    import json as _json

    created_reply_ids: list[int] = []
    drafted_ids: list[int] = []
    skipped = 0

    eff_playbook_path = Path(playbook_path)
    extra_overclaim: list[str] = []
    if eff_playbook_path == DEFAULT_PLAYBOOK_PATH:
        loaded_pb = load_shop_playbook(db=db, scenario_tag=scenario_tag)
        if loaded_pb.get("_resolved_path"):
            eff_playbook_path = Path(loaded_pb["_resolved_path"])
        extra_overclaim = list(
            ((loaded_pb.get("shop_profile") or {}).get("brand_voice") or {}).get(
                "custom_overclaim_keywords"
            )
            or []
        )

    for row in rows:
        if len(created_reply_ids) >= safe_limit:
            break
        rid = str(row["review_id"])
        raw_flags = row["anomaly_flags"] if "anomaly_flags" in row.keys() else "[]"
        try:
            flags = (
                _json.loads(raw_flags or "[]") if isinstance(raw_flags, str) else list(raw_flags)
            )
        except Exception:
            flags = []

        if (
            rid in neg_rids
            or rid in already_replied
            or "HIDDEN_COMPLAINT" in flags
            or "SPAM_REPEATED_CHARS" in flags
        ):
            skipped += 1
            continue

        reply_text = build_five_star_reply(rid, product=str(row["product"] or ""))
        report = check_reply_guardrails(
            reply_text=reply_text,
            negative_aspects=[],
            playbook_path=eff_playbook_path,
            extra_overclaim_keywords=extra_overclaim,
        )
        target_status = "SENT" if report.passed else "DRAFT"
        new_id = db.insert_review_reply(
            review_id=rid,
            scenario_tag=scenario_tag,
            reply_text=reply_text,
            mode_used="auto_5star",
            guardrail_passed=report.passed,
            violations=report.violations,
            status=target_status,
            created_by=actor,
        )
        if report.passed:
            created_reply_ids.append(new_id)
        else:
            drafted_ids.append(new_id)

    return {
        "scenario_tag": scenario_tag,
        "replied_count": len(created_reply_ids),
        "skipped_count": skipped,
        "created_reply_ids": created_reply_ids,
        "drafted_ids": drafted_ids,
    }


# CreBy: MenBoyBMN
