"""Engine, session factory and the per-request session dependency."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.errors import DatabaseNotConfigured


@lru_cache
def get_engine() -> Engine:
    """Create the engine lazily so importing the app never needs a live database."""
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,  # detect connections dropped by MySQL (wait_timeout)
        pool_recycle=1800,  # recycle before MySQL's default 8 h idle timeout
        pool_size=5,
        max_overflow=10,
        pool_timeout=10,
        echo=settings.DB_ECHO,
        hide_parameters=True,  # never include bound values in error messages
        connect_args={
            "charset": "utf8mb4",
            "connect_timeout": settings.DB_CONNECT_TIMEOUT,
            "read_timeout": 30,
            "write_timeout": 30,
            # Store and compare all timestamps in UTC regardless of server time zone.
            "init_command": "SET time_zone = '+00:00'",
        },
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request.

    Endpoints commit explicitly. Any exception rolls the transaction back,
    and the session is always closed.
    """
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ping() -> None:
    """Run SELECT 1. Raises the underlying SQLAlchemy error on failure."""
    if get_settings().password_is_placeholder:
        raise DatabaseNotConfigured()
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1")).scalar_one()
