"""Integration tests for POST /food/match."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.auth.dependencies import get_current_user
from src.auth.models import CurrentUser
from src.domain.food import MacroTotals, MatchResult
from src.main import create_app
from src.routes.food import get_food_matcher_service

_DUMMY_USER = CurrentUser(user_id="test-user-id")


def _make_app_with_service(mock_service):
    app = create_app()
    app.dependency_overrides[get_food_matcher_service] = lambda: mock_service
    app.dependency_overrides[get_current_user] = lambda: _DUMMY_USER
    return app


@pytest.fixture
def matched_service():
    """Service that returns one matched item per food in the payload."""

    async def _match_all(foods):
        from src.domain.food import MacrosPer100g, MatchedFood

        items = [
            MatchedFood(
                query_name=f.name,
                grams=f.estimated_grams,
                source="supabase",
                matched_name=f.name,
                score=90.0,
                macros_per_100g=MacrosPer100g(calories=100.0, protein=5.0, carbs=10.0, fat=3.0),
                macros_actual=MacroTotals(calories=100.0, protein=5.0, carbs=10.0, fat=3.0),
                low_confidence=False,
            )
            for f in foods.items
        ]
        return MatchResult(
            items=items,
            totals=MacroTotals(
                calories=sum(i.macros_actual.calories for i in items),
                protein=sum(i.macros_actual.protein for i in items),
                carbs=sum(i.macros_actual.carbs for i in items),
                fat=sum(i.macros_actual.fat for i in items),
            ),
            degraded=False,
        )

    svc = MagicMock()
    svc.match_all = _match_all
    return svc


@pytest.fixture
def degraded_service():
    svc = MagicMock()
    svc.match_all = AsyncMock(
        return_value=MatchResult(items=[], totals=MacroTotals(), degraded=True)
    )
    return svc


def test_valid_request_returns_200(matched_service) -> None:
    app = _make_app_with_service(matched_service)
    with TestClient(app) as client:
        payload = {
            "items": [
                {"name": "chicken", "estimated_grams": 150.0, "confidence": 0.9},
                {"name": "rice", "estimated_grams": 100.0, "confidence": 0.85},
            ]
        }
        response = client.post("/food/match", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["degraded"] is False


def _make_app_no_service() -> object:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _DUMMY_USER
    return app


def test_malformed_payload_returns_422() -> None:
    """An item with a missing required field (name) must yield 422."""
    app = _make_app_no_service()
    with TestClient(app) as client:
        # estimated_grams and confidence present, but name is missing — required field
        response = client.post(
            "/food/match",
            json={"items": [{"estimated_grams": 100.0, "confidence": 0.9}]},
        )
    assert response.status_code == 422


def test_degraded_returns_200_with_flag(degraded_service) -> None:
    app = _make_app_with_service(degraded_service)
    with TestClient(app) as client:
        payload = {"items": [{"name": "apple", "estimated_grams": 80.0, "confidence": 0.9}]}
        response = client.post("/food/match", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is True
    assert body["items"] == []


def test_route_appears_in_openapi() -> None:
    app = _make_app_no_service()
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    paths = schema.get("paths", {})
    assert "/food/match" in paths
    assert "post" in paths["/food/match"]


# ---------------------------------------------------------------------------
# Auth guard tests for POST /food/match (T10)
# ---------------------------------------------------------------------------


def test_food_match_requires_auth_no_header() -> None:
    """POST /food/match without Authorization header returns 401."""
    app = create_app()
    payload = {"items": [{"name": "apple", "estimated_grams": 80.0, "confidence": 0.9}]}
    with TestClient(app) as client:
        response = client.post("/food/match", json=payload)
    assert response.status_code == 401


def test_food_match_requires_auth_invalid_token() -> None:
    """POST /food/match with a tampered token returns 401."""
    app = create_app()
    payload = {"items": [{"name": "apple", "estimated_grams": 80.0, "confidence": 0.9}]}
    with TestClient(app) as client:
        response = client.post(
            "/food/match",
            json=payload,
            headers={"Authorization": "Bearer not.a.valid.token"},
        )
    assert response.status_code == 401
