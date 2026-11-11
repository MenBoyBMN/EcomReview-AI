"""Vietnamese Social Text Normalization for E-commerce Reviews."""

import re
import unicodedata

# Comprehensive Teencode and abbreviation dictionary on Shopee & TikTok Shop
TEENCODE_MAP: dict[str, str] = {
    "ko": "không",
    "k": "không",
    "kh": "không",
    "khg": "không",
    "hok": "không",
    "hong": "không",
    "hông": "không",
    "kô": "không",
    "dc": "được",
    "đc": "được",
    "dk": "được",
    "đk": "được",
    "sp": "sản phẩm",
    "mn": "mọi người",
    "mng": "mọi người",
    "shop": "shop",
    "sh": "shop",
    "sop": "shop",
    "nv": "nhân viên",
    "cskh": "chăm sóc khách hàng",
    "vs": "với",
    "iu": "yêu",
    "ưng": "ưng ý",
    "okla": "ok",
    "oke": "ok",
    "okie": "ok",
    "cx": "cũng",
    "z": "vậy",
    "v": "vậy",
    "j": "gì",
    "nc": "nước",
    "đg": "đóng gói",
    "sz": "size",
    "mik": "mình",
    "mk": "mình",
    "bh": "bao giờ",
    "tl": "trả lời",
    "rep": "trả lời",
    "ib": "nhắn tin",
    "nt": "nhắn tin",
    "chất": "chất lượng",
    "chat": "chất lượng",
    "đẹp": "đẹp",
    "chê": "chê",
    "qúa": "quá",
    "wa": "quá",
}

EMOJI_SENTIMENT_MAP: dict[str, str] = {
    "😍": " [EMO_POS] ",
    "🥰": " [EMO_POS] ",
    "❤️": " [EMO_POS] ",
    "👍": " [EMO_POS] ",
    "💯": " [EMO_POS] ",
    "🌟": " [EMO_POS] ",
    "✨": " [EMO_POS] ",
    "😊": " [EMO_POS] ",
    "😁": " [EMO_POS] ",
    "😡": " [EMO_NEG] ",
    "🤬": " [EMO_NEG] ",
    "👎": " [EMO_NEG] ",
    "😢": " [EMO_NEG] ",
    "😭": " [EMO_NEG] ",
    "💔": " [EMO_NEG] ",
    "🤮": " [EMO_NEG] ",
    "😤": " [EMO_NEG] ",
}

PRICE_K_RE = re.compile(r"\b(\d+)\s*k\b", re.IGNORECASE)
WEIGHT_KG_RE = re.compile(r"\b(\d+)\s*kg\b", re.IGNORECASE)
HEIGHT_M_RE = re.compile(r"\b1m(\d{1,2})\b", re.IGNORECASE)

# Vietnamese diacritics character set
VN_DIACRITICS_PATTERN = re.compile(
    r"[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]",
    re.IGNORECASE,
)


def normalize_social_text(text: str | None, enable: bool = True) -> str:
    """Normalize Vietnamese e-commerce social text.

    If enable=False, only perform NFC Unicode normalization, HTML stripping, and whitespace cleanup.
    If enable=True, expand teencode, normalize elongated characters, and map sentiment emojis.
    """
    if not text:
        return ""

    # Normalize Unicode NFC
    t = unicodedata.normalize("NFC", text)
    # Remove HTML tags if present
    t = re.sub(r"<[^>]+>", " ", t)

    if not enable:
        return re.sub(r"\s+", " ", t).strip()

    t = t.lower()

    # 1. Protect currency shorthand '150k' -> '150 nghìn' before 'k' -> 'không' mapping
    t = PRICE_K_RE.sub(r"\1 nghìn", t)

    # 2. Compress elongated letters (>= 3 repeats, e.g. "mỏnggggg" -> "mỏng")
    t = re.sub(
        r"([a-zàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ])\1{2,}",
        r"\1",
        t,
    )
    # Compress repeated punctuation (e.g. "!!!!!" -> "!", "?????" -> "?")
    t = re.sub(r"([!?.,])\1+", r"\1", t)

    # 3. Replace teencode word by word while preserving boundary punctuation
    # Context-aware guard against over-normalizing compound nouns ("chất liệu", "chất vải", etc.)
    compound_followers = {
        "liệu",
        "lieu",
        "lượng",
        "luong",
        "vải",
        "vai",
        "dù",
        "du",
        "nhựa",
        "nhua",
        "lỏng",
        "độc",
        "xám",
        "với",
        "vs",
        "shop",
        "sh",
        "sop",
    }
    raw_words = t.split()
    tokens: list[str] = []
    for idx, word in enumerate(raw_words):
        clean_w = word.strip(".,!?;:()[]\"'")
        if not clean_w:
            tokens.append(word)
            continue
        punct_prefix = word[: len(word) - len(word.lstrip(".,!?;:()[]\"'"))]
        punct_suffix = word[len(word.rstrip(".,!?;:()[]\"'")) :]
        next_clean = raw_words[idx + 1].strip(".,!?;:()[]\"'") if idx + 1 < len(raw_words) else ""
        if clean_w in {"chất", "chat"} and next_clean in compound_followers:
            mapped = "chất" if clean_w == "chất" else clean_w
        else:
            mapped = TEENCODE_MAP.get(clean_w, clean_w)
        tokens.append(f"{punct_prefix}{mapped}{punct_suffix}")
    t = " ".join(tokens)

    # 4. Map emojis to sentiment tokens
    for emo, token in EMOJI_SENTIMENT_MAP.items():
        t = t.replace(emo, token)

    return re.sub(r"\s+", " ", t).strip()


def extract_noise_flags(text: str | None) -> dict[str, bool]:
    """Extract noise flags from review text for RQ2 ablation and diagnostic profiling."""
    if not text:
        return {
            "has_teencode": False,
            "has_emoji": False,
            "is_no_diacritics": False,
            "is_short": True,
        }

    raw = text.lower()
    words = [w.strip(".,!?;:()[]\"'") for w in raw.split()]
    words = [w for w in words if w]

    has_teencode = any(w in TEENCODE_MAP for w in words)
    has_emoji = any(e in raw for e in EMOJI_SENTIMENT_MAP)
    has_vn_diacritics = bool(VN_DIACRITICS_PATTERN.search(raw))
    # No diacritics condition: review has >= 3 words and no Vietnamese accented characters
    is_no_diacritics = (not has_vn_diacritics) and (len(words) >= 3)
    is_short = len(words) <= 3

    return {
        "has_teencode": has_teencode,
        "has_emoji": has_emoji,
        "is_no_diacritics": is_no_diacritics,
        "is_short": is_short,
    }


# CreBy: MenBoyBMN
