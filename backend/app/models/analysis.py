"""Analysis persistence models.

Stored values match the frontend's TypeScript types in
frontend/src/types/analysis.ts, so API responses can pass them through
unchanged. See backend/README.md for the mapping to Turkish UI labels.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, utcnow


class AnalysisStatus(str, enum.Enum):
    """Processing state of an analysis. Independent from the risk level."""

    PENDING = "pending"  # accepted, not started   -> frontend job state "queued"
    RUNNING = "running"  # in progress             -> frontend job state "running"
    COMPLETED = "completed"  # all modules produced data
    PARTIAL = "partial"  # finished with at least one module missing
    FAILED = "failed"  # no risk assessment could be made


class RiskLevel(str, enum.Enum):
    LOW = "low"
    SUSPICIOUS = "suspicious"
    HIGH = "high"


class AnalysisMode(str, enum.Enum):
    FULL = "full"
    URL_ONLY = "url_only"


class ModuleName(str, enum.Enum):
    """Analysis modules. "html" is the DOM / HTML structure module
    (frontend ModuleKey "html", UI label "HTML yapısı analizi")."""

    URL = "url"
    VISUAL = "visual"
    TEXT = "text"
    HTML = "html"


class ModuleStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"  # ran, but there was nothing to inspect (e.g. no screenshot)
    SKIPPED = "skipped"  # not run because an earlier step failed
    FAILED = "failed"


class FailureCode(str, enum.Enum):
    UNREACHABLE = "unreachable"
    TIMEOUT = "timeout"
    SERVICE_UNAVAILABLE = "service_unavailable"
    UNKNOWN = "unknown"


def _in(column: str, enum_cls: type[enum.Enum]) -> str:
    values = ", ".join(f"'{member.value}'" for member in enum_cls)
    return f"{column} IN ({values})"


class Analysis(Base):
    __tablename__ = "analyses"

    # UUID string; the frontend routes to /analiz/{id} with any string id.
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # TEXT holds up to 65,535 bytes; the frontend accepts URLs up to 2,048 characters.
    submitted_url: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=AnalysisStatus.PENDING.value)
    # NULL until a real result exists. Pending and failed analyses keep NULL.
    risk_level: Mapped[str | None] = mapped_column(String(16))
    # Combined model score 0-100 shown in the UI; NULL while risk_level is NULL.
    risk_score: Mapped[int | None] = mapped_column(SmallInteger)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    error_code: Mapped[str | None] = mapped_column(String(32))
    error_message: Mapped[str | None] = mapped_column(Text)

    analysis_mode: Mapped[str | None] = mapped_column(String(16))
    model_version: Mapped[str | None] = mapped_column(String(64))

    modules: Mapped[list["AnalysisModule"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AnalysisModule.id",
    )

    __table_args__ = (
        CheckConstraint(_in("status", AnalysisStatus), name="status_valid"),
        CheckConstraint(f"risk_level IS NULL OR {_in('risk_level', RiskLevel)}", name="risk_level_valid"),
        CheckConstraint(f"analysis_mode IS NULL OR {_in('analysis_mode', AnalysisMode)}", name="analysis_mode_valid"),
        CheckConstraint(f"error_code IS NULL OR {_in('error_code', FailureCode)}", name="error_code_valid"),
        CheckConstraint("risk_score IS NULL OR (risk_score BETWEEN 0 AND 100)", name="risk_score_range"),
        # A risk level may only exist on a finished, successful analysis.
        CheckConstraint("risk_level IS NULL OR status IN ('completed', 'partial')", name="risk_requires_result"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="duration_non_negative"),
        # History list: newest first.
        Index("ix_analyses_created_at", "created_at"),
        # History filtered by result / status.
        Index("ix_analyses_status_created_at", "status", "created_at"),
        Index("ix_analyses_risk_level_created_at", "risk_level", "created_at"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    def __repr__(self) -> str:
        return f"<Analysis id={self.id} status={self.status} risk_level={self.risk_level}>"


class AnalysisModule(Base):
    __tablename__ = "analysis_modules"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
    )
    module: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ModuleStatus.PENDING.value)

    # One-sentence module summary shown at the top of each detail tab.
    summary: Mapped[str | None] = mapped_column(Text)
    # Frontend Finding[]: [{id, severity, title, description}, ...]
    findings: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    # Module-specific data (frontend UrlModuleData, VisualModuleData, ...).
    features: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    duration_ms: Mapped[int | None] = mapped_column(Integer)
    # Reason shown when status is unavailable / skipped / failed.
    error_message: Mapped[str | None] = mapped_column(Text)

    analysis: Mapped[Analysis] = relationship(back_populates="modules")

    __table_args__ = (
        # One result per module per analysis. Its leading column also serves the FK lookup.
        UniqueConstraint("analysis_id", "module"),
        CheckConstraint(_in("module", ModuleName), name="module_valid"),
        CheckConstraint(_in("status", ModuleStatus), name="status_valid"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="duration_non_negative"),
        Index("ix_analysis_modules_status", "status"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    def __repr__(self) -> str:
        return f"<AnalysisModule analysis_id={self.analysis_id} module={self.module} status={self.status}>"
