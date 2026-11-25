"""Turn database exceptions into safe, credential-free messages.

Raw driver errors can contain the user name and host. These helpers return
a category and a short explanation instead of the original text.
"""

from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

# MySQL / PyMySQL client error codes
_MESSAGES: dict[int, tuple[str, str]] = {
    1044: ("access_denied", "The user has no access to this database."),
    1045: ("access_denied", "Access denied: check DB_USER and DB_PASSWORD."),
    1005: ("schema_mismatch", "An existing table does not match the models, so a foreign key could not be created (for example a different column type or collation). Existing tables are not changed automatically; reconcile them with an Alembic migration."),
    1049: ("unknown_database", "The database named in DB_NAME does not exist."),
    1142: ("access_denied", "The database user lacks permission for this operation (e.g. CREATE)."),
    1215: ("schema_mismatch", "An existing table does not match the models, so a foreign key could not be created (for example a different column type or collation). Existing tables are not changed automatically; reconcile them with an Alembic migration."),
    2003: ("unreachable", "Cannot reach the MySQL server: check DB_HOST, DB_PORT and that the service is running."),
    2005: ("unknown_host", "Unknown MySQL host: check DB_HOST."),
    2013: ("connection_lost", "The connection was lost or timed out during the handshake."),
    3780: ("schema_mismatch", "An existing table does not match the models, so a foreign key could not be created (for example a different column type or collation). Existing tables are not changed automatically; reconcile them with an Alembic migration."),
}


class DatabaseNotConfigured(RuntimeError):
    """backend/.env still contains the placeholder password."""


@dataclass(frozen=True)
class SafeDbError:
    category: str
    message: str
    code: int | None = None

    def __str__(self) -> str:
        suffix = f" (MySQL error {self.code})" if self.code else ""
        return f"{self.message}{suffix}"


def describe(error: BaseException) -> SafeDbError:
    if isinstance(error, DatabaseNotConfigured):
        return SafeDbError("not_configured", "DB_PASSWORD in backend/.env still contains the placeholder.")

    if isinstance(error, ValidationError):
        fields = ", ".join(str(item["loc"][0]) for item in error.errors() if item.get("loc"))
        return SafeDbError("configuration", f"Invalid or missing settings in backend/.env: {fields}.")

    if isinstance(error, DBAPIError) and error.orig is not None and error.orig.args:
        code = error.orig.args[0]
        if isinstance(code, int):
            category, message = _MESSAGES.get(code, ("database_error", "The database returned an error."))
            return SafeDbError(category, message, code)

    if isinstance(error, SQLAlchemyError):
        return SafeDbError("database_error", f"Database error ({type(error).__name__}).")

    return SafeDbError("unexpected", f"Unexpected error ({type(error).__name__}).")
