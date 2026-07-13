"""Tests for POST /api/parse route."""

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from src.auth.dependencies import get_current_user
from src.auth.models import CurrentUser
from src.domain.food import MacroTotals, MacrosPer100g, MatchedFood, MatchResult
from src.main import create_app
from src.routes.parse import get_text_parsing_service
from src.services.errors import LLMError, LLMTimeoutError

_DUMMY_USER = CurrentUser(user_id="test-user-id")

_EMPTY_RESULT = MatchResult(items=[], totals=MacroTotals(), degraded=False)


def _matched_food(query_name: str) -> MatchedFood:
    return MatchedFood(
        query_name=query_name,
        grams=100.0,
        source="supabase",
        matched_name=query_name,
        macros_per_100g=MacrosPer100g(calories=100.0, protein=5.0, carbs=10.0, fat=2.0),
        macros_actual=MacroTotals(calories=100.0, protein=5.0, carbs=10.0, fat=2.0),
    )


def _make_app(service=None):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _DUMMY_USER
    if service is not None:
        app.dependency_overrides[get_text_parsing_service] = lambda: service
    return app


def _mock_service(result=_EMPTY_RESULT, side_effect=None):
    svc = MagicMock()
    if side_effect is not None:
        svc.parse = AsyncMock(side_effect=side_effect)
    else:
        svc.parse = AsyncMock(return_value=result)
    return svc


def test_parse_valid_text_returns_200_with_items():
    items = [_matched_food("pollo")]
    result = MatchResult(
        items=items,
        totals=MacroTotals(calories=100.0, protein=5.0, carbs=10.0, fat=2.0),
        degraded=False,
    )
    app = _make_app(_mock_service(result=result))
    with TestClient(app) as client:
        resp = client.post("/api/parse", json={"text": "pollo a la plancha"})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["query_name"] == "pollo"
    assert body["skipped"] == []


def test_parse_all_unmatched_returns_200_empty_items_with_skipped():
    result = MatchResult(
        items=[],
        totals=MacroTotals(),
        degraded=False,
        skipped=["xyzfood", "blargh"],
    )
    app = _make_app(_mock_service(result=result))
    with TestClient(app) as client:
        resp = client.post("/api/parse", json={"text": "xyzfood and blargh"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert set(body["skipped"]) == {"xyzfood", "blargh"}


def test_parse_empty_text_returns_422():
    app = _make_app(_mock_service())
    with TestClient(app) as client:
        resp = client.post("/api/parse", json={"text": ""})

    assert resp.status_code == 422


def test_parse_whitespace_only_text_returns_422():
    app = _make_app(_mock_service())
    with TestClient(app) as client:
        resp = client.post("/api/parse", json={"text": "   "})

    assert resp.status_code == 422


def test_parse_requires_auth():
    app = create_app()  # no auth override
    with TestClient(app) as client:
        resp = client.post("/api/parse", json={"text": "pollo"})

    assert resp.status_code == 401


def test_parse_llm_timeout_returns_504():
    app = _make_app(_mock_service(side_effect=LLMTimeoutError()))
    with TestClient(app) as client:
        resp = client.post("/api/parse", json={"text": "some food"})

    assert resp.status_code == 504


def test_parse_llm_error_returns_502():
    app = _make_app(_mock_service(side_effect=LLMError("model failure")))
    with TestClient(app) as client:
        resp = client.post("/api/parse", json={"text": "some food"})

    assert resp.status_code == 502
