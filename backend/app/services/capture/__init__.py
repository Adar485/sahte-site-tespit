"""Page capture with headless Chromium. See backend/README.md for protections and limits."""

from functools import lru_cache
from pathlib import Path

from app.core.config import BACKEND_DIR, get_settings
from app.db.session import get_session_factory
from app.services.capture.browser import CaptureConfig
from app.services.capture.manager import CaptureManager
from app.services.capture.network import NetworkPolicy
from app.services.capture.storage import ArtifactStore

_MB = 1024 * 1024


def artifact_store() -> ArtifactStore:
    settings = get_settings()
    root = Path(settings.CAPTURE_STORAGE_DIR)
    root = (root if root.is_absolute() else BACKEND_DIR / root).resolve()
    if root.is_relative_to((BACKEND_DIR.parent / "frontend").resolve()):
        raise ValueError("CAPTURE_STORAGE_DIR must not be inside the frontend folder.")
    return ArtifactStore(root, settings.CAPTURE_STORAGE_MAX_MB * _MB)


@lru_cache
def _manager() -> CaptureManager:
    settings = get_settings()
    return CaptureManager(
        session_factory=lambda: get_session_factory()(),
        store=artifact_store(),
        config=CaptureConfig(
            navigation_timeout_s=settings.CAPTURE_NAVIGATION_TIMEOUT_S,
            total_timeout_s=settings.CAPTURE_TOTAL_TIMEOUT_S,
            settle_max_s=settings.CAPTURE_SETTLE_MAX_S,
            max_redirects=settings.CAPTURE_MAX_REDIRECTS,
            max_requests=settings.CAPTURE_MAX_REQUESTS,
            max_download_bytes=settings.CAPTURE_MAX_DOWNLOAD_MB * _MB,
            max_html_bytes=settings.CAPTURE_MAX_HTML_MB * _MB,
            max_text_chars=settings.CAPTURE_MAX_TEXT_CHARS,
            max_screenshot_bytes=settings.CAPTURE_MAX_SCREENSHOT_MB * _MB,
        ),
        policy=NetworkPolicy(allowed_ports=settings.capture_allowed_ports),
        concurrency=settings.CAPTURE_CONCURRENCY,
        max_pending=settings.CAPTURE_MAX_PENDING,
    )


def get_capture_manager() -> CaptureManager | None:
    """FastAPI dependency. None when capture is switched off."""
    return _manager() if get_settings().CAPTURE_ENABLED else None


def shutdown_capture_manager() -> None:
    if _manager.cache_info().currsize:
        _manager().shutdown()
        _manager.cache_clear()
