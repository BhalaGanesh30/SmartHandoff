"""Unit tests for otp_helpers key derivation and bcrypt functions."""

import pytest

from app.core.auth.otp_helpers import (
    otp_redis_key,
    rate_limit_redis_key,
    failures_redis_key,
    hash_otp,
    verify_otp,
)
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def set_otp_salt_env(monkeypatch):
    """Inject OTP_PHONE_SALT and clear the lru_cache."""
    monkeypatch.setenv("OTP_PHONE_SALT", "test-salt")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestKeyDerivation:
    def test_otp_key_prefix(self):
        assert otp_redis_key("token-abc").startswith("otp:")

    def test_rate_limit_key_prefix(self):
        assert rate_limit_redis_key("+12345678901").startswith("otp_rate:")

    def test_failures_key_prefix(self):
        assert failures_redis_key("token-abc").startswith("otp_failures:")

    def test_otp_key_does_not_contain_plaintext_token(self):
        token = "my-secret-portal-token"
        assert token not in otp_redis_key(token)

    def test_rate_limit_key_does_not_contain_phone(self):
        phone = "+12345678901"
        assert phone not in rate_limit_redis_key(phone)

    def test_different_tokens_produce_different_otp_keys(self):
        assert otp_redis_key("token-A") != otp_redis_key("token-B")

    def test_same_token_produces_stable_key(self):
        assert otp_redis_key("stable-token") == otp_redis_key("stable-token")


class TestBcryptHelpers:
    def test_hash_otp_returns_bcrypt_string(self):
        h = hash_otp("123456")
        assert h.startswith("$2b$")

    def test_verify_otp_correct_code(self):
        h = hash_otp("654321")
        assert verify_otp("654321", h) is True

    def test_verify_otp_wrong_code(self):
        h = hash_otp("111111")
        assert verify_otp("999999", h) is False

    def test_different_calls_produce_different_hashes(self):
        # bcrypt uses random salt — same OTP should yield different hashes
        assert hash_otp("123456") != hash_otp("123456")
