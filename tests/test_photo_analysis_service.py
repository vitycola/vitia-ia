"""Tests for PhotoAnalysisService."""

from unittest.mock import AsyncMock, patch

import pytest

from src.domain.food import IdentifiedFoods, MacroTotals, MatchResult
from src.services.photo_analysis import LLMError, LLMTimeoutError, PhotoAnalysisService
from src.utils.image import TranscodeError

FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # minimal JPEG header bytes


def _make_service(llm=None, matcher=None) -> PhotoAnalysisService:
    if llm is None:
        llm = AsyncMock()
        llm.analyze_image = AsyncMock(return_value=IdentifiedFoods(items=[]))
    if matcher is None:
        matcher = AsyncMock()
        matcher.match_all = AsyncMock(
            return_value=MatchResult(items=[], totals=MacroTotals(), degraded=False)
        )
    return PhotoAnalysisService(llm=llm, matcher=matcher)


@pytest.mark.asyncio
async def test_analyze_jpeg_happy_path():
    service = _make_service()
    result = await service.analyze(
        image_bytes=FAKE_JPEG,
        media_type="image/jpeg",
        meal_context=None,
        correlation_id="test-id",
    )
    assert isinstance(result, MatchResult)
    service.llm.analyze_image.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_heic_transcodes_first():
    service = _make_service()
    fake_jpeg = b"\xff\xd8\xff" + b"\x00" * 50

    with patch(
        "src.services.photo_analysis.transcode_heic_to_jpeg", return_value=fake_jpeg
    ) as mock_tc:
        result = await service.analyze(
            image_bytes=b"heic-bytes",
            media_type="image/heic",
            meal_context=None,
            correlation_id="test-id",
        )

    mock_tc.assert_called_once_with(b"heic-bytes")
    assert isinstance(result, MatchResult)
    # Verify jpeg was passed to llm (media_type changed to image/jpeg)
    call_kwargs = service.llm.analyze_image.call_args
    assert call_kwargs.kwargs.get("media_type") == "image/jpeg" or call_args_has_jpeg(call_kwargs)


def call_args_has_jpeg(call_kwargs):
    """Helper: check positional or keyword args for image/jpeg."""
    args = call_kwargs.args if call_kwargs.args else ()
    kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
    return "image/jpeg" in args or kwargs.get("media_type") == "image/jpeg"


@pytest.mark.asyncio
async def test_analyze_transcode_error_propagates():
    service = _make_service()
    with patch(
        "src.services.photo_analysis.transcode_heic_to_jpeg",
        side_effect=TranscodeError("corrupt"),
    ):
        with pytest.raises(TranscodeError):
            await service.analyze(
                image_bytes=b"bad",
                media_type="image/heic",
                meal_context=None,
                correlation_id="test-id",
            )


@pytest.mark.asyncio
async def test_analyze_llm_timeout_raises():
    llm = AsyncMock()
    llm.analyze_image = AsyncMock(side_effect=TimeoutError())
    service = _make_service(llm=llm)
    with pytest.raises(LLMTimeoutError):
        await service.analyze(
            image_bytes=FAKE_JPEG,
            media_type="image/jpeg",
            meal_context=None,
            correlation_id="test-id",
        )


@pytest.mark.asyncio
async def test_analyze_llm_error_raises():
    llm = AsyncMock()
    llm.analyze_image = AsyncMock(side_effect=RuntimeError("network error"))
    service = _make_service(llm=llm)
    with pytest.raises(LLMError):
        await service.analyze(
            image_bytes=FAKE_JPEG,
            media_type="image/jpeg",
            meal_context=None,
            correlation_id="test-id",
        )


@pytest.mark.asyncio
async def test_analyze_empty_foods_returns_degraded_result():
    llm = AsyncMock()
    llm.analyze_image = AsyncMock(return_value=IdentifiedFoods(items=[]))
    matcher = AsyncMock()
    matcher.match_all = AsyncMock(
        return_value=MatchResult(items=[], totals=MacroTotals(), degraded=True)
    )
    service = _make_service(llm=llm, matcher=matcher)
    result = await service.analyze(
        image_bytes=FAKE_JPEG,
        media_type="image/jpeg",
        meal_context=None,
        correlation_id="test-id",
    )
    assert result.degraded is True
    assert result.items == []
