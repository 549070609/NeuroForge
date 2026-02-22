"""Health check routes."""

from fastapi import APIRouter

from ...schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        Health status
    """
    return HealthResponse()


@router.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Service Layer", "docs": "/docs"}
