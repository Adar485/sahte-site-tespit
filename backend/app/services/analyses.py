"""Analysis records: creation, retrieval, history and the DB -> API mapping."""

import logging
import time
from datetime import timedelta

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.base import utcnow
from app.models import (
    Analysis,
    AnalysisMode,
    AnalysisModule,
    AnalysisStatus,
    CaptureStatus,
    FailureCode,
    ModuleName,
    ModuleStatus,
    PageCapture,
)
from app.schemas.analysis import (
    AnalysisStage,
    CaptureArtifactsOut,
    CaptureOut,
    ErrorInfo,
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
from app.services.capture import artifact_store
from app.services.capture.manager import CaptureManager, fail_capture, finish_analysis, new_capture
from app.services.url_inspection import InvalidUrl, parse_url

logger = logging.getLogger(__name__)

# A pending/running record older than this is treated as timed out, so no
# record can stay "running" forever (for example after a crash).
STALE_AFTER = timedelta(minutes=30)
RESULT_FILTERS = ("all", "low", "suspicious", "high", "failed")
TEXT_PREVIEW_CHARS = 2000


def validate_url(raw: str) -> str:
    """Accept or reject a submission with the same parser the inspector uses.

    Returns the trimmed input, which is what analyses.submitted_url stores.
    The normalised form is kept in the URL module's data.
    """
    return parse_url(raw).submitted


# --------------------------------------------------------------------------- #
# Create / read / delete
# --------------------------------------------------------------------------- #


def create_analysis(db: Session, url: str, capture_manager: CaptureManager | None = None) -> Analysis:
    """Run URL inspection, store it, and queue the page capture.

    The record with its module rows (and pending capture) is written in one commit.
    With a capture it stays "running" until the capture ends; the final state is
    "partial" with no risk level, whether or not the page could be captured,
    because this is not a phishing assessment.
    """
    clock = time.perf_counter()
    analysis = Analysis(submitted_url=url, created_at=utcnow(), analysis_mode=AnalysisMode.URL_ONLY.value)

    try:
        inspection = engine.run_url_inspection(url)
    except Exception as error:  # noqa: BLE001 - stored and reported with a fixed message
        # Only the type is logged: messages may repeat parts of the submitted address.
        logger.error("URL inspection failed (%s).", type(error).__name__)
        url_module = AnalysisModule(
            module=ModuleName.URL.value,
            status=ModuleStatus.FAILED.value,
            summary="Adres incelenemedi.",
            findings=[],
            error_message=engine.URL_FAILURE_MESSAGE,
        )
        analysis.status = AnalysisStatus.FAILED.value
        analysis.error_code = FailureCode.UNKNOWN.value
        analysis.error_message = engine.URL_FAILURE_MESSAGE
    else:
        url_module = AnalysisModule(
            module=ModuleName.URL.value,
            status=ModuleStatus.COMPLETED.value,
            summary=inspection.summary,
            findings=inspection.findings,
            features=inspection.data,
        )
        analysis.status = AnalysisStatus.PARTIAL.value

    elapsed_ms = round((time.perf_counter() - clock) * 1000)
    url_module.duration_ms = elapsed_ms
    analysis.modules = [url_module] + [
        AnalysisModule(
            module=name.value,
            status=ModuleStatus.SKIPPED.value,
            summary="Çalıştırılmadı.",
            findings=[],
            error_message=engine.MODULE_NOT_IMPLEMENTED_REASON,
        )
        for name in ModuleName
        if name is not ModuleName.URL
    ]
    capture = None
    if capture_manager is not None and analysis.status == AnalysisStatus.PARTIAL.value:
        capture = new_capture(url_module.features["address"]["normalizedUrl"])
        analysis.capture = capture
        analysis.status = AnalysisStatus.RUNNING.value
    else:
        analysis.completed_at = utcnow()
        analysis.duration_ms = elapsed_ms

    db.add(analysis)
    db.commit()

    if capture is not None and not capture_manager.submit(capture.id):
        fail_capture(capture, "busy")
        finish_analysis(analysis)
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
    if analysis.capture is not None:
        # The URL results exist; only the capture is lost.
        if analysis.capture.status in (CaptureStatus.PENDING.value, CaptureStatus.RUNNING.value):
            fail_capture(analysis.capture, "interrupted")
        finish_analysis(analysis)
        db.commit()
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
    had_capture = analysis.capture is not None
    db.delete(analysis)
    db.commit()
    if had_capture:
        artifact_store().delete_analysis(analysis_id)
    return True


def screenshot_file(db: Session, capture_id: str):  # type: ignore[no-untyped-def]
    """The stored screenshot of a known capture, or None. No path comes from the client."""
    capture = db.get(PageCapture, capture_id)
    if capture is None or not capture.has_screenshot:
        return None
    return artifact_store().resolve(capture.screenshot_path)


def _capture_out(capture: PageCapture | None) -> CaptureOut | None:
    if capture is None:
        return None
    store = artifact_store()
    details = capture.details or {}
    # A flag is reported only while the file is really there.
    screenshot = capture.has_screenshot and store.resolve(capture.screenshot_path) is not None
    html = capture.has_html and store.resolve(capture.html_path) is not None
    text_file = store.resolve(capture.text_path) if capture.has_text else None
    preview = None
    if text_file is not None:
        with text_file.open(encoding="utf-8", errors="replace") as handle:
            preview = handle.read(TEXT_PREVIEW_CHARS)
    return CaptureOut(
        id=capture.id,
        status=capture.status,
        requested_url=capture.requested_url,
        final_url=capture.final_url,
        http_status=capture.http_status,
        requested_at=capture.requested_at,
        completed_at=capture.completed_at,
        duration_ms=capture.duration_ms,
        viewport_width=capture.viewport_width,
        viewport_height=capture.viewport_height,
        artifacts=CaptureArtifactsOut(screenshot=screenshot, html=html, text=text_file is not None),
        screenshot_url=f"/api/captures/{capture.id}/screenshot" if screenshot else None,
        text_preview=preview,
        text_length=capture.text_length,
        redirected=len(details.get("redirectChain", [])) > 1,
        consistent=details.get("consistent"),
        page_title=details.get("title"),
        signals=details.get("signals"),
        error=ErrorInfo(code=capture.error_code, message=capture.error_message)
        if capture.error_code and capture.error_message
        else None,
        capture_version=capture.capture_version,
    )


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
    url_row = rows.get(ModuleName.URL.value)
    if failure and url_row is not None and url_row.status == ModuleStatus.FAILED.value:
        failure.stage = "url_check"
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
        capture=_capture_out(analysis.capture),
    )


def to_job(analysis: Analysis) -> JobPendingOut | JobDoneOut:
    if analysis.status == AnalysisStatus.PENDING.value:
        return JobPendingOut(id=analysis.id, state="queued", stage="url_check", submitted_url=analysis.submitted_url)
    if analysis.status == AnalysisStatus.RUNNING.value:
        stage = "page_fetch" if analysis.capture is not None else "url_check"
        return JobPendingOut(id=analysis.id, state="running", stage=stage, submitted_url=analysis.submitted_url)
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
