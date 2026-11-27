"""API response/request schemas.

Field names are camelCase on the wire to match frontend/src/types/analysis.ts.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

AnalysisStage = Literal["url_check", "page_fetch", "content_inspection", "scoring"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AnalyzeRequest(BaseModel):
    url: str = Field(description="http(s) URL or bare domain (https:// is assumed), at most 2048 characters.")


class ErrorInfo(CamelModel):
    code: str
    message: str


class AnalyzeResponse(CamelModel):
    id: str
    # "running" while the page capture is in progress; "done" when nothing else is pending.
    state: Literal["queued", "running", "done"]
    status: str
    error: ErrorInfo | None = None


class RiskOut(CamelModel):
    level: Literal["low", "suspicious", "high"]
    score: int | None
    summary: str | None = None
    recommendation: str | None = None


class FailureOut(CamelModel):
    code: str
    message: str
    stage: AnalysisStage


class ModuleOut(CamelModel):
    key: Literal["url", "visual", "text", "html"]
    status: str
    summary: str
    unavailable_reason: str | None = None
    findings: list[dict[str, Any]] = Field(default_factory=list)
    data: dict[str, Any] | None = None
    duration_ms: int | None = None


class CaptureArtifactsOut(CamelModel):
    screenshot: bool
    html: bool
    text: bool


class CaptureOut(CamelModel):
    """Page capture of one analysis. File paths and raw HTML are never exposed."""

    id: str
    status: Literal["pending", "running", "completed", "partial", "failed"]
    requested_url: str
    final_url: str | None
    http_status: int | None
    requested_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    viewport_width: int
    viewport_height: int
    artifacts: CaptureArtifactsOut
    screenshot_url: str | None  # path on this API
    text_preview: str | None  # plain text, first 2000 characters
    text_length: int | None
    redirected: bool
    consistent: bool | None  # False: the page navigated while artifacts were taken
    page_title: str | None
    signals: dict[str, bool] | None  # httpError, blank, captcha: observations, not judgements
    error: ErrorInfo | None
    capture_version: str


class ResultOut(CamelModel):
    id: str
    submitted_url: str
    final_url: str | None
    requested_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    status: Literal["completed", "partial", "failed"]
    risk: RiskOut | None
    failure: FailureOut | None
    modules: dict[str, ModuleOut]
    analysis_mode: Literal["full", "url_only"] | None
    model_version: str | None
    is_demo: bool = False
    capture: CaptureOut | None = None  # None for records without a capture


class JobPendingOut(CamelModel):
    id: str
    state: Literal["queued", "running"]
    stage: AnalysisStage
    submitted_url: str


class JobDoneOut(CamelModel):
    id: str
    state: Literal["done"]
    result: ResultOut


class HistoryEntryOut(CamelModel):
    id: str
    submitted_url: str
    final_url: str | None
    analyzed_at: datetime
    status: str
    risk_level: Literal["low", "suspicious", "high"] | None


class HistoryCounts(CamelModel):
    all: int
    low: int
    suspicious: int
    high: int
    failed: int


class HistoryPageOut(CamelModel):
    items: list[HistoryEntryOut]
    # Number of records matching the search and the selected result filter.
    total: int
    # Per-filter counts for the current search (used by the filter chips).
    counts: HistoryCounts
