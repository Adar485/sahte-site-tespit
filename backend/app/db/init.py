"""Database initialisation run at every application startup.

1. Verify the MySQL connection (SELECT 1).
2. Make sure every model is registered on Base.metadata.
3. Create only the application tables that are missing (with their indexes,
   constraints and foreign keys). Existing tables and their data are never
   dropped, recreated or altered.
4. If startup created the whole schema in a database without Alembic history,
   record the current Alembic revision so later migrations start from it.

Structural changes to existing tables are the job of Alembic migrations.
Safe to repeat on every restart or development reload.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Engine, inspect
from sqlalchemy.exc import OperationalError

import app.models  # noqa: F401 - registers analyses and analysis_modules on Base.metadata
from app.core.config import BACKEND_DIR, get_settings
from app.db.base import Base
from app.db.errors import describe
from app.db.session import get_engine, ping

logger = logging.getLogger(__name__)

ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
MYSQL_TABLE_EXISTS = 1050


class DatabaseInitializationError(RuntimeError):
    """Startup could not prepare the database. The message is credential-free."""


@dataclass
class InitReport:
    existing: list[str] = field(default_factory=list)
    created: list[str] = field(default_factory=list)
    alembic_stamped: str | None = None


def _application_tables() -> list[str]:
    names = [table.name for table in Base.metadata.sorted_tables]
    if not names:
        raise DatabaseInitializationError("No models are registered on Base.metadata; check app/models/__init__.py.")
    return names


def _stamp_alembic_head(engine: Engine) -> str | None:
    """Record the head revision when no Alembic history exists yet."""
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    if not Path(ALEMBIC_INI).exists():
        return None
    script = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        if context.get_current_revision() is not None:
            return None
        context.stamp(script, "head")
        return script.get_current_head()


def initialize_database() -> InitReport:
    """Run the startup checks. Raises DatabaseInitializationError on failure."""
    report = InitReport()
    try:
        settings = get_settings()
        ping()  # also refuses to connect while DB_PASSWORD is still the placeholder
        engine = get_engine()
        logger.info("Database connection succeeded (%s).", settings.safe_target)

        expected = _application_tables()
        present = set(inspect(engine).get_table_names())
        report.existing = [name for name in expected if name in present]
        missing = [name for name in expected if name not in present]

        if not missing:
            logger.info("All application tables exist: %s.", ", ".join(expected))
        else:
            logger.info("Missing application tables: %s. Creating them.", ", ".join(missing))
            tables = [Base.metadata.tables[name] for name in missing]
            try:
                Base.metadata.create_all(bind=engine, tables=tables, checkfirst=True)
            except OperationalError as error:
                # Another process (e.g. a second worker) created it first: that is fine.
                if not (error.orig and error.orig.args and error.orig.args[0] == MYSQL_TABLE_EXISTS):
                    raise
            still_missing = [name for name in missing if name not in set(inspect(engine).get_table_names())]
            if still_missing:
                raise DatabaseInitializationError(f"Tables could not be created: {', '.join(still_missing)}.")
            report.created = missing
            logger.info("Created missing tables: %s.", ", ".join(missing))

            if not report.existing:
                report.alembic_stamped = _stamp_alembic_head(engine)
                if report.alembic_stamped:
                    logger.info("Recorded Alembic revision %s for the new schema.", report.alembic_stamped)
            elif "alembic_version" not in present:
                logger.warning(
                    "Some tables existed before this startup and there is no Alembic history. After checking that "
                    "they match the models, run: python -m alembic stamp head"
                )
    except DatabaseInitializationError as error:
        logger.error("Database initialization failed: %s", error)
        raise
    except Exception as error:  # noqa: BLE001 - convert to a sanitized message
        safe = describe(error)
        logger.error("Database initialization failed: %s", safe)
        # "from None" drops the driver exception, whose text may include the user name and host.
        raise DatabaseInitializationError(f"Database initialization failed: {safe}") from None

    logger.info("Database initialization completed.")
    return report

