"""Shared test setup. The tests never connect to MySQL: the API tests use SQLite."""

import os

# Settings require DB_USER; no connection is opened with it.
os.environ.setdefault("DB_USER", "test")
os.environ["REFERENCE_DOMAINS_FILE"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def client(session_factory):
    def override():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    # Not used as a context manager: the MySQL startup check must not run.
    yield TestClient(app)
    app.dependency_overrides.clear()
