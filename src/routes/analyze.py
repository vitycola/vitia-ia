import logging
import time
import uuid
from collections.abc import AsyncGenerator

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.adapters.factory import get_llm_adapter
from src.adapters.off_client import OFFFallbackClient
from src.adapters.supabase_client import GenericFoodRepository
from src.auth.dependencies import get_current_user
from src.auth.models import CurrentUser
from src.config import MAX_IMAGE_BYTES, get_settings
from src.domain.food import MatchResult
from src.services.food_matcher import FoodMatcherService
from src.services.photo_analysis import LLMError, LLMTimeoutError, PhotoAnalysisService
from src.utils.image import TranscodeError, compress_to_limit

router = APIRouter(prefix="/api", tags=["analyze"])

ALLOWED_MIMES = {"image/jpeg", "image/png", "image/heic", "image/heif"}

logger = logging.getLogger("vitia.analyze")

# python-magic is an optional dependency (requires libmagic system library).
# On platforms where it is unavailable (e.g. Vercel Python runtime), we fall
# back to the client-declared Content-Type.
try:
    import magic as _magic_mod

    _MAGIC_AVAILABLE = True
except (ImportError, OSError):
    _magic_mod = None  # type: ignore[assignment]
    _MAGIC_AVAILABLE = False


def sniff_mime(data: bytes, declared: str | None) -> str:
    """Return the detected MIME type, falling back to the declared one."""
    if _MAGIC_AVAILABLE and _magic_mod is not None:
        try:
            detected = _magic_mod.from_buffer(data, mime=True)
            if detected and detected != "application/octet-stream":
                return detected
        except Exception:
            pass
    return declared or "application/octet-stream"


async def get_photo_analysis_service() -> AsyncGenerator[PhotoAnalysisService, None]:
    settings = get_settings()
    llm = get_llm_adapter(settings)
    async with httpx.AsyncClient() as client:
        repo = GenericFoodRepository(
            client=client,
            base_url=settings.supabase_url,
            anon_key=settings.supabase_anon_key.get_secret_value(),
        )
        off_client = OFFFallbackClient(client=client)
        matcher = FoodMatcherService(repo=repo, off_client=off_client)
        yield PhotoAnalysisService(llm=llm, matcher=matcher)


@router.post("/analyze", response_model=MatchResult)
async def analyze_photo(
    image: UploadFile = File(...),  # noqa: B008
    meal_context: str | None = Form(None),  # noqa: B008
    service: PhotoAnalysisService = Depends(get_photo_analysis_service),  # noqa: B008
    _user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> MatchResult:
    t_start = time.monotonic()
    correlation_id = str(uuid.uuid4())

    data = await image.read()

    logger.info(
        "analyze_request",
        extra={
            "correlation_id": correlation_id,
            "declared_content_type": image.content_type,
            "size_bytes": len(data),
            "has_meal_context": meal_context is not None,
        },
    )

    mime = sniff_mime(data, image.content_type)

    if mime not in ALLOWED_MIMES:
        logger.warning(
            "validation_failed",
            extra={
                "correlation_id": correlation_id,
                "reason": "unsupported_mime",
                "mime_type": mime,
            },
        )
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type: {mime!r}. Allowed: {sorted(ALLOWED_MIMES)}",
        )

    if len(data) > MAX_IMAGE_BYTES:
        logger.info(
            "image_compressing",
            extra={
                "correlation_id": correlation_id,
                "original_size_bytes": len(data),
                "limit_bytes": MAX_IMAGE_BYTES,
            },
        )
        data = compress_to_limit(data, MAX_IMAGE_BYTES)
        logger.info(
            "image_compressed",
            extra={"correlation_id": correlation_id, "compressed_size_bytes": len(data)},
        )

    try:
        result = await service.analyze(
            image_bytes=data,
            media_type=mime,
            meal_context=meal_context,
            correlation_id=correlation_id,
        )
    except TranscodeError as exc:
        logger.error(
            "transcode_error",
            extra={"correlation_id": correlation_id, "error_message": str(exc)},
        )
        raise HTTPException(status_code=422, detail=f"Could not process image: {exc}") from exc
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=504, detail="LLM request timed out. Please try again."
        ) from exc
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc

    logger.info(
        "response_sent",
        extra={
            "correlation_id": correlation_id,
            "total_duration_ms": int((time.monotonic() - t_start) * 1000),
            "status_code": 200,
        },
    )
    return result
