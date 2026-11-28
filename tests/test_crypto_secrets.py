"""Tests for at-rest secret encryption, key rotation, and production fail-closed checks."""

from __future__ import annotations

import json
import sqlite3

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from ecomreview.api.auth import hash_password
from ecomreview.api.main import create_app
from ecomreview.crypto import (
    ENCRYPTED_PREFIX,
    decrypt_secret,
    encrypt_secret,
    get_encryption_keys,
)
from ecomreview.db.database import DatabaseManager


class TestSecretEncryptionAtRest:
    def test_encrypt_decrypt_roundtrip_idempotent_and_key_rotation(self, monkeypatch):
        k1 = Fernet.generate_key().decode("ascii")
        k2 = Fernet.generate_key().decode("ascii")
        monkeypatch.setenv("ECOMREVIEW_ENV", "production")
        monkeypatch.setenv("ECOMREVIEW_ENCRYPTION_KEY", k1)

        enc1 = encrypt_secret("12345:MY_BOT_TOKEN")
        assert enc1.startswith(ENCRYPTED_PREFIX)
        assert "12345:MY_BOT_TOKEN" not in enc1
        # Idempotent re-encryption does not double-wrap
        assert encrypt_secret(enc1) == enc1
        assert decrypt_secret(enc1) == "12345:MY_BOT_TOKEN"

        # Legacy unencrypted value passes through cleanly
        assert decrypt_secret("legacy_plain_secret") == "legacy_plain_secret"
        assert decrypt_secret("") == ""
        assert encrypt_secret("") == ""

        # Key rotation: k2 is new primary, k1 remains for reading old ciphertexts
        monkeypatch.setenv("ECOMREVIEW_ENCRYPTION_KEY", f"{k2},{k1}")
        assert decrypt_secret(enc1) == "12345:MY_BOT_TOKEN"
        enc2 = encrypt_secret("new_secret_value")
        assert decrypt_secret(enc2) == "new_secret_value"

    def test_production_requires_valid_encryption_key(self, monkeypatch):
        monkeypatch.setenv("ECOMREVIEW_ENV", "production")
        monkeypatch.delenv("ECOMREVIEW_ENCRYPTION_KEY", raising=False)
        with pytest.raises(RuntimeError, match="ECOMREVIEW_ENCRYPTION_KEY"):
            get_encryption_keys()

        monkeypatch.setenv("ECOMREVIEW_ENCRYPTION_KEY", "not-a-valid-fernet-key")
        with pytest.raises(RuntimeError, match="ECOMREVIEW_ENCRYPTION_KEY"):
            get_encryption_keys()

    def test_pilot_shop_secrets_are_encrypted_in_db_and_masked_on_list(self, tmp_path, monkeypatch):
        k = Fernet.generate_key().decode("ascii")
        monkeypatch.setenv("ECOMREVIEW_ENV", "production")
        monkeypatch.setenv("ECOMREVIEW_JWT_SECRET", "super-strong-pilot-jwt-secret-key-32bytes")
        monkeypatch.setenv("ECOMREVIEW_ENCRYPTION_KEY", k)
        monkeypatch.setenv("ECOMREVIEW_CORS_ORIGINS", "https://pilot.ecomreview.vn")

        db_file = tmp_path / "enc_shops.db"
        db = DatabaseManager(db_path=str(db_file), db_backend="sqlite")
        created = db.create_pilot_shop(
            slug="shop_enc",
            name="Shop Encrypted",
            alert_config={
                "telegram_bot_token": "99999:SECRET_TG_TOKEN",
                "telegram_chat_id": "-100123",
            },
            webhook_secret="raw_wh_secret_123456",
        )
        assert created["webhook_secret"] == "raw_wh_secret_123456"
        assert created["alert_config"]["telegram_bot_token"] == "99999:SECRET_TG_TOKEN"

        # Inspect raw SQLite row directly to confirm ciphertext on disk
        with sqlite3.connect(db_file) as raw_conn:
            row = raw_conn.execute(
                "SELECT webhook_secret, alert_config FROM pilot_shops WHERE slug = 'shop_enc'"
            ).fetchone()
        assert row is not None
        raw_wh_secret, raw_alert_json = row
        assert str(raw_wh_secret).startswith(ENCRYPTED_PREFIX)
        assert "raw_wh_secret_123456" not in str(raw_wh_secret)
        parsed_alert = json.loads(raw_alert_json)
        assert str(parsed_alert["telegram_bot_token"]).startswith(ENCRYPTED_PREFIX)
        assert "99999:SECRET_TG_TOKEN" not in raw_alert_json

        # Updating other alert fields preserves encrypted token without double-encrypting
        db.update_pilot_shop_alerts("shop_enc", {"min_rating_alert": 1})
        loaded = db.get_pilot_shop("shop_enc", include_secret=True)
        assert loaded is not None
        assert loaded["alert_config"]["telegram_bot_token"] == "99999:SECRET_TG_TOKEN"
        assert loaded["webhook_secret"] == "raw_wh_secret_123456"

        # Public shop list endpoint masks token and never exposes webhook_secret
        db.upsert_user(
            email="owner@enc.vn",
            password_hash=hash_password("OwnerPass123!"),
            full_name="Owner Enc",
            role="owner",
            allowed_shops=["shop_enc"],
        )
        app = create_app(db_path=str(db_file))
        client = TestClient(app, base_url="https://testserver")
        client.post(
            "/api/v1/auth/login",
            json={"email": "owner@enc.vn", "password": "OwnerPass123!"},
        )
        r_shops = client.get("/api/v1/shops")
        assert r_shops.status_code == 200
        shop_item = r_shops.json()["shops"][0]
        assert "webhook_secret" not in shop_item
        assert shop_item["alert_config"]["telegram_bot_token"] == ""
        assert shop_item["alert_config"]["telegram_bot_token_configured"] is True


# CreBy: MenBoyBMN
