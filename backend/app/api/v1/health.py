"""Health check endpoint."""

from fastapi import APIRouter, status

from app import __version__
from app.core.config import settings
from app.domain.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=settings.app_env,
    )
