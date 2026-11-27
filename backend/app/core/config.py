"""Environment-based configuration.

Values are read from environment variables first, then from backend/.env.
The password is held as a SecretStr so it never appears in reprs or logs.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"

# Placeholder written to .env.example / the initial .env.
PASSWORD_PLACEHOLDER = "__ENTER_YOUR_PASSWORD__"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    DB_HOST: str = "localhost"
    DB_PORT: int = Field(default=3306, ge=1, le=65535)
    DB_NAME: str = "sahte_site_tespit"
    DB_USER: str
    DB_PASSWORD: SecretStr = SecretStr("")
    DB_CONNECT_TIMEOUT: int = Field(default=5, ge=1, le=60)
    DB_ECHO: bool = False

    # Comma-separated browser origins allowed to call the API (the Vite dev server by default).
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Optional JSON file of reference domains for spelling-similarity comparison
    # (relative paths are resolved against the backend folder). Empty: no comparison.
    REFERENCE_DOMAINS_FILE: str = ""

    # Page capture (headless Chromium). The viewport is fixed in code so captures stay comparable.
    CAPTURE_ENABLED: bool = True
    CAPTURE_STORAGE_DIR: str = "var/captures"  # relative to backend/
    CAPTURE_NAVIGATION_TIMEOUT_S: float = Field(default=20, ge=1, le=120)
    CAPTURE_TOTAL_TIMEOUT_S: float = Field(default=45, ge=5, le=300)
    CAPTURE_SETTLE_MAX_S: float = Field(default=5, ge=0, le=30)
    CAPTURE_MAX_REDIRECTS: int = Field(default=10, ge=0, le=20)
    CAPTURE_MAX_REQUESTS: int = Field(default=250, ge=1, le=2000)
    CAPTURE_MAX_DOWNLOAD_MB: int = Field(default=30, ge=1, le=500)
    CAPTURE_MAX_HTML_MB: int = Field(default=5, ge=1, le=50)
    CAPTURE_MAX_TEXT_CHARS: int = Field(default=500_000, ge=1000, le=5_000_000)
    CAPTURE_MAX_SCREENSHOT_MB: int = Field(default=10, ge=1, le=50)
    CAPTURE_STORAGE_MAX_MB: int = Field(default=1024, ge=1)
    CAPTURE_CONCURRENCY: int = Field(default=2, ge=1, le=8)
    CAPTURE_MAX_PENDING: int = Field(default=10, ge=1, le=100)
    CAPTURE_ALLOWED_PORTS: str = "80,443,8080,8443"

    @property
    def capture_allowed_ports(self) -> frozenset[int]:
        return frozenset(int(port) for port in self.CAPTURE_ALLOWED_PORTS.split(",") if port.strip())

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def password_is_placeholder(self) -> bool:
        return self.DB_PASSWORD.get_secret_value() == PASSWORD_PLACEHOLDER

    @property
    def database_url(self) -> URL:
        """SQLAlchemy URL built from parts.

        URL.create escapes each component, so passwords containing characters
        such as @, #, : or / work without manual quoting. Rendering this
        object with str() masks the password as ***.
        """
        return URL.create(
            drivername="mysql+pymysql",
            username=self.DB_USER,
            password=self.DB_PASSWORD.get_secret_value(),
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
            query={"charset": "utf8mb4"},
        )

    @property
    def safe_target(self) -> str:
        """Human-readable target without user name or password, for messages."""
        return f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
