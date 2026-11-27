"""Create the page_captures table.

Backend startup also creates missing tables, so the table may already exist when
this runs; then nothing is changed and only the revision is recorded.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import mysql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "page_captures"


def _utc_datetime() -> sa.types.TypeEngine:
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        if TABLE in inspector.get_table_names():
            columns = {column["name"] for column in inspector.get_columns(TABLE)}
            if not {"id", "analysis_id", "status", "screenshot_path", "details"} <= columns:
                raise RuntimeError(f"A different {TABLE} table already exists; it was not modified.")
            return

    flags = [sa.Column(name, sa.Boolean(create_constraint=False), nullable=False) for name in ("has_screenshot", "has_html", "has_text")]
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("analysis_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("requested_url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=True),
        sa.Column("http_status", sa.SmallInteger(), nullable=True),
        sa.Column("requested_at", _utc_datetime(), nullable=False),
        sa.Column("started_at", _utc_datetime(), nullable=True),
        sa.Column("completed_at", _utc_datetime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("viewport_width", sa.SmallInteger(), nullable=False),
        sa.Column("viewport_height", sa.SmallInteger(), nullable=False),
        sa.Column("screenshot_path", sa.String(255), nullable=True),
        sa.Column("html_path", sa.String(255), nullable=True),
        sa.Column("text_path", sa.String(255), nullable=True),
        *flags,
        sa.Column("text_length", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(40), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("capture_version", sa.String(16), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_page_captures"),
        sa.ForeignKeyConstraint(
            ["analysis_id"], ["analyses.id"], name="fk_page_captures_analysis_id_analyses", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("analysis_id", name="uq_page_captures_analysis_id"),
        sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'partial', 'failed')", name="status_valid"),
        sa.CheckConstraint("has_screenshot = (screenshot_path IS NOT NULL)", name="screenshot_flag"),
        sa.CheckConstraint("has_html = (html_path IS NOT NULL)", name="html_flag"),
        sa.CheckConstraint("has_text = (text_path IS NOT NULL)", name="text_flag"),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="duration_non_negative"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_page_captures_status", TABLE, ["status"])


def downgrade() -> None:
    # Only on an explicit `alembic downgrade`. Artifact files are not removed.
    op.drop_index("ix_page_captures_status", table_name=TABLE)
    op.drop_table(TABLE)
