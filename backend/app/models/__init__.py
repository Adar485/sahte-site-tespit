"""Import every model here so Base.metadata is complete for Alembic."""

from app.models.analysis import (
    Analysis,
    AnalysisMode,
    AnalysisModule,
    AnalysisStatus,
    FailureCode,
    ModuleName,
    ModuleStatus,
    RiskLevel,
)
from app.models.capture import CaptureStatus, PageCapture

__all__ = [
    "Analysis",
    "AnalysisMode",
    "AnalysisModule",
    "AnalysisStatus",
    "CaptureStatus",
    "FailureCode",
    "ModuleName",
    "ModuleStatus",
    "PageCapture",
    "RiskLevel",
]
