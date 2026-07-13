"""Tests for Settings startup validator and JWT aud/iss verification (T10)."""

import pytest

from tests.conftest import make_token

# ---------------------------------------------------------------------------
# Settings fail-fast validator (T02)
# ---------------------------------------------------------------------------


def test_settings_raises_when_supabase_url_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_ANON_KEY", "some-key")
    monkeypatch.setenv("SUPABASE_JWKS_URL", "https://x.supabase.co/auth/v1/.well-known/jwks.json")

    from src.config import Settings, get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(Exception, match="SUPABASE_URL"):
            Settings()
    finally:
        get_settings.cache_clear()


def test_settings_raises_when_supabase_anon_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_JWKS_URL", "https://x.supabase.co/auth/v1/.well-known/jwks.json")

    from src.config import Settings, get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(Exception, match="SUPABASE_ANON_KEY"):
            Settings()
    finally:
        get_settings.cache_clear()


def test_settings_raises_when_supabase_jwks_url_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "some-key")
    monkeypatch.delenv("SUPABASE_JWKS_URL", raising=False)

    from src.config import Settings, get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(Exception, match="SUPABASE_JWKS_URL"):
            Settings()
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# JWT aud/iss verification (T03)
# ---------------------------------------------------------------------------


def test_verify_jwt_rejects_wrong_audience(
    ec_private_key,
) -> None:
    """A token with wrong aud claim must raise AuthError."""
    from src.auth.jwt import AuthError, verify_jwt

    token = make_token(ec_private_key, aud="wrong-audience")

    with pytest.raises(AuthError):
        verify_jwt(token, "https://fake.test/jwks.json")


def test_verify_jwt_rejects_wrong_issuer(
    ec_private_key,
) -> None:
    """A token with wrong iss claim must raise AuthError."""
    from src.auth.jwt import AuthError, verify_jwt

    token = make_token(ec_private_key, iss="https://evil.example.com/auth/v1")

    with pytest.raises(AuthError):
        verify_jwt(token, "https://fake.test/jwks.json")


def test_verify_jwt_accepts_correct_aud_iss(
    ec_private_key,
) -> None:
    """A token with correct aud and iss must decode successfully."""
    from src.auth.jwt import verify_jwt

    token = make_token(
        ec_private_key,
        aud="authenticated",
    )
    claims = verify_jwt(token, "https://fake.test/jwks.json")
    assert claims["sub"] == "user-123"
