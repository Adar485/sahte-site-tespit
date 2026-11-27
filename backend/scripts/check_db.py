"""Check the MySQL connection without exposing credentials.

Usage (from the backend directory):
    python -m scripts.check_db

Exit code 0 on success, 1 on failure.
"""

import sys

from pydantic import ValidationError
from sqlalchemy import inspect, text

EXPECTED_TABLES = ("analyses", "analysis_modules", "page_captures")


def main() -> int:
    from app.core.config import ENV_FILE, get_settings
    from app.db.errors import describe

    try:
        settings = get_settings()
    except ValidationError as error:
        print(f"[FAIL] {describe(error)}")
        print(f"       Settings file: {ENV_FILE}")
        return 1

    if not ENV_FILE.exists():
        print(f"[WARN] {ENV_FILE} not found; using environment variables and defaults only.")
    if settings.password_is_placeholder:
        print("[FAIL] DB_PASSWORD in backend/.env still contains the placeholder. Enter your MySQL password first.")
        return 1

    print(f"Checking MySQL at {settings.safe_target} ...")

    from app.db.session import get_engine

    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar_one()
            version = connection.execute(text("SELECT VERSION()")).scalar_one()
            charset, collation = connection.execute(
                text(
                    "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
                    "FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = DATABASE()"
                )
            ).one()
            tables = set(inspect(connection).get_table_names())

            print(f"[OK]   SELECT 1 succeeded. MySQL server {version}.")
            print(f"       Database default character set: {charset} / {collation}")
            if charset != "utf8mb4":
                print("[WARN] The database default is not utf8mb4. The migration creates its tables as utf8mb4 explicitly.")

            if "alembic_version" in tables:
                revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
                print(f"       Alembic revision: {revision or 'none'}")
            else:
                print("       Alembic revision: not initialised (run: python -m alembic upgrade head)")

            for name in EXPECTED_TABLES:
                if name in tables:
                    rows = connection.execute(text(f"SELECT COUNT(*) FROM `{name}`")).scalar_one()
                    print(f"       Table {name}: present ({rows} rows)")
                else:
                    print(f"       Table {name}: missing")

            others = sorted(tables - set(EXPECTED_TABLES) - {"alembic_version"})
            if others:
                print(f"       Other tables in this database: {', '.join(others)}")
    except Exception as error:  # noqa: BLE001 - report every failure safely
        print(f"[FAIL] {describe(error)}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
