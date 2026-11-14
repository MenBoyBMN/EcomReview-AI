"""Baseline 1 (B1): Rule and Lexicon-based ABSA Analyzer.

Zero ML, zero training cost, instant deterministic inference.
Employs domain-specific keyword matching, context sliding windows (+-5 words),
and negation handling for Vietnamese e-commerce customer feedback.
"""

import re

from ecomreview.normalize import normalize_social_text
from ecomreview.schemas import Aspect, AspectOpinion, Polarity, ReviewAnalysis

# Domain aspect keyword lexicon (with and without diacritics)
ASPECT_LEXICON: dict[Aspect, list[str]] = {
    Aspect.WATERPROOF: [
        "chống thấm",
        "chống nước",
        "kín nước",
        "ngấm nước",
        "thấm nước",
        "thoát nước",
        "vô nước",
        "vào nước",
        "thấm",
        "dột",
        "ướt",
        "ngấm",
        "chong tham",
        "chong nuoc",
        "kin nuoc",
        "ngam nuoc",
        "tham nuoc",
        "vo nuoc",
        "vao nuoc",
        "tham",
        "dot",
        "uot",
        "ngam",
    ],
    Aspect.MATERIAL_DURABILITY: [
        "chất liệu",
        "chất vải",
        "vải dù",
        "đường may",
        "khóa kéo",
        "dây kéo",
        "nút bấm",
        "cúc bấm",
        "bền",
        "rách",
        "dày",
        "mỏng",
        "nhựa",
        "mùi nhựa",
        "mùi hôi",
        "chắc chắn",
        "chat lieu",
        "chat vai",
        "vai du",
        "duong may",
        "khoa keo",
        "day keo",
        "nut bam",
        "cuc bam",
        "ben",
        "rach",
        "day",
        "mong",
        "nhua",
        "mui nhua",
        "mui hoi",
        "chac chan",
    ],
    Aspect.FIT_SIZE: [
        "kích thước",
        "kích cỡ",
        "chiều dài",
        "chiều rộng",
        "form",
        "size",
        "rộng",
        "chật",
        "ngắn",
        "dài",
        "vừa vặn",
        "vừa",
        "trùm",
        "kich thuoc",
        "kich co",
        "chieu dai",
        "chieu rong",
        "rong",
        "chat",
        "ngan",
        "dai",
        "vua van",
        "vua",
        "trum",
    ],
    Aspect.COMFORT_USABILITY: [
        "thoáng khí",
        "gấp gọn",
        "bỏ cốp",
        "kính chắn",
        "tay bao",
        "mũ trùm",
        "thoải mái",
        "tiện lợi",
        "tiện dụng",
        "nóng",
        "bí bách",
        "bí",
        "nặng",
        "nhẹ",
        "thoang khi",
        "gap gon",
        "bo cop",
        "kinh chan",
        "tay bao",
        "mu trum",
        "thoai mai",
        "tien loi",
        "tien dung",
        "nong",
        "bi bach",
        "bi",
        "nang",
        "nhe",
    ],
    Aspect.PRICE_VALUE: [
        "đáng tiền",
        "hợp lý",
        "phải chăng",
        "giá cả",
        "đắt đỏ",
        "giá",
        "tiền",
        "đắt",
        "rẻ",
        "sale",
        "dang tien",
        "hop ly",
        "phai chang",
        "gia ca",
        "dat do",
        "gia",
        "tien",
        "dat",
        "re",
    ],
    Aspect.PACKAGING_SHIPPING: [
        "giao hàng",
        "đóng gói",
        "vận chuyển",
        "shipper",
        "nhận hàng",
        "gói hàng",
        "ship",
        "hộp",
        "túi",
        "giao hang",
        "dong goi",
        "van chuyen",
        "nhan hang",
        "goi hang",
        "hop",
        "tui",
    ],
    Aspect.CUSTOMER_SERVICE: [
        "chăm sóc",
        "tư vấn",
        "hỗ trợ",
        "đổi trả",
        "thái độ",
        "trả lời",
        "tin nhắn",
        "shop",
        "cskh",
        "rep",
        "cham soc",
        "tu van",
        "ho tro",
        "doi tra",
        "thai do",
        "tra loi",
        "tin nhan",
    ],
    Aspect.ACCESSIBILITY_DESIGN: [
        "thời trang",
        "kiểu dáng",
        "họa tiết",
        "hình ảnh",
        "màu sắc",
        "mẫu mã",
        "màu",
        "mẫu",
        "đẹp",
        "xấu",
        "thoi trang",
        "kieu dang",
        "hoa tiet",
        "hinh anh",
        "mau sac",
        "mau ma",
        "mau",
        "dep",
        "xau",
    ],
}

# Polarity Lexicon
POSITIVE_WORDS = {
    "tốt",
    "tot",
    "đẹp",
    "dep",
    "bền",
    "ben",
    "dày",
    "day",
    "chắc",
    "chac",
    "xịn",
    "xin",
    "thích",
    "thich",
    "ưng",
    "ung",
    "hài lòng",
    "hai long",
    "chuẩn",
    "chuan",
    "nhanh",
    "vừa",
    "vua",
    "ổn",
    "on",
    "ok",
    "oke",
    "okie",
    "tuyệt",
    "tuyet",
    "tuyệt vời",
    "tuyet voi",
    "emo_pos",
    "rẻ",
    "re",
    "hợp lý",
    "hop ly",
    "đáng",
    "dang",
    "thoáng",
    "thoang",
    "tiện",
    "tien",
    "được",
    "duoc",
}

NEGATIVE_WORDS = {
    "xấu",
    "xau",
    "rách",
    "rach",
    "thấm",
    "tham",
    "ướt",
    "uot",
    "dột",
    "dot",
    "mỏng",
    "mong",
    "kém",
    "kem",
    "tệ",
    "te",
    "dở",
    "do",
    "chán",
    "chan",
    "hỏng",
    "emo_neg",
    "lỗi",
    "loi",
    "đắt",
    "dat",
    "chậm",
    "cham",
    "lâu",
    "lau",
    "nóng",
    "nong",
    "bí",
    "bi",
    "chật",
    "chat",
    "ngắn",
    "ngan",
    "bẩn",
    "ban",
    "hôi",
    "hoi",
    "thất vọng",
    "that vong",
}

NEGATION_WORDS = {
    "không",
    "khong",
    "ko",
    "k",
    "chưa",
    "chua",
    "chẳng",
    "chang",
    "đếch",
    "hổng",
    "hong",
    "ít",
    "it",
}


_CHAT_MESSAGING_FOLLOWERS = {"với", "vs", "shop", "cskh", "nhắn"}


def _is_messaging_chat(tokens: list[str], idx: int) -> bool:
    """Return True when 'chat' refers to customer-shop messaging rather than 'chật' (tight)."""
    if idx < 0 or idx >= len(tokens) or tokens[idx] != "chat":
        return False
    if idx + 1 < len(tokens) and tokens[idx + 1] in _CHAT_MESSAGING_FOLLOWERS:
        return True
    if idx > 0 and tokens[idx - 1] in {"nhắn", "tin"}:
        return True
    return False


class B1RuleAnalyzer:
    """Rule and lexicon-based ABSA analyzer for raincoat e-commerce reviews."""

    def __init__(self, window_size: int = 5, enable_norm: bool = True):
        self.window_size = window_size
        self.enable_norm = enable_norm

    def _score_tokens(
        self, sub_tokens: list[str], global_offset: int = 0, full_tokens: list[str] | None = None
    ) -> tuple[int, int]:
        """Count positive and negative n-gram sentiment hits with negation handling."""
        pos_count = 0
        neg_count = 0
        ctx_tokens = full_tokens if full_tokens is not None else sub_tokens

        i = 0
        while i < len(sub_tokens):
            matched_len = 1
            is_pos = False
            is_neg = False
            for n in (3, 2, 1):
                if i + n <= len(sub_tokens):
                    phrase = " ".join(sub_tokens[i : i + n])
                    if (
                        n == 1
                        and phrase == "chat"
                        and _is_messaging_chat(ctx_tokens, global_offset + i)
                    ):
                        continue
                    in_pos = phrase in POSITIVE_WORDS
                    in_neg = phrase in NEGATIVE_WORDS
                    if in_pos or in_neg:
                        matched_len = n
                        is_pos = in_pos
                        is_neg = in_neg
                        break

            if is_pos or is_neg:
                # Check if preceded by a negation word (1 or 2 tokens before phrase start)
                is_negated = any(
                    i - step >= 0 and sub_tokens[i - step] in NEGATION_WORDS for step in (1, 2)
                )
                if is_negated:
                    if is_pos:
                        neg_count += 1
                    elif is_neg:
                        pos_count += 1
                else:
                    if is_pos:
                        pos_count += 1
                    elif is_neg:
                        neg_count += 1

            i += matched_len

        return pos_count, neg_count

    def _determine_sentiment_in_window(
        self, tokens: list[str], target_idx: int, kw_len: int = 1
    ) -> Polarity:
        """Examine context window around target token span to assign polarity."""
        start = max(0, target_idx - self.window_size)
        end = min(len(tokens), target_idx + kw_len + self.window_size)
        sub_tokens = tokens[start:end]
        pos_count, neg_count = self._score_tokens(
            sub_tokens, global_offset=start, full_tokens=tokens
        )

        if pos_count > neg_count:
            return Polarity.POS
        if neg_count > pos_count:
            return Polarity.NEG
        return Polarity.NEU

    def analyze_review(self, text: str) -> ReviewAnalysis:
        """Analyze a single review text and return a ReviewAnalysis model."""
        if not text or not text.strip():
            return ReviewAnalysis(
                overall_sentiment=Polarity.NEU,
                opinions=[],
                informative=False,
            )

        norm_text = normalize_social_text(text, enable=self.enable_norm)
        tokens = re.findall(r"\w+", norm_text.lower())
        raw_matches = list(re.finditer(r"\w+", text))
        text_lower = text.lower()

        opinions: list[AspectOpinion] = []
        detected_aspects: set[Aspect] = set()

        # Iterate over all defined aspects and their keyword lexicons
        for aspect, keywords in ASPECT_LEXICON.items():
            for kw in keywords:
                kw_tokens = kw.split()
                kw_len = len(kw_tokens)

                # Search for multi-token or single-token keyword match
                for i in range(len(tokens) - kw_len + 1):
                    if tokens[i : i + kw_len] == kw_tokens:
                        if kw_len == 1 and kw == "chat" and _is_messaging_chat(tokens, i):
                            continue
                        if aspect not in detected_aspects:
                            pol = self._determine_sentiment_in_window(tokens, i, kw_len=kw_len)

                            # Extract verbatim slice from raw text preserving punctuation
                            verbatim_ev = ""
                            kw_lower = kw.lower()
                            if kw_lower in text_lower:
                                k_idx = text_lower.find(kw_lower)
                                span_start = max(0, k_idx - 12)
                                span_end = min(len(text), k_idx + len(kw) + 18)
                                verbatim_ev = text[span_start:span_end].strip()
                            elif raw_matches:
                                approx_idx = int(i * len(raw_matches) / max(1, len(tokens)))
                                raw_start = min(len(raw_matches) - 1, max(0, approx_idx - 2))
                                raw_end = min(len(raw_matches) - 1, approx_idx + kw_len + 2)
                                verbatim_ev = text[
                                    raw_matches[raw_start].start() : raw_matches[raw_end].end()
                                ]
                            if not verbatim_ev or verbatim_ev.lower() not in text_lower:
                                verbatim_ev = text[: min(40, len(text))].strip()

                            opinions.append(
                                AspectOpinion(
                                    aspect=aspect,
                                    polarity=pol,
                                    evidence=verbatim_ev,
                                )
                            )
                            detected_aspects.add(aspect)
                        break

        full_pos, full_neg = self._score_tokens(tokens)

        # Fallback to GENERAL aspect if no domain aspect matched
        if not opinions:
            if full_pos > full_neg:
                pol = Polarity.POS
            elif full_neg > full_pos:
                pol = Polarity.NEG
            else:
                pol = Polarity.NEU

            if raw_matches:
                end_m = raw_matches[min(7, len(raw_matches) - 1)]
                ev_slice = text[raw_matches[0].start() : end_m.end()]
            else:
                ev_slice = text[: min(30, len(text))]
            opinions.append(
                AspectOpinion(
                    aspect=Aspect.GENERAL,
                    polarity=pol,
                    evidence=ev_slice,
                )
            )

        # Compute overall sentiment from opinions
        pos_ops = sum(1 for op in opinions if op.polarity == Polarity.POS)
        neg_ops = sum(1 for op in opinions if op.polarity == Polarity.NEG)

        if pos_ops > neg_ops:
            overall = Polarity.POS
        elif neg_ops > pos_ops:
            overall = Polarity.NEG
        else:
            if full_pos > full_neg:
                overall = Polarity.POS
            elif full_neg > full_pos:
                overall = Polarity.NEG
            else:
                overall = Polarity.POS  # E-commerce default bias

        informative = len(tokens) >= 3

        return ReviewAnalysis(
            overall_sentiment=overall,
            opinions=opinions,
            informative=informative,
        )


# CreBy: MenBoyBMN
