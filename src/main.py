from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.routes import food, health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


def create_app(allowed_origins: list[str] | None = None) -> FastAPI:
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

    return application


app = create_app()
