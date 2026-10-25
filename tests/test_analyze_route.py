"""Tests for POST /api/analyze route."""

import logging
import pathlib
import struct
import zlib
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


def test_analyze_compresses_oversized_image():
    from unittest.mock import patch as _patch

    app = _make_app(_mock_service())
    big_data = b"\xff\xd8\xff" + b"\x00" * (4 * 1024 * 1024 + 1)
    compressed = b"\xff\xd8\xff" + b"\x00" * 100  # simulate compressed result
    with patch("src.routes.analyze.sniff_mime", return_value="image/jpeg"):
        with _patch(
            "src.routes.analyze.compress_to_limit", return_value=compressed
        ) as mock_compress:
            with TestClient(app) as client:
                resp = client.post(
                    "/api/analyze",
                    files={"image": ("big.jpg", big_data, "image/jpeg")},
                )
    mock_compress.assert_called_once()
    assert resp.status_code == 200


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


def _post_with_context(svc, meal_context=None):
    app = _make_app(svc)
    data = {} if meal_context is None else {"meal_context": meal_context}
    with patch("src.routes.analyze.sniff_mime", return_value="image/jpeg"):
        with TestClient(app) as client:
            return client.post(
                "/api/analyze",
                files={"image": ("photo.jpg", _JPEG_BYTES, "image/jpeg")},
                data=data,
            )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  200g rice  ", "200g rice"),
        ("", None),
        ("   \n\t ", None),
        ("\x00\x07\x1b", None),
        ("rice\x00 and beans", "rice and beans"),
        ("a" * 150, "a" * 150),
        ("a" * 151, "a" * 150),
        ("a" * 300, "a" * 150),
        (None, None),
    ],
)
def test_analyze_normalizes_meal_context(raw, expected):
    svc = _mock_service()
    resp = _post_with_context(svc, raw)
    assert resp.status_code == 200
    assert svc.analyze.call_args.kwargs["meal_context"] == expected


def _analyze_request_record(caplog):
    return next(r for r in caplog.records if r.getMessage() == "analyze_request")


def test_analyze_logs_meal_context_length_only(caplog):
    with caplog.at_level(logging.DEBUG):
        _post_with_context(_mock_service(), "200g rice")
    record = _analyze_request_record(caplog)
    assert record.meal_context_length == 9
    assert not any(key.startswith("has_") for key in vars(record))
    for rec in caplog.records:
        assert "200g rice" not in rec.getMessage()
        assert "200g rice" not in str(rec.__dict__)


def test_analyze_logs_zero_length_without_context(caplog):
    with caplog.at_level(logging.DEBUG):
        _post_with_context(_mock_service())
    assert _analyze_request_record(caplog).meal_context_length == 0


def test_analyze_logs_post_truncation_length_and_hides_long_text(caplog):
    marker = "SECRETMARKER" + "x" * 288
    with caplog.at_level(logging.DEBUG):
        _post_with_context(_mock_service(), marker)
    assert _analyze_request_record(caplog).meal_context_length == 150
    for rec in caplog.records:
        assert "SECRETMARKER" not in str(rec.__dict__)
