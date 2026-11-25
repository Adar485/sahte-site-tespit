"""Save and read back a disposable analysis inside a transaction, then roll back.

Nothing is left in the database. Usage (from the backend directory):
    python -m scripts.verify_persistence
"""

import sys
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import selectinload


def main() -> int:
    import app.models  # noqa: F401
    from app.db.base import utcnow
    from app.db.errors import describe
    from app.db.session import get_session_factory
    from app.models import (
        Analysis,
        AnalysisMode,
        AnalysisModule,
        AnalysisStatus,
        ModuleName,
        ModuleStatus,
        RiskLevel,
    )

    from app.core.config import get_settings

    if get_settings().password_is_placeholder:
        print("[FAIL] DB_PASSWORD in backend/.env still contains the placeholder. Enter your MySQL password first.")
        return 1

    marker = "https://verify.invalid/persistence-check"
    session = get_session_factory()()
    try:
        started = utcnow()
        analysis = Analysis(
            submitted_url=marker,
            final_url=marker + "?yönlendirme=1",  # non-ASCII checks utf8mb4 round-trip
            status=AnalysisStatus.COMPLETED.value,
            risk_level=RiskLevel.SUSPICIOUS.value,
            risk_score=58,
            created_at=started,
            completed_at=started + timedelta(milliseconds=4200),
            duration_ms=4200,
            analysis_mode=AnalysisMode.FULL.value,
            model_version="verification",
        )
        analysis.modules.append(
            AnalysisModule(
                module=ModuleName.URL.value,
                status=ModuleStatus.COMPLETED.value,
                summary="Doğrulama kaydı — şüpheli ifade içermiyor.",
                findings=[{"id": "v-1", "severity": "info", "title": "Test", "description": "Geçici kayıt"}],
                features={"hostname": "verify.invalid", "usesHttps": True, "redirectChain": []},
                duration_ms=900,
            )
        )
        pending = Analysis(submitted_url=marker + "/pending")
        session.add_all([analysis, pending])
        session.flush()
        analysis_id = analysis.id
        session.expire_all()

        loaded = session.execute(
            select(Analysis).options(selectinload(Analysis.modules)).where(Analysis.id == analysis_id)
        ).scalar_one()
        module = loaded.modules[0]
        checks = {
            "analysis saved and read back": loaded.submitted_url == marker,
            "utf8mb4 text preserved": loaded.final_url.endswith("yönlendirme=1")
            and module.summary.startswith("Doğrulama"),
            "timestamps returned as UTC": loaded.created_at.utcoffset() == timedelta(0),
            "relationship returns module": len(loaded.modules) == 1 and module.module == "url",
            "JSON findings round-trip": module.findings[0]["severity"] == "info",
            "JSON features round-trip": module.features["usesHttps"] is True,
            "pending analysis has no risk level": session.get(Analysis, pending.id).risk_level is None,
        }

        # Constraint checks run in savepoints so the outer transaction survives.
        def rejected(build) -> bool:  # type: ignore[no-untyped-def]
            savepoint = session.begin_nested()
            try:
                session.add(build())
                session.flush()
            except DBAPIError:
                savepoint.rollback()
                return True
            savepoint.rollback()
            return False

        checks["duplicate module per analysis rejected"] = rejected(
            lambda: AnalysisModule(analysis_id=analysis_id, module="url", status="completed")
        )
        checks["risk level on failed analysis rejected"] = rejected(
            lambda: Analysis(submitted_url=marker + "/x", status="failed", risk_level="low")
        )
        checks["unknown module name rejected"] = rejected(
            lambda: AnalysisModule(analysis_id=analysis_id, module="dom", status="completed")
        )

        session.rollback()

        remaining = session.execute(
            select(func.count()).select_from(Analysis).where(Analysis.submitted_url.like(marker + "%"))
        ).scalar_one()
        checks["verification records rolled back"] = remaining == 0
    except Exception as error:  # noqa: BLE001
        session.rollback()
        print(f"[FAIL] {describe(error)}")
        return 1
    finally:
        session.close()

    for name, ok in checks.items():
        print(f"[{'OK' if ok else 'FAIL'}]   {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
