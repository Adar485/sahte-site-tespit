"""Analysis records: creation, retrieval, history and the DB -> API mapping."""

import ipaddress
import logging
import re
from datetime import timedelta
from urllib.parse import urlsplit

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.base import utcnow
from app.models import Analysis, AnalysisModule, AnalysisStatus, FailureCode, ModuleName
from app.schemas.analysis import (
    AnalysisStage,
    FailureOut,
    HistoryCounts,
    HistoryEntryOut,
    HistoryPageOut,
    JobDoneOut,
    JobPendingOut,
    ModuleOut,
    ResultOut,
    RiskOut,
)
from app.services import engine

logger = logging.getLogger(__name__)

MAX_URL_LENGTH = 2048
# A pending/running record older than this is treated as timed out, so no
# record can stay "running" forever (for example after a crash).
STALE_AFTER = timedelta(minutes=30)
RESULT_FILTERS = ("all", "low", "suspicious", "high", "failed")


class InvalidUrl(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_DOMAIN = re.compile(r"^(?!-)[\w-]+(\.[\w-]+)*\.([^\W\d_]{2,}|xn--[a-z0-9-]+)\.?$", re.IGNORECASE)


def validate_url(raw: str) -> str:
    """Server-side counterpart of frontend/src/lib/url.ts (the frontend normalises first)."""
    value = raw.strip()
    if not value:
        raise InvalidUrl("empty", "İncelemek istediğiniz web adresini yazın.")
    if len(value) > MAX_URL_LENGTH:
        raise InvalidUrl("too_long", "Bu adres çok uzun. En fazla 2048 karakterlik adresler incelenebilir.")
    if re.search(r"\s", value):
        raise InvalidUrl("whitespace", "Adres boşluk içeremez.")
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
    except ValueError:
        raise InvalidUrl("malformed", "Bu bir web adresine benzemiyor.") from None
    if parts.scheme.lower() not in ("http", "https"):
        raise InvalidUrl(
            "unsupported_scheme", "Yalnızca http:// veya https:// ile başlayan web adresleri incelenebilir."
        )
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        is_ip = False
    if not host or (not is_ip and not _DOMAIN.match(host)):
        raise InvalidUrl("invalid_host", "Alan adı eksik ya da hatalı görünüyor.")
    return value


# --------------------------------------------------------------------------- #
# Create / read / delete
# --------------------------------------------------------------------------- #


def create_analysis(db: Session, url: str) -> Analysis:
    """Record the request and hand it to the engine.

    While the engine is unavailable the record is stored as failed in the same
    transaction, so it is never left pending.
    """
    started = utcnow()
    analysis = Analysis(submitted_url=url, status=AnalysisStatus.PENDING.value, created_at=started)
    db.add(analysis)
    db.flush()

    try:
        engine.submit(analysis.id, url)
    except engine.AnalysisEngineUnavailable as error:
        finished = utcnow()
        analysis.status = AnalysisStatus.FAILED.value
        analysis.error_code = FailureCode.SERVICE_UNAVAILABLE.value
        analysis.error_message = str(error)
        analysis.completed_at = finished
        analysis.duration_ms = int((finished - started).total_seconds() * 1000)
        logger.info("Analysis %s recorded as failed: analysis engine unavailable.", analysis.id)

    db.commit()
    return analysis


def get_analysis(db: Session, analysis_id: str) -> Analysis | None:
    analysis = db.execute(
        select(Analysis).options(selectinload(Analysis.modules)).where(Analysis.id == analysis_id)
    ).scalar_one_or_none()
    if analysis is not None:
        _expire_if_stale(db, analysis)
    return analysis


def _expire_if_stale(db: Session, analysis: Analysis) -> None:
    if analysis.status not in (AnalysisStatus.PENDING.value, AnalysisStatus.RUNNING.value):
        return
    if utcnow() - analysis.created_at < STALE_AFTER:
        return
    analysis.status = AnalysisStatus.FAILED.value
    analysis.risk_level = None
    analysis.risk_score = None
    analysis.error_code = FailureCode.TIMEOUT.value
    analysis.error_message = "Analiz belirlenen süre içinde tamamlanmadı."
    analysis.completed_at = utcnow()
    db.commit()
    logger.warning("Analysis %s was still %s after %s; marked as timed out.", analysis.id, "pending/running", STALE_AFTER)


def delete_analysis(db: Session, analysis_id: str) -> bool:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        return False
    db.delete(analysis)
    db.commit()
    return True


# --------------------------------------------------------------------------- #
# DB -> API mapping
# --------------------------------------------------------------------------- #

_FAILURE_STAGE: dict[str, AnalysisStage] = {
    FailureCode.SERVICE_UNAVAILABLE.value: "url_check",
    FailureCode.UNREACHABLE.value: "page_fetch",
    FailureCode.TIMEOUT.value: "page_fetch",
    FailureCode.UNKNOWN.value: "scoring",
}
_DEFAULT_FAILURE_MESSAGE = "Analiz tamamlanamadı."
_MISSING_MODULE_REASON = "Bu bölüm için kayıtlı bir sonuç yok."


def _module_out(key: str, row: AnalysisModule | None) -> ModuleOut:
    if row is None:
        # Never invent module content: a missing row is reported as not run.
        return ModuleOut(key=key, status="skipped", summary="Sonuç yok.", unavailable_reason=_MISSING_MODULE_REASON)
    return ModuleOut(
        key=key,
        status=row.status,
        summary=row.summary or "",
        unavailable_reason=row.error_message,
        findings=row.findings or [],
        data=row.features,
        duration_ms=row.duration_ms,
    )


def to_result(analysis: Analysis) -> ResultOut:
    risk = None
    if analysis.risk_level is not None and analysis.status in (
        AnalysisStatus.COMPLETED.value,
        AnalysisStatus.PARTIAL.value,
    ):
        risk = RiskOut(level=analysis.risk_level, score=analysis.risk_score)

    failure = None
    if analysis.status == AnalysisStatus.FAILED.value:
        code = analysis.error_code or FailureCode.UNKNOWN.value
        failure = FailureOut(
            code=code,
            message=analysis.error_message or _DEFAULT_FAILURE_MESSAGE,
            stage=_FAILURE_STAGE.get(code, "scoring"),
        )

    rows = {row.module: row for row in analysis.modules}
    return ResultOut(
        id=analysis.id,
        submitted_url=analysis.submitted_url,
        final_url=analysis.final_url,
        requested_at=analysis.created_at,
        completed_at=analysis.completed_at,
        duration_ms=analysis.duration_ms,
        status=analysis.status,
        risk=risk,
        failure=failure,
        modules={name.value: _module_out(name.value, rows.get(name.value)) for name in ModuleName},
        analysis_mode=analysis.analysis_mode,
        model_version=analysis.model_version,
    )


def to_job(analysis: Analysis) -> JobPendingOut | JobDoneOut:
    if analysis.status == AnalysisStatus.PENDING.value:
        return JobPendingOut(id=analysis.id, state="queued", stage="url_check", submitted_url=analysis.submitted_url)
    if analysis.status == AnalysisStatus.RUNNING.value:
        # No stage column yet; the future engine can add one.
        return JobPendingOut(id=analysis.id, state="running", stage="url_check", submitted_url=analysis.submitted_url)
    return JobDoneOut(id=analysis.id, state="done", result=to_result(analysis))


# --------------------------------------------------------------------------- #
# History
# --------------------------------------------------------------------------- #


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_history(db: Session, search: str, result: str, limit: int, offset: int) -> HistoryPageOut:
    conditions = []
    term = search.strip()
    if term:
        pattern = f"%{_escape_like(term)}%"
        conditions.append(
            or_(
                Analysis.submitted_url.like(pattern, escape="\\"),
                Analysis.final_url.like(pattern, escape="\\"),
            )
        )

    def count_if(condition):  # type: ignore[no-untyped-def]
        return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)

    row = db.execute(
        select(
            func.count(),
            count_if(Analysis.risk_level == "low"),
            count_if(Analysis.risk_level == "suspicious"),
            count_if(Analysis.risk_level == "high"),
            count_if(Analysis.status == AnalysisStatus.FAILED.value),
        ).where(*conditions)
    ).one()
    counts = HistoryCounts(all=row[0], low=row[1], suspicious=row[2], high=row[3], failed=row[4])

    if result in ("low", "suspicious", "high"):
        conditions.append(Analysis.risk_level == result)
    elif result == "failed":
        conditions.append(Analysis.status == AnalysisStatus.FAILED.value)

    records = db.execute(
        select(Analysis)
        .where(*conditions)
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .limit(limit)
        .offset(offset)
    ).scalars()

    items = [
        HistoryEntryOut(
            id=record.id,
            submitted_url=record.submitted_url,
            final_url=record.final_url,
            analyzed_at=record.completed_at or record.created_at,
            status=record.status,
            risk_level=record.risk_level,
        )
        for record in records
    ]
    return HistoryPageOut(items=items, total=getattr(counts, result), counts=counts)
