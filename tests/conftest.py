import os
from datetime import UTC, datetime, timedelta

# Set required env vars before any src imports trigger Settings validation
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-for-tests-only-32bytes!!")

import jwt
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from src.auth.dependencies import get_current_user
from src.auth.models import CurrentUser
from src.main import create_app

_TEST_JWT_SECRET = "test-secret-for-tests-only-32bytes!!"


def make_token(
    secret: str,
    *,
    sub: str = "user-123",
    exp_delta: timedelta = timedelta(hours=1),
    **extra: object,
) -> str:
    payload = {
        "sub": sub,
        "exp": datetime.now(tz=UTC) + exp_delta,
        **extra,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def jwt_secret() -> str:
    return _TEST_JWT_SECRET


@pytest.fixture
def client() -> TestClient:
    app = create_app()

    # Register a protected test route for auth integration tests
    @app.get("/test-protected")
    async def test_protected(current_user: CurrentUser = Depends(get_current_user)):  # noqa: B008
        return {"user_id": current_user.user_id}

    return TestClient(app)
