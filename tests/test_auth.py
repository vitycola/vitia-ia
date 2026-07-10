from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from src.auth.jwt import AuthError, verify_jwt
from tests.conftest import make_token

# ---------------------------------------------------------------------------
# HTTP-layer integration tests
# ---------------------------------------------------------------------------


def test_valid_token(client: TestClient, jwt_secret: str) -> None:
    token = make_token(jwt_secret, sub="user-abc")
    response = client.get(
        "/test-protected",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == "user-abc"


def test_expired_token(client: TestClient, jwt_secret: str) -> None:
    token = make_token(jwt_secret, exp_delta=timedelta(seconds=-1))
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


def test_verify_jwt_valid(jwt_secret: str) -> None:
    token = make_token(jwt_secret, sub="u-999")
    claims = verify_jwt(token, jwt_secret)
    assert claims["sub"] == "u-999"


def test_verify_jwt_expired(jwt_secret: str) -> None:
    token = make_token(jwt_secret, exp_delta=timedelta(seconds=-1))
    with pytest.raises(AuthError) as exc_info:
        verify_jwt(token, jwt_secret)
    assert exc_info.value.reason == "expired"


def test_verify_jwt_malformed(jwt_secret: str) -> None:
    with pytest.raises(AuthError):
        verify_jwt("not.a.jwt", jwt_secret)


def test_verify_jwt_wrong_secret(jwt_secret: str) -> None:
    token = make_token(jwt_secret)
    with pytest.raises(AuthError):
        verify_jwt(token, "wrong-secret")
