"""FastAPI application entry point.

Run from the backend directory:
    python -m uvicorn app.main:app --reload --port 8000
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.api import analyses, health
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.errors import describe
from app.db.init import initialize_database
from app.db.session import get_engine

setup_logging()
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Startup: check the connection and create missing tables before serving
    # requests. A DatabaseInitializationError aborts startup.
    await run_in_threadpool(initialize_database)
    yield
    # Shutdown: close pooled connections.
    get_engine().dispose()


app = FastAPI(
    title="Sahte Site Avcıları API",
    version="0.2.0",
    description="Phishing risk analysis backend. The analysis engine is not available yet.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Accept", "Content-Type"],
)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_: Request, error: SQLAlchemyError) -> JSONResponse:
    # Driver messages may contain user and host names; respond with a fixed message.
    logger.error("Database error while handling a request: %s", describe(error))
    return JSONResponse(
        status_code=503,
        content={"detail": {"code": "database_unavailable", "message": "Veritabanına şu anda ulaşılamıyor."}},
    )


app.include_router(health.router)
app.include_router(analyses.router)
