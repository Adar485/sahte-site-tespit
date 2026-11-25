"""Create analyses and analysis_modules tables.

Revision ID: 0001
Revises:
Create Date: 2026-11-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("analyses", "analysis_modules")
TABLE_OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


def _utc_datetime() -> sa.types.TypeEngine:
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def _guard_existing_tables() -> None:
    """Never touch pre-existing tables. Stop and report instead."""
    if context_is_offline():
        return
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    clashes = [name for name in TABLES if name in existing]
    if not clashes:
        return
    details = []
    for name in clashes:
        rows = bind.execute(sa.text(f"SELECT COUNT(*) FROM `{name}`")).scalar_one()
        details.append(f"{name} ({rows} rows)")
    raise RuntimeError(
        "Migration 0001 stopped: these tables already exist and were not modified: "
        + ", ".join(details)
        + ". Inspect them (python -m scripts.check_db) and decide how to reconcile them before migrating."
    )


def context_is_offline() -> bool:
    from alembic import context

    return context.is_offline_mode()


def upgrade() -> None:
    _guard_existing_tables()

    op.create_table(
        "analyses",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("submitted_url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=True),
        sa.Column("risk_score", sa.SmallInteger(), nullable=True),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.Column("completed_at", _utc_datetime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(32), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("analysis_mode", sa.String(16), nullable=True),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_analyses"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'partial', 'failed')", name="status_valid"
        ),
        sa.CheckConstraint(
            "risk_level IS NULL OR risk_level IN ('low', 'suspicious', 'high')", name="risk_level_valid"
        ),
        sa.CheckConstraint(
            "analysis_mode IS NULL OR analysis_mode IN ('full', 'url_only')", name="analysis_mode_valid"
        ),
        sa.CheckConstraint(
            "error_code IS NULL OR error_code IN ('unreachable', 'timeout', 'service_unavailable', 'unknown')",
            name="error_code_valid",
        ),
        sa.CheckConstraint("risk_score IS NULL OR (risk_score BETWEEN 0 AND 100)", name="risk_score_range"),
        sa.CheckConstraint(
            "risk_level IS NULL OR status IN ('completed', 'partial')", name="risk_requires_result"
        ),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="duration_non_negative"),
        **TABLE_OPTIONS,
    )
    op.create_index("ix_analyses_created_at", "analyses", ["created_at"])
    op.create_index("ix_analyses_status_created_at", "analyses", ["status", "created_at"])
    op.create_index("ix_analyses_risk_level_created_at", "analyses", ["risk_level", "created_at"])

    op.create_table(
        "analysis_modules",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("analysis_id", sa.String(36), nullable=False),
        sa.Column("module", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("findings", sa.JSON(), nullable=True),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_analysis_modules"),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            name="fk_analysis_modules_analysis_id_analyses",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("analysis_id", "module", name="uq_analysis_modules_analysis_id_module"),
        sa.CheckConstraint(
            "module IN ('url', 'visual', 'text', 'html')", name="module_valid"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'unavailable', 'skipped', 'failed')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0", name="duration_non_negative"
        ),
        **TABLE_OPTIONS,
    )
    op.create_index("ix_analysis_modules_status", "analysis_modules", ["status"])


def downgrade() -> None:
    # Only runs on an explicit `alembic downgrade`; never part of a normal upgrade.
    op.drop_index("ix_analysis_modules_status", table_name="analysis_modules")
    op.drop_table("analysis_modules")
    op.drop_index("ix_analyses_risk_level_created_at", table_name="analyses")
    op.drop_index("ix_analyses_status_created_at", table_name="analyses")
    op.drop_index("ix_analyses_created_at", table_name="analyses")
    op.drop_table("analyses")
