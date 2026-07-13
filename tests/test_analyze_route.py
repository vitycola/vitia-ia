"""Tests for POST /api/analyze route."""

import io
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.dependencies import get_current_user
from src.auth.models import CurrentUser
from src.domain.food import MacroTotals, MatchResult
from src.main import create_app
from src.routes.analyze import get_photo_analysis_service
from src.services.photo_analysis import LLMError, LLMTimeoutError
from src.utils.image import TranscodeError

_DUMMY_USER = CurrentUser(user_id="test-user-id")

_FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"
_JPEG_BYTES = (_FIXTURE_DIR / "test_food.jpg").read_bytes()

# Minimal 1x1 PNG
import struct, zlib

def _make_png() -> bytes:
    def chunk(name, data):
        c = name + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")

_PNG_BYTES = _make_png()

_EMPTY_RESULT = MatchResult(items=[], totals=MacroTotals(), degraded=False)


def _make_app(service=None):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _DUMMY_USER
    if service is not None:
        app.dependency_overrides[get_photo_analysis_service] = lambda: service
    return app


def _mock_service(result=_EMPTY_RESULT, side_effect=None):
    svc = MagicMock()
    if side_effect:
        svc.analyze = AsyncMock(side_effect=side_effect)
    else:
        svc.analyze = AsyncMock(return_value=result)
    return svc


def test_analyze_rejects_unsupported_mime():
    app = _make_app(_mock_service())
    with patch("src.routes.analyze.sniff_mime", return_value="text/plain"):
        with TestClient(app) as client:
            resp = client.post(
                "/api/analyze",
                files={"image": ("photo.txt", b"hello", "text/plain")},
            )
    assert resp.status_code == 415


def test_analyze_accepts_jpeg():
    app = _make_app(_mock_service())
    with patch("src.routes.analyze.sniff_mime", return_value="image/jpeg"):
        with TestClient(app) as client:
            resp = client.post(
                "/api/analyze",
                files={"image": ("photo.jpg", _JPEG_BYTES, "image/jpeg")},
            )
    assert resp.status_code == 200


def test_analyze_accepts_png():
    app = _make_app(_mock_service())
    with patch("src.routes.analyze.sniff_mime", return_value="image/png"):
        with TestClient(app) as client:
            resp = client.post(
                "/api/analyze",
                files={"image": ("photo.png", _PNG_BYTES, "image/png")},
            )
    assert resp.status_code == 200


def test_analyze_accepts_heic():
    app = _make_app(_mock_service())
    with patch("src.routes.analyze.sniff_mime", return_value="image/heic"):
        with TestClient(app) as client:
            resp = client.post(
                "/api/analyze",
                files={"image": ("photo.heic", b"fake-heic", "image/heic")},
            )
    assert resp.status_code == 200


def test_analyze_rejects_oversized():
    app = _make_app(_mock_service())
    big_data = b"\xff\xd8\xff" + b"\x00" * (4 * 1024 * 1024 + 1)
    with patch("src.routes.analyze.sniff_mime", return_value="image/jpeg"):
        with TestClient(app) as client:
            resp = client.post(
                "/api/analyze",
                files={"image": ("big.jpg", big_data, "image/jpeg")},
            )
    assert resp.status_code == 413


def test_analyze_happy_path_returns_match_result():
    from src.domain.food import MacrosPer100g, MatchedFood

    items = [
        MatchedFood(
            query_name="apple",
            grams=100.0,
            source="supabase",
            matched_name="apple",
            score=95.0,
            macros_per_100g=MacrosPer100g(calories=52.0, protein=0.3, carbs=14.0, fat=0.2),
            macros_actual=MacroTotals(calories=52.0, protein=0.3, carbs=14.0, fat=0.2),
            low_confidence=False,
        )
    ]
    result = MatchResult(
        items=items,
        totals=MacroTotals(calories=52.0, protein=0.3, carbs=14.0, fat=0.2),
        degraded=False,
    )
    app = _make_app(_mock_service(result=result))
    with patch("src.routes.analyze.sniff_mime", return_value="image/jpeg"):
        with TestClient(app) as client:
            resp = client.post(
                "/api/analyze",
                files={"image": ("photo.jpg", _JPEG_BYTES, "image/jpeg")},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["query_name"] == "apple"


def test_analyze_transcode_error_returns_422():
    app = _make_app(_mock_service(side_effect=TranscodeError("bad file")))
    with patch("src.routes.analyze.sniff_mime", return_value="image/jpeg"):
        with TestClient(app) as client:
            resp = client.post(
                "/api/analyze",
                files={"image": ("photo.jpg", _JPEG_BYTES, "image/jpeg")},
            )
    assert resp.status_code == 422


def test_analyze_llm_timeout_returns_504():
    app = _make_app(_mock_service(side_effect=LLMTimeoutError()))
    with patch("src.routes.analyze.sniff_mime", return_value="image/jpeg"):
        with TestClient(app) as client:
            resp = client.post(
                "/api/analyze",
                files={"image": ("photo.jpg", _JPEG_BYTES, "image/jpeg")},
            )
    assert resp.status_code == 504


def test_analyze_llm_error_returns_502():
    app = _make_app(_mock_service(side_effect=LLMError("model failure")))
    with patch("src.routes.analyze.sniff_mime", return_value="image/jpeg"):
        with TestClient(app) as client:
            resp = client.post(
                "/api/analyze",
                files={"image": ("photo.jpg", _JPEG_BYTES, "image/jpeg")},
            )
    assert resp.status_code == 502


def test_analyze_requires_auth():
    app = create_app()  # no auth override
    with TestClient(app) as client:
        resp = client.post(
            "/api/analyze",
            files={"image": ("photo.jpg", _JPEG_BYTES, "image/jpeg")},
        )
    assert resp.status_code == 401
