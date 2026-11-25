"""Health endpoints."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db.errors import describe
from app.db.session import ping

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health() -> dict[str, str]:
    """Liveness: the API process is running."""
    return {"status": "ok"}


@router.get("/db", responses={503: {"description": "Database unavailable"}})
def database_health() -> JSONResponse:
    """Readiness: runs SELECT 1 against MySQL.

    Returns 503 with a controlled message when the database is unavailable.
    Credentials and raw driver messages are never included.
    """
    try:
        ping()
    except Exception as error:  # noqa: BLE001 - every failure maps to a controlled 503
        safe = describe(error)
        logger.warning("Database health check failed: %s", safe)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "database": "not_configured" if safe.category == "not_configured" else "unreachable",
                "reason": safe.category,
            },
        )
    return JSONResponse(content={"status": "ok", "database": "reachable"})
