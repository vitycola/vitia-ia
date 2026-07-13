import os

import pytest
from fastapi.testclient import TestClient

from src.main import app

integration = pytest.mark.skipif(
    os.getenv("SKIP_INTEGRATION_TESTS") == "1" or os.getenv("CI") == "true",
    reason="Integration tests skipped in CI",
)


@integration
def test_analyze_real_llm():
    """POST a real food image to /api/analyze with a real JWT and assert 200 + non-empty items."""
    import pathlib

    fixture = pathlib.Path(__file__).parent.parent / "fixtures" / "test_food.jpg"
    assert fixture.exists(), f"Test fixture not found: {fixture}"

    # Requires a valid JWT in TEST_JWT env var and all real credentials configured.
    jwt_token = os.getenv("TEST_JWT", "")
    if not jwt_token:
        pytest.skip("TEST_JWT env var not set — skipping real LLM integration test")

    with TestClient(app) as client:
        with fixture.open("rb") as f:
            resp = client.post(
                "/api/analyze",
                files={"file": ("test_food.jpg", f, "image/jpeg")},
                headers={"Authorization": f"Bearer {jwt_token}"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("items"), list)
    assert len(body["items"]) > 0, "Expected at least one food item identified"
