"""Customer Care Reply Assistant with Deterministic Guardrails (G1 - G6)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

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
    overclaim_kws = guardrails.get(
        "overclaim_keywords",
        [
            "chống thấm 100%",
            "chống nước tuyệt đối",
            "không bao giờ thấm",
            "vĩnh viễn không rách",
            "bảo hành trọn đời",
        ],
    )
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
) -> str:
    """Deterministically assemble an empathetic, policy-compliant reply from playbook templates."""
    playbook = load_playbook(playbook_path)
    templates = playbook.get("reply_templates", {})
    greeting = templates.get(
        "greeting",
        "Dạ Shop Áo Mưa xin chân thành cảm ơn Quý khách đã gửi phản hồi cho đơn hàng.",
    )
    closing = templates.get(
        "closing",
        "Shop chúc Quý khách luôn có những chuyến đi bình an và an tâm trong mùa mưa này ạ!",
    )
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

    if mode == "llm":
        try:
            from ecomreview.llm_provider import get_default_llm_client

            client = llm_client or get_default_llm_client()
            system_prompt = (
                PROMPT_PATH.read_text(encoding="utf-8")
                if PROMPT_PATH.exists()
                else "Bạn là trợ lý CSKH áo mưa."
            )
            asp_str = ", ".join(neg_aspects) if neg_aspects else "Không có (đánh giá chung)"
            user_prompt = (
                f"Đánh giá của khách ({platform.upper()}, {rating} sao):\n"
                f"{wrap_untrusted_review(raw_text)}\n\n"
                f"Các khía cạnh bị chê: {asp_str}.\n"
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
            report = check_reply_guardrails(reply_text, neg_aspects, playbook_path=playbook_path)

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
                    retry_draft.reply_text, neg_aspects, playbook_path=playbook_path
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
                    reply_text = build_template_reply(neg_aspects, review_id, playbook_path)
                    actual_mode = "llm+template_fallback"
                    addressed = list(neg_aspects)
                    report = check_reply_guardrails(reply_text, neg_aspects, playbook_path)
        except Exception as e:
            logger.warning("LLM reply generation failed: %s. Using template fallback.", e)
            reply_text = build_template_reply(neg_aspects, review_id, playbook_path)
            actual_mode = "template_fallback"
            addressed = list(neg_aspects)
            report = check_reply_guardrails(reply_text, neg_aspects, playbook_path)
    else:
        reply_text = build_template_reply(neg_aspects, review_id, playbook_path)
        report = check_reply_guardrails(reply_text, neg_aspects, playbook_path)

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


# CreBy: MenBoyBMN
