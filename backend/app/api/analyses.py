"""Analysis endpoints used by the frontend."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analysis import (
    AnalyzeRequest,
    AnalyzeResponse,
    ErrorInfo,
    HistoryPageOut,
    JobDoneOut,
    JobPendingOut,
)
from app.services import analyses
from app.services.capture import get_capture_manager
from app.services.capture.manager import CaptureManager

router = APIRouter(prefix="/api", tags=["analyses"])

DbSession = Annotated[Session, Depends(get_db)]
Captures = Annotated[CaptureManager | None, Depends(get_capture_manager)]
NOT_FOUND = {"code": "not_found", "message": "Bu analiz sonucu bulunamadı. Silinmiş olabilir."}
ERRORS = {
    404: {"description": "Unknown analysis id"},
    422: {"description": "Invalid URL"},
    503: {"description": "Database unavailable"},
}


@router.post("/analyze", status_code=status.HTTP_202_ACCEPTED, response_model=AnalyzeResponse, responses=ERRORS)
def analyze(body: AnalyzeRequest, db: DbSession, captures: Captures) -> AnalyzeResponse:
    try:
        url = analyses.validate_url(body.url)
    except analyses.InvalidUrl as error:
        raise HTTPException(status_code=422, detail={"code": error.code, "message": error.message}) from None

    record = analyses.create_analysis(db, url, captures)
    finished = record.status not in ("pending", "running")
    return AnalyzeResponse(
        id=record.id,
        state="done" if finished else ("queued" if record.status == "pending" else "running"),
        status=record.status,
        error=ErrorInfo(code=record.error_code, message=record.error_message)
        if record.error_code and record.error_message
        else None,
    )


@router.get("/result/{analysis_id}", response_model=JobPendingOut | JobDoneOut, responses=ERRORS)
def get_result(analysis_id: str, db: DbSession) -> JobPendingOut | JobDoneOut:
    record = analyses.get_analysis(db, analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return analyses.to_job(record)


@router.get("/history", response_model=HistoryPageOut, responses=ERRORS)
def history(
    db: DbSession,
    search: Annotated[str, Query(max_length=200)] = "",
    result: Literal["all", "low", "suspicious", "high", "failed"] = "all",
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HistoryPageOut:
    return analyses.list_history(db, search=search, result=result, limit=limit, offset=offset)


@router.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
def delete(analysis_id: str, db: DbSession) -> Response:
    if not analyses.delete_analysis(db, analysis_id):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/captures/{capture_id}/screenshot", response_class=FileResponse, responses=ERRORS)
def screenshot(capture_id: str, db: DbSession) -> FileResponse:
    path = analyses.screenshot_file(db, capture_id)
    if path is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Ekran görüntüsü bulunamadı."})
    return FileResponse(
        path,
        media_type="image/png",
        headers={"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'"},
    )
