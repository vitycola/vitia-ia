import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from pythonjsonlogger.json import (
        JsonFormatter as _JsonFormatter,  # type: ignore[import-not-found]
    )
except ImportError:
    from pythonjsonlogger.jsonlogger import (
        JsonFormatter as _JsonFormatter,  # type: ignore[no-redef,import-not-found]
    )

from src.config import get_settings
from src.routes import analyze, food, health, parse


def _configure_logging() -> None:
    logger = logging.getLogger("vitia")
    already_configured = any(
        isinstance(h, logging.StreamHandler)
        and isinstance(getattr(h, "formatter", None), _JsonFormatter)
        for h in logger.handlers
    )
    if not already_configured:
        handler = logging.StreamHandler()
        formatter = _JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


def create_app(allowed_origins: list[str] | None = None) -> FastAPI:
    _configure_logging()

    settings = get_settings()
    origins = allowed_origins if allowed_origins is not None else settings.allowed_origins

    application = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )

    _raw_regex = settings.allowed_origins_regex or None
    if _raw_regex:
        prefix = "" if _raw_regex.startswith("^") else "^"
        suffix = "" if _raw_regex.endswith("$") else "$"
        origin_regex: str | None = prefix + _raw_regex + suffix
    else:
        origin_regex = None

    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=origin_regex,
        allow_credentials=True,
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    application.include_router(health.router)
    application.include_router(food.router)
    application.include_router(analyze.router)
    application.include_router(parse.router)

    return application


app = create_app()
