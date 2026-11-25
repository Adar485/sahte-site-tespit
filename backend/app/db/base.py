"""Declarative base and shared column types."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, MetaData
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

# Deterministic constraint names keep Alembic migrations stable.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware datetimes stored as UTC in a MySQL DATETIME(6).

    MySQL DATETIME has no time zone. Values are converted to UTC before
    writing and returned as aware UTC datetimes when read. Naive datetimes
    are rejected so local time can never be stored by mistake.
    """

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[no-untyped-def]
        if dialect.name == "mysql":
            return dialect.type_descriptor(mysql.DATETIME(fsp=6))
        return dialect.type_descriptor(DateTime())

    def process_bind_param(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetime given; use an aware UTC datetime.")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)
