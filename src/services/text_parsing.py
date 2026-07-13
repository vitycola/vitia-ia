import logging
import time

from src.adapters.llm_adapter import LLMAdapter
from src.domain.food import MacroTotals, MatchResult, MatchedFood
from src.services.errors import LLMError, LLMTimeoutError
from src.services.food_matcher import FoodMatcherService

logger = logging.getLogger("vitia.parse")


def _sum_totals(items: list[MatchedFood]) -> MacroTotals:
    return MacroTotals(
        calories=sum(i.macros_actual.calories for i in items),
        protein=sum(i.macros_actual.protein for i in items),
        carbs=sum(i.macros_actual.carbs for i in items),
        fat=sum(i.macros_actual.fat for i in items),
    )


class TextParsingService:
    def __init__(self, llm: LLMAdapter, matcher: FoodMatcherService) -> None:
        self.llm = llm
        self.matcher = matcher

    async def parse(self, text: str, correlation_id: str) -> MatchResult:
        logger.info("parse_text_start", extra={"correlation_id": correlation_id})

        t0 = time.monotonic()
        try:
            foods = await self.llm.parse_text(text)
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
            "parse_text_llm_end",
            extra={
                "correlation_id": correlation_id,
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "foods_identified": len(foods.items),
            },
        )

        t0 = time.monotonic()
        logger.info("parse_text_matcher_start", extra={"correlation_id": correlation_id})
        raw_result = await self.matcher.match_all(foods)
        if not foods.items:
            raw_result.degraded = True

        matched = [i for i in raw_result.items if i.source != "unmatched"]
        unmatched = [i for i in raw_result.items if i.source == "unmatched"]

        logger.info(
            "parse_text_matcher_end",
            extra={
                "correlation_id": correlation_id,
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "matched_count": len(matched),
                "unmatched_count": len(unmatched),
                "degraded": raw_result.degraded,
            },
        )

        skipped = [f.query_name for f in unmatched]
        totals = _sum_totals(matched)

        result = MatchResult(
            items=matched,
            totals=totals,
            degraded=raw_result.degraded,
            skipped=skipped,
        )

        logger.info(
            "parse_text_response",
            extra={
                "correlation_id": correlation_id,
                "items_count": len(matched),
                "skipped_count": len(skipped),
                "calories": totals.calories,
            },
        )

        return result
