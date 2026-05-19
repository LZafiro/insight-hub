"""FastAPI application entrypoint."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.services.reranker import CrossEncoderReranker

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log.info("app.startup", env=settings.app_env, version=__version__)
    app.state.reranker = CrossEncoderReranker()
    app.state.reranker._load()
    yield
    log.info("app.shutdown")


app = FastAPI(
    title="Insight Hub API",
    version=__version__,
    description="AI-powered research assistant with verifiable citations.",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Attach a correlation id to every request, surface it on the response."""
    correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=correlation_id, path=request.url.path)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = correlation_id
        return response
    finally:
        structlog.contextvars.clear_contextvars()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler. FastAPI's own handlers cover HTTPException etc.;
    this catches anything else so the user sees a clean 500."""
    log.exception("unhandled_exception", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "Insight Hub API", "version": __version__, "docs": "/docs"}
