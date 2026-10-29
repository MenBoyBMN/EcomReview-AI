"""Security module providing defense-in-depth against prompt injection and PII leaks."""

import re

# Regex patterns for Vietnamese phone numbers and emails
PHONE_RE = re.compile(r"(?:\+84|0)[35789]\d{8}\b")
EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def scrub_pii(text: str) -> str:
    """Anonymize personally identifiable information (PII) such as phone numbers and emails.

    Args:
        text: Raw text potentially containing PII.

    Returns:
        Cleaned text with phone numbers replaced by [PHONE] and emails by [EMAIL].
    """
    if not text:
        return ""
    cleaned = PHONE_RE.sub("[PHONE]", text)
    return EMAIL_RE.sub("[EMAIL]", cleaned)


def sanitize_for_llm(text: str, max_chars: int = 1500) -> str:
    """Sanitize untrusted text before injecting into LLM prompt templates.

    - Strips non-printable control characters
    - Truncates to maximum character length
    - Escapes XML/HTML delimiters to prevent prompt jailbreak
    - Scrubs PII

    Args:
        text: Raw user review text.
        max_chars: Upper character limit to prevent context-stuffing denial of service.

    Returns:
        Sanitized and safe string.
    """
    if not text:
        return ""
    cleaned = CONTROL_CHARS_RE.sub("", text)[:max_chars]
    # Escape XML delimiters to prevent breakout from <customer_review> tags
    cleaned = cleaned.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return scrub_pii(cleaned).strip()


def wrap_untrusted_review(text: str) -> str:
    """Wrap untrusted customer review text inside explicit XML isolation boundary.

    Args:
        text: Raw customer review.

    Returns:
        Isolated XML block.
    """
    sanitized = sanitize_for_llm(text)
    return f"<customer_review>\n{sanitized}\n</customer_review>"


# CreBy: MenBoyBMN
