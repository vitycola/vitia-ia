import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
try:
    from pythonjsonlogger import json as _jsonlogger
except ImportError:
    from pythonjsonlogger import jsonlogger as _jsonlogger  # type: ignore[no-redef]

from src.config import get_settings
from src.routes import food, health
from src.routes import analyze


def _configure_logging() -> None:
    logger = logging.getLogger("vitia")
    if not any(isinstance(h, logging.StreamHandler) and isinstance(getattr(h, "formatter", None), _jsonlogger.JsonFormatter) for h in logger.handlers):
        handler = logging.StreamHandler()
        formatter = _jsonlogger.JsonFormatter(
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

    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router)
    application.include_router(food.router)
    application.include_router(analyze.router)

    return application


app = create_app()
