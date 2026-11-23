"""Abstract connector interface for two-way Marketplace API integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class BasePlatformConnector(ABC):
    """Contract for fetching customer reviews and posting approved replies to a marketplace."""

    platform_name: str = "generic"

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if partner credentials and shop access token are available."""

    @abstractmethod
    def fetch_reviews(
        self, since: datetime | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Pull new customer reviews normalized to EcomReview ingestion format."""

    @abstractmethod
    def post_reply(self, external_review_id: str, reply_text: str) -> dict[str, Any]:
        """Push an approved, G1-G6 verified CSKH reply directly to the marketplace."""


# CreBy: MenBoyBMN
