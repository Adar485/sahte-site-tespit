"""One page capture per analysis. Page content lives in files, not in the database."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Index, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, utcnow


class CaptureStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"  # all artifacts, from an unchanged page
    PARTIAL = "partial"  # some artifacts, or the page changed / timed out meanwhile
    FAILED = "failed"  # no artifacts


class PageCapture(Base):
    __tablename__ = "page_captures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=CaptureStatus.PENDING.value)

    requested_url: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[str | None] = mapped_column(Text)
    http_status: Mapped[int | None] = mapped_column(SmallInteger)

    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    viewport_width: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    viewport_height: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # Relative to the storage directory; a flag is true only when its file was written.
    screenshot_path: Mapped[str | None] = mapped_column(String(255))
    html_path: Mapped[str | None] = mapped_column(String(255))
    text_path: Mapped[str | None] = mapped_column(String(255))
    has_screenshot: Mapped[bool] = mapped_column(Boolean(create_constraint=False), nullable=False, default=False)
    has_html: Mapped[bool] = mapped_column(Boolean(create_constraint=False), nullable=False, default=False)
    has_text: Mapped[bool] = mapped_column(Boolean(create_constraint=False), nullable=False, default=False)
    text_length: Mapped[int | None] = mapped_column(Integer)

    error_code: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(Text)
    capture_version: Mapped[str] = mapped_column(String(16), nullable=False)
    # Redirect chain, per-artifact times, strategy, page signals, counters.
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    analysis: Mapped["Analysis"] = relationship(back_populates="capture")  # type: ignore[name-defined]  # noqa: F821

    __table_args__ = (
        UniqueConstraint("analysis_id"),
        CheckConstraint("status IN ('pending', 'running', 'completed', 'partial', 'failed')", name="status_valid"),
        CheckConstraint("has_screenshot = (screenshot_path IS NOT NULL)", name="screenshot_flag"),
        CheckConstraint("has_html = (html_path IS NOT NULL)", name="html_flag"),
        CheckConstraint("has_text = (text_path IS NOT NULL)", name="text_flag"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="duration_non_negative"),
        Index("ix_page_captures_status", "status"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    def __repr__(self) -> str:
        return f"<PageCapture id={self.id} analysis_id={self.analysis_id} status={self.status}>"
