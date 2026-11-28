"""Security module providing defense-in-depth against prompt injection, PII leaks, and SSRF."""

import ipaddress
import os
import re
import socket
from urllib.parse import urlparse

_BLOCKED_WEBHOOK_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata",
    "db",
    "redis",
    "api",
    "worker",
    "frontend",
}
_BLOCKED_HOST_SUFFIXES = (".local", ".internal", ".localhost")

# Regex patterns for Vietnamese phone numbers, emails, and external links
PHONE_RE = re.compile(r"(?<!\d)(?:\+?84\s?0?|0)[\s.\-]?[35789](?:[\s.\-]?\d){8}(?!\d)")
EMAIL_RE = re.compile(r"[\w.\-+]+@[\w.\-]+\.\w+")
LINK_RE = re.compile(
    r"(?:https?://|www\.)[^\s<>\"']+"
    r"|\b(?:zalo\.me|fb\.com|facebook\.com|m\.me|shopee\.vn|s\.shopee\.vn|"
    r"tiktok\.com|vt\.tiktok\.com|lazada\.vn|t\.me|bit\.ly|t\.ly|tinyurl\.com|goo\.gl)/[^\s<>\"']+",
    re.IGNORECASE,
)
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def scrub_pii(text: str) -> str:
    """Anonymize personally identifiable information (PII) such as phone numbers, emails, and links.

    Args:
        text: Raw text potentially containing PII.

    Returns:
        Cleaned text with phone numbers replaced by [PHONE], emails by [EMAIL], links by [LINK].
    """
    if not text:
        return ""
    cleaned = PHONE_RE.sub("[PHONE]", text)
    cleaned = EMAIL_RE.sub("[EMAIL]", cleaned)
    return LINK_RE.sub("[LINK]", cleaned)


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
    cleaned = CONTROL_CHARS_RE.sub("", text)
    cleaned = scrub_pii(cleaned)
    # Escape XML delimiters to prevent breakout from <customer_review> tags, then enforce max_chars
    cleaned = cleaned.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    cleaned = cleaned[:max_chars]
    return cleaned.strip()


def wrap_untrusted_review(text: str) -> str:
    """Wrap untrusted customer review text inside explicit XML isolation boundary.

    Args:
        text: Raw customer review.

    Returns:
        Isolated XML block.
    """
    sanitized = sanitize_for_llm(text)
    return f"<customer_review>\n{sanitized}\n</customer_review>"


def _is_disallowed_ip(ip_str: str) -> bool:
    """Return True if an IP literal belongs to private, loopback, link-local, or reserved ranges."""
    addr = ipaddress.ip_address(ip_str.split("%", 1)[0])
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def validate_webhook_url(url: str, *, allow_http: bool | None = None) -> str:
    """Validate an outbound webhook URL against SSRF (blocks internal hosts and private IPs)."""
    clean_url = (url or "").strip()
    if not clean_url:
        raise ValueError("Webhook URL không được để trống.")

    parsed = urlparse(clean_url)
    allow_http_effective = (
        allow_http
        if allow_http is not None
        else os.getenv("ECOMREVIEW_ALLOW_INSECURE_WEBHOOK", "false").strip().lower() == "true"
    )
    scheme = (parsed.scheme or "").lower()
    if scheme != "https" and not (allow_http_effective and scheme == "http"):
        raise ValueError("Webhook URL bắt buộc sử dụng giao thức HTTPS.")

    if parsed.username or parsed.password:
        raise ValueError("Webhook URL không được chứa thông tin đăng nhập.")

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if (
        not hostname
        or hostname in _BLOCKED_WEBHOOK_HOSTS
        or hostname.endswith(_BLOCKED_HOST_SUFFIXES)
        or "." not in hostname
    ):
        raise ValueError("Webhook URL không được trỏ tới máy chủ nội bộ.")

    try:
        _ip = ipaddress.ip_address(hostname)
    except ValueError:
        _ip = None

    if _ip is not None:
        if _is_disallowed_ip(str(_ip)):
            raise ValueError(
                "Webhook URL không được trỏ tới địa chỉ IP nội bộ/private (SSRF blocked)."
            )
        return clean_url

    try:
        infos = socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        if os.getenv("ECOMREVIEW_ENV", "development").strip().lower() == "production":
            raise ValueError("Không thể phân giải tên miền Webhook URL.") from exc
        return clean_url

    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        resolved_ip = str(sockaddr[0])
        if _is_disallowed_ip(resolved_ip):
            raise ValueError("Webhook URL phân giải tới địa chỉ mạng nội bộ (SSRF blocked).")

    return clean_url


# CreBy: MenBoyBMN
