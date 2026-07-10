from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from src.auth.jwt import AuthError, verify_jwt
from tests.conftest import make_token

# ---------------------------------------------------------------------------
# HTTP-layer integration tests
# ---------------------------------------------------------------------------


def test_valid_token(client: TestClient, ec_private_key: ec.EllipticCurvePrivateKey) -> None:
    token = make_token(ec_private_key, sub="user-abc")
    response = client.get(
        "/test-protected",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == "user-abc"


def test_expired_token(client: TestClient, ec_private_key: ec.EllipticCurvePrivateKey) -> None:
    token = make_token(ec_private_key, exp_delta=timedelta(seconds=-1))
    response = client.get(
        "/test-protected",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_malformed_token(client: TestClient) -> None:
    response = client.get(
        "/test-protected",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert response.status_code == 401


def test_missing_token(client: TestClient) -> None:
    response = client.get("/test-protected")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_health_still_public(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Unit tests for verify_jwt (pure, no HTTP)
# ---------------------------------------------------------------------------


def test_verify_jwt_valid(
    ec_private_key: ec.EllipticCurvePrivateKey,
    ec_public_key: ec.EllipticCurvePublicKey,
) -> None:
    token = make_token(ec_private_key, sub="u-999")
    claims = verify_jwt(token, "https://fake.test/jwks.json")
    assert claims["sub"] == "u-999"


def test_verify_jwt_expired(ec_private_key: ec.EllipticCurvePrivateKey) -> None:
    token = make_token(ec_private_key, exp_delta=timedelta(seconds=-1))
    with pytest.raises(AuthError) as exc_info:
        verify_jwt(token, "https://fake.test/jwks.json")
    assert exc_info.value.reason == "expired"


def test_verify_jwt_malformed() -> None:
    with pytest.raises(AuthError):
        verify_jwt("not.a.jwt", "https://fake.test/jwks.json")


def test_verify_jwt_wrong_key(ec_private_key: ec.EllipticCurvePrivateKey) -> None:
    token = make_token(ec_private_key, sub="u-999")

    # Make the mock return a different public key so signature verification fails
    wrong_key = ec.generate_private_key(ec.SECP256R1()).public_key()
    signing_key_mock = MagicMock()
    signing_key_mock.key = wrong_key

    with patch("src.auth.jwt.PyJWKClient") as mock_cls:
        instance = MagicMock()
        instance.get_signing_key_from_jwt.return_value = signing_key_mock
        mock_cls.return_value = instance

        with pytest.raises(AuthError):
            verify_jwt(token, "https://fake.test/jwks.json")
