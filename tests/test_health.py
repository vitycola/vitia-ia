import pytest
from fastapi.testclient import TestClient

from src.main import create_app


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_ok_body(client: TestClient) -> None:
    response = client.get("/health")
    assert response.json() == {"status": "ok"}


@pytest.fixture
def cors_client() -> TestClient:
    app = create_app(allowed_origins=["https://vitia.app"])
    return TestClient(app, raise_server_exceptions=True)


def test_cors_allowed_origin_receives_header(cors_client: TestClient) -> None:
    response = cors_client.get("/health", headers={"Origin": "https://vitia.app"})
    assert response.headers.get("access-control-allow-origin") == "https://vitia.app"


def test_cors_disallowed_origin_receives_no_header(cors_client: TestClient) -> None:
    response = cors_client.get("/health", headers={"Origin": "https://evil.com"})
    assert "access-control-allow-origin" not in response.headers
