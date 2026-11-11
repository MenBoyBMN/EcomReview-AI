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

DEFAULT_PLAYBOOK_PATH = Path("knowledge/playbook_aomua.yaml")
PROMPT_PATH = Path("prompts/reply_v1.md")

MONEY_PROMISE_RE = re.compile(r"\b\d+\s?(?:k|đ|vnđ|nghìn|triệu|percent|%)\b", re.IGNORECASE)

ASPECT_KEYWORDS: dict[str, list[str]] = {
    "WATERPROOF": ["thấm", "nước", "mưa", "đường may", "ướt", "dột", "seam"],
    "MATERIAL_DURABILITY": ["vải", "chất liệu", "bền", "rách", "khóa", "nút", "dày", "mỏng"],
    "FIT_SIZE": ["size", "kích", "cỡ", "rộng", "chật", "dài", "ngắn", "balo"],
    "COMFORT_USABILITY": ["tiện", "gấp", "bí", "mũ", "kính", "thoáng", "vướng"],
    "PRICE_VALUE": ["giá", "tiền", "đắt", "rẻ", "đáng"],
    "PACKAGING_SHIPPING": ["giao", "ship", "đóng gói", "hộp", "túi", "vận chuyển"],
    "CUSTOMER_SERVICE": ["tư vấn", "cskh", "chăm sóc", "hỗ trợ", "tin nhắn", "thái độ"],
    "ACCESSIBILITY_DESIGN": ["màu", "mẫu", "kiểu", "đẹp", "dáng"],
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
    prohibited_kws = guardrails.get(
        "prohibited_policy_keywords",
        [
            "tặng tiền đổi 5 sao",
            "hoàn tiền nếu đánh giá 5 sao",
            "xóa đánh giá 1 sao",
            "chuyển khoản ngoài sàn",
            "zalo cá nhân",
        ],
    )
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
        if len(unaddressed) == len(negative_aspects) and negative_aspects:
            violations.append(
                f"G5 (Aspect Coverage): Phản hồi chưa đề cập trực diện đến vấn đề "
                f"khách hàng phàn nàn: {', '.join(negative_aspects)}."
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
    if negative_aspects:
        for asp in negative_aspects:
            if asp in handlers and handlers[asp] not in body_sentences:
                body_sentences.append(handlers[asp])

    if not body_sentences:
        body_sentences.append(
            handlers.get(
                "GENERAL",
                "Shop đã ghi nhận phản hồi và luôn sẵn sàng hỗ trợ Quý khách "
                "qua cổng Chat chính thức của sàn trong vòng 24h.",
            )
        )

    body_text = " ".join(body_sentences)
    return f"{greeting} {body_text} {closing}".strip()


def generate_customer_reply(
    review_id: str,
    scenario_tag: str = "real_shop",
    mode: str = "template",
    db: DatabaseManager | None = None,
    playbook_path: str | Path = DEFAULT_PLAYBOOK_PATH,
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
            from ecomreview.llm_provider import UnifiedLLMClient

            llm_client = UnifiedLLMClient()
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
            draft: ReplyDraft = llm_client.generate_structured(
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
                retry_draft: ReplyDraft = llm_client.generate_structured(
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
                else:
                    logger.warning("Retry still violated guardrails. Falling back to template.")
                    reply_text = build_template_reply(neg_aspects, review_id, playbook_path)
                    actual_mode = "llm+template_fallback"
                    report = check_reply_guardrails(reply_text, neg_aspects, playbook_path)
        except Exception as e:
            logger.warning("LLM reply generation failed: %s. Using template fallback.", e)
            reply_text = build_template_reply(neg_aspects, review_id, playbook_path)
            actual_mode = "template_fallback"
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
