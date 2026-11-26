"""Analysis engine boundary.

Only URL-only inspection is implemented. It is deterministic, needs no network
access and runs within the request. Page fetching, the visual, text and DOM
modules and the XGBoost classifier are not implemented, so no risk level,
score or model version is produced anywhere.
"""

from pathlib import Path

from app.core.config import BACKEND_DIR, get_settings
from app.services.url_inspection import UrlInspection, inspect_url

MODULE_NOT_IMPLEMENTED_REASON = "Bu analiz bölümü henüz uygulanmadı; yalnızca adres incelendi."
URL_FAILURE_MESSAGE = "Adres incelenirken beklenmeyen bir sorun oluştu."


def _reference_file() -> Path | None:
    configured = get_settings().REFERENCE_DOMAINS_FILE.strip()
    if not configured:
        return None
    path = Path(configured)
    return path if path.is_absolute() else BACKEND_DIR / path


def run_url_inspection(url: str) -> UrlInspection:
    return inspect_url(url, _reference_file())
