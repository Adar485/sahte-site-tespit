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

__all__ = [
    "Analysis",
    "AnalysisMode",
    "AnalysisModule",
    "AnalysisStatus",
    "FailureCode",
    "ModuleName",
    "ModuleStatus",
    "RiskLevel",
]
