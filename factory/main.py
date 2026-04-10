"""Forge Factory — FastAPI entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from factory.api import api_router
from factory.config import get_settings
from factory.database import close_engine, init_engine

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise and tear down shared infrastructure."""
    settings = get_settings()
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            __import__("logging").getLevelName(settings.log_level)
        ),
    )
    init_engine()
    logger.info("forge_factory_startup", environment=settings.environment)
    yield
    await close_engine()
    logger.info("forge_factory_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Forge Factory API",
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    @app.get("/", tags=["meta"])
    async def root() -> dict[str, str]:
        return {"service": "forge-factory", "docs": "/docs"}

    @app.exception_handler(Exception)
    async def unhandled_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", exc=str(exc))
        return JSONResponse(status_code=500, content={"error": "internal_error"})

    app.include_router(api_router)
    return app


app = create_app()
