import base64
import logging
import time

from src.adapters.llm_adapter import LLMAdapter
from src.domain.food import MatchResult
from src.services.food_matcher import FoodMatcherService
from src.utils.image import transcode_heic_to_jpeg

logger = logging.getLogger("vitia.analyze")


class LLMTimeoutError(Exception):
    pass


class LLMError(Exception):
    pass


class PhotoAnalysisService:
    def __init__(self, llm: LLMAdapter, matcher: FoodMatcherService) -> None:
        self.llm = llm
        self.matcher = matcher

    async def analyze(
        self,
        image_bytes: bytes,
        media_type: str,
        meal_context: str | None,
        correlation_id: str,
    ) -> MatchResult:
        if media_type in ("image/heic", "image/heif"):
            t0 = time.monotonic()
            logger.info(
                "transcode_start",
                extra={"correlation_id": correlation_id, "mime_type": media_type},
            )
            image_bytes = transcode_heic_to_jpeg(image_bytes)
            media_type = "image/jpeg"
            logger.info(
                "transcode_end",
                extra={
                    "correlation_id": correlation_id,
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                },
            )

        image_b64 = base64.b64encode(image_bytes).decode()

        t0 = time.monotonic()
        logger.info("llm_start", extra={"correlation_id": correlation_id})
        try:
            foods = await self.llm.analyze_image(image_b64, media_type, context=meal_context)
        except TimeoutError:
            logger.error(
                "llm_error",
                extra={
                    "correlation_id": correlation_id,
                    "stage": "llm",
                    "error_type": "timeout",
                },
            )
            raise LLMTimeoutError() from None
        except Exception as e:
            logger.error(
                "llm_error",
                extra={
                    "correlation_id": correlation_id,
                    "stage": "llm",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
            raise LLMError(str(e)) from e
        logger.info(
            "llm_end",
            extra={
                "correlation_id": correlation_id,
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "foods_identified": len(foods.items),
            },
        )

        t0 = time.monotonic()
        logger.info("matcher_start", extra={"correlation_id": correlation_id})
        result = await self.matcher.match_all(foods)
        if not foods.items:
            result.degraded = True
        matched = sum(1 for i in result.items if i.source != "unmatched")
        unmatched = sum(1 for i in result.items if i.source == "unmatched")
        logger.info(
            "matcher_end",
            extra={
                "correlation_id": correlation_id,
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "matched_count": matched,
                "unmatched_count": unmatched,
                "degraded": result.degraded,
            },
        )

        return result
