import os
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

# Set required env vars before any src imports trigger Settings validation
os.environ.setdefault("SUPABASE_JWKS_URL", "https://fake.test/jwks.json")
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "fake-anon-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends
from fastapi.testclient import TestClient

from src.auth.dependencies import get_current_user
from src.auth.models import CurrentUser
from src.config import get_settings
from src.main import create_app

# Generate a single EC keypair for the entire test session
_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
_PUBLIC_KEY = _PRIVATE_KEY.public_key()


def make_token(
    private_key: ec.EllipticCurvePrivateKey,
    *,
    sub: str = "user-123",
    exp_delta: timedelta = timedelta(hours=1),
    aud: str = "authenticated",
    iss: str | None = None,
    **extra: object,
) -> str:
    if iss is None:
        iss = f"{get_settings().supabase_url}/auth/v1"
    payload = {
        "sub": sub,
        "exp": datetime.now(tz=UTC) + exp_delta,
        "aud": aud,
        "iss": iss,
        **extra,
    }
    return jwt.encode(payload, private_key, algorithm="ES256")


@pytest.fixture
def ec_private_key() -> ec.EllipticCurvePrivateKey:
    return _PRIVATE_KEY


@pytest.fixture
def ec_public_key() -> ec.EllipticCurvePublicKey:
    return _PUBLIC_KEY


@pytest.fixture(autouse=True)
def mock_jwks_client(ec_public_key):
    """Patch PyJWKClient so tests never hit the network."""
    signing_key_mock = MagicMock()
    signing_key_mock.key = ec_public_key

    with patch("src.auth.jwt.PyJWKClient") as mock_cls:
        instance = MagicMock()
        instance.get_signing_key_from_jwt.return_value = signing_key_mock
        mock_cls.return_value = instance
        yield mock_cls


@pytest.fixture
def client() -> TestClient:
    app = create_app()

    # Register a protected test route for auth integration tests
    @app.get("/test-protected")
    async def test_protected(current_user: CurrentUser = Depends(get_current_user)):  # noqa: B008
        return {"user_id": current_user.user_id}

    return TestClient(app)


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    get_settings.cache_clear()
    from src.config import Settings

    s = Settings()
    yield s
    get_settings.cache_clear()
