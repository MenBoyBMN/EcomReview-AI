"""Baseline 1 (B1): Rule and Lexicon-based ABSA Analyzer.

Zero ML, zero training cost, instant deterministic inference.
Employs domain-specific keyword matching, context sliding windows (+-5 words),
and negation handling for Vietnamese e-commerce customer feedback.
"""

import re
from typing import Sequence

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
    "hong",
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


class B1RuleAnalyzer:
    """Rule and lexicon-based ABSA analyzer for raincoat e-commerce reviews."""

    def __init__(self, window_size: int = 5):
        self.window_size = window_size

    def _determine_sentiment_in_window(
        self, tokens: list[str], target_idx: int
    ) -> tuple[Polarity, str]:
        """Examine context window around target token index to assign polarity."""
        start = max(0, target_idx - self.window_size)
        end = min(len(tokens), target_idx + self.window_size + 1)
        sub_tokens = tokens[start:end]
        evidence = " ".join(sub_tokens)

        pos_count = 0
        neg_count = 0

        for i, tok in enumerate(sub_tokens):
            is_pos = tok in POSITIVE_WORDS
            is_neg = tok in NEGATIVE_WORDS

            if not is_pos and not is_neg:
                continue

            # Check if preceded by a negation word (1 or 2 tokens before)
            is_negated = False
            for step in (1, 2):
                if i - step >= 0 and sub_tokens[i - step] in NEGATION_WORDS:
                    is_negated = True
                    break

            if is_negated:
                # Invert polarity
                if is_pos:
                    neg_count += 1
                elif is_neg:
                    pos_count += 1
            else:
                if is_pos:
                    pos_count += 1
                elif is_neg:
                    neg_count += 1

        if pos_count > neg_count:
            return Polarity.POS, evidence
        if neg_count > pos_count:
            return Polarity.NEG, evidence
        return Polarity.NEU, evidence

    def analyze_review(self, text: str) -> ReviewAnalysis:
        """Analyze a single review text and return a ReviewAnalysis model."""
        if not text or not text.strip():
            return ReviewAnalysis(
                overall_sentiment=Polarity.NEU,
                opinions=[],
                informative=False,
            )

        norm_text = normalize_social_text(text, enable=True)
        tokens = re.findall(r"\w+", norm_text.lower())
        raw_tokens = re.findall(r"\w+", text)

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
                        if aspect not in detected_aspects:
                            pol, _ = self._determine_sentiment_in_window(tokens, i)

                            # Extract verbatim slice from raw text if possible for evidence
                            raw_start = max(0, i - 2)
                            raw_end = min(len(raw_tokens), i + kw_len + 3)
                            verbatim_ev = " ".join(raw_tokens[raw_start:raw_end])
                            if not verbatim_ev or verbatim_ev.lower() not in text.lower():
                                verbatim_ev = " ".join(kw_tokens)

                            opinions.append(
                                AspectOpinion(
                                    aspect=aspect,
                                    polarity=pol,
                                    evidence=verbatim_ev,
                                )
                            )
                            detected_aspects.add(aspect)
                        break

        # Fallback to GENERAL aspect if no domain aspect matched
        if not opinions:
            # Overall polarity check on full text
            pos_total = sum(1 for tok in tokens if tok in POSITIVE_WORDS)
            neg_total = sum(1 for tok in tokens if tok in NEGATIVE_WORDS)
            if pos_total > neg_total:
                pol = Polarity.POS
            elif neg_total > pos_total:
                pol = Polarity.NEG
            else:
                pol = Polarity.NEU

            ev_tokens = raw_tokens[:8] if raw_tokens else [text[:20]]
            opinions.append(
                AspectOpinion(
                    aspect=Aspect.GENERAL,
                    polarity=pol,
                    evidence=" ".join(ev_tokens),
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
            # Tie breaker: check raw text positive vs negative signals
            pos_t = sum(1 for tok in tokens if tok in POSITIVE_WORDS)
            neg_t = sum(1 for tok in tokens if tok in NEGATIVE_WORDS)
            if pos_t > neg_t:
                overall = Polarity.POS
            elif neg_t > pos_t:
                overall = Polarity.NEG
            else:
                overall = Polarity.POS  # E-commerce default bias

        informative = len(tokens) >= 3 and not (len(tokens) <= 2 and "ok" in tokens)

        return ReviewAnalysis(
            overall_sentiment=overall,
            opinions=opinions,
            informative=informative,
        )

    def analyze_batch(self, texts: Sequence[str]) -> list[ReviewAnalysis]:
        """Analyze a list of review texts sequentially."""
        return [self.analyze_review(t) for t in texts]


# CreBy: MenBoyBMN
