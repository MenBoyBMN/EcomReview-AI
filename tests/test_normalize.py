"""Unit tests for Vietnamese social text normalization module."""

from ecomreview.normalize import extract_noise_flags, normalize_social_text


class TestNormalizeSocialText:
    """Test suite for normalize_social_text function."""

    def test_price_k_protection(self):
        """Ensure '150k' is transformed to '150 nghìn' and does not conflict with 'k' -> 'không'."""
        raw = "Áo 150k ko thấm nc"
        normalized = normalize_social_text(raw, enable=True)
        assert "150 nghìn" in normalized
        assert "không" in normalized
        assert "nước" in normalized
        assert "150 không" not in normalized

    def test_character_elongation_compression(self):
        """Ensure repeated letters (>= 3 times) are compressed to single occurrence."""
        raw = "áo mỏnggggg và đẹppppp quá"
        normalized = normalize_social_text(raw, enable=True)
        assert "mỏng" in normalized
        assert "đẹp" in normalized
        assert "mỏnggggg" not in normalized

    def test_punctuation_compression(self):
        """Ensure repeated punctuation marks are collapsed to a single character."""
        raw = "chất lượng quá tệ!!!!!! hàng rách????"
        normalized = normalize_social_text(raw, enable=True)
        assert "tệ!" in normalized
        assert "rách?" in normalized
        assert "!!!!!!" not in normalized

    def test_teencode_mapping_with_punctuation(self):
        """Ensure teencode words with surrounding punctuation are correctly mapped."""
        raw = "sp này okla, mik rất ưng! shop rep ib nhanh."
        normalized = normalize_social_text(raw, enable=True)
        assert "sản phẩm" in normalized
        assert "ok," in normalized
        assert "mình" in normalized
        assert "ưng ý!" in normalized
        assert "trả lời" in normalized
        assert "nhắn tin" in normalized

    def test_emoji_positive_mapping(self):
        """Ensure positive emojis are replaced by [EMO_POS] tokens."""
        raw = "áo mặc rất thích 😍🥰❤️"
        normalized = normalize_social_text(raw, enable=True)
        assert "[EMO_POS]" in normalized
        assert "😍" not in normalized

    def test_emoji_negative_mapping(self):
        """Ensure negative emojis are replaced by [EMO_NEG] tokens."""
        raw = "mới mặc 1 lần đã rách 😡👎💔"
        normalized = normalize_social_text(raw, enable=True)
        assert "[EMO_NEG]" in normalized
        assert "😡" not in normalized

    def test_enable_toggle_off(self):
        """When enable=False, text is cleaned for NFC/whitespace but teencode is preserved."""
        raw = "áo 150k  ko  thấm  nc   "
        normalized = normalize_social_text(raw, enable=False)
        assert normalized == "áo 150k ko thấm nc"
        assert "150 nghìn" not in normalized
        assert "không" not in normalized

    def test_empty_and_none_input(self):
        """Ensure empty and None inputs return an empty string without raising an exception."""
        assert normalize_social_text("") == ""
        assert normalize_social_text(None) == ""
        assert normalize_social_text("   ") == ""


class TestExtractNoiseFlags:
    """Test suite for extract_noise_flags function."""

    def test_detect_teencode(self):
        """Verify proper detection of teencode tokens."""
        text = "áo này ko thấm nc nha sop"
        flags = extract_noise_flags(text)
        assert flags["has_teencode"] is True

    def test_detect_no_diacritics(self):
        """Verify non-accented Vietnamese sentence detection."""
        text = "ao mua mong qua di mua bi uot het"
        flags = extract_noise_flags(text)
        assert flags["is_no_diacritics"] is True

    def test_with_diacritics_not_flagged(self):
        """Verify standard accented Vietnamese text is not flagged as no diacritics."""
        text = "áo mưa dày dặn đi mưa không ướt"
        flags = extract_noise_flags(text)
        assert flags["is_no_diacritics"] is False

    def test_detect_emoji(self):
        """Verify presence of sentiment emojis is detected."""
        text = "sản phẩm tuyệt vời 👍💯"
        flags = extract_noise_flags(text)
        assert flags["has_emoji"] is True

    def test_detect_short_review(self):
        """Verify short reviews (<= 3 words) are flagged."""
        text = "quá tốt"
        flags = extract_noise_flags(text)
        assert flags["is_short"] is True

        long_text = "áo mưa chống thấm rất tốt mặc vừa vặn thoải mái"
        flags_long = extract_noise_flags(long_text)
        assert flags_long["is_short"] is False

    def test_empty_noise_flags(self):
        """Verify flags for empty text input."""
        flags = extract_noise_flags("")
        assert flags["has_teencode"] is False
        assert flags["is_short"] is True


# CreBy: MenBoyBMN
