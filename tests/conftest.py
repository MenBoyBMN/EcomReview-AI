"""Pytest session isolation to prevent local production .env from polluting test collection."""

from __future__ import annotations

import os

# Isolate test collection from local .env (load_dotenv() defaults to override=False).
# Production-mode tests explicitly set ECOMREVIEW_ENV=production via monkeypatch.
os.environ["ECOMREVIEW_ENV"] = "development"

# CreBy: MenBoyBMN
