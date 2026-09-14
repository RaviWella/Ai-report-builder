"""Seed demo_tenant for local development (registry + semantic views with sample data).

Run from repo root:
  cd backend && python ../scripts/seed_demo_tenant.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.application_db import create_postgres_engine  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.tenant import tenant_manager  # noqa: E402

TENANT_ID = "demo_tenant"
SEMANTIC = f"{TENANT_ID}_hr_semantic"


def _ensure_registry(session: Session) -> None:
    row = session.execute(
        text(
            "SELECT 1 FROM hrm_control.tenant_registry WHERE tenant_id = :tid"
        ),
        {"tid": TENANT_ID},
    )
    if row.scalar():
        print(f"  tenant_registry: {TENANT_ID} already exists")
        return

    session.execute(
        text(
            """
            INSERT INTO hrm_control.tenant_registry
                (tenant_id, display_name, source_type, mysql_host, mysql_port,
                 mysql_db, mysql_user, mysql_password_enc, is_active)
            VALUES
                (:tid, :dn, 'mysql', '127.0.0.1', 3306,
                 'minthrm_demo', 'demo', 'demo', TRUE)
            """
        ),
        {"tid": TENANT_ID, "dn": "Demo Tenant (local)"},
    )
    session.commit()
    print(f"  tenant_registry: registered {TENANT_ID}")


def _seed_semantic(session: Session) -> None:
    session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SEMANTIC}"'))

    # Replace prior demo objects so re-runs are idempotent
    for obj in (
        "vw_headcount",
        "vw_turnover",
        "vw_payroll_summary",
        "vw_attendance_summary",
        "vw_leave_summary",
        "vw_performance_summary",
    ):
        session.execute(
            text(f'DROP TABLE IF EXISTS "{SEMANTIC}".{obj} CASCADE')
        )

    session.execute(
        text(
            f"""
            CREATE TABLE "{SEMANTIC}".vw_headcount (
                employee_id     INTEGER,
                department_id   INTEGER,
                branch_id       INTEGER,
                status          VARCHAR(32)
            )
            """
        )
    )
    session.execute(
        text(
            f"""
            INSERT INTO "{SEMANTIC}".vw_headcount (employee_id, department_id, branch_id, status)
            SELECT g, (g % 3) + 1, (g % 2) + 1,
                   CASE
                       WHEN g <= 42 THEN 'active'
                       WHEN g <= 47 THEN 'new_hire'
                       ELSE 'active'
                   END
            FROM generate_series(1, 47) AS g
            """
        )
    )

    session.execute(
        text(
            f"""
            CREATE TABLE "{SEMANTIC}".vw_turnover (
                employee_id     INTEGER,
                department_id   INTEGER,
                branch_id       INTEGER,
                status          VARCHAR(32),
                period_label    VARCHAR(7)
            )
            """
        )
    )
    session.execute(
        text(
            f"""
            INSERT INTO "{SEMANTIC}".vw_turnover
            SELECT g, (g % 3) + 1, (g % 2) + 1, 'separated', '2026-04'
            FROM generate_series(1, 5) AS g
            """
        )
    )

    session.execute(
        text(
            f"""
            CREATE TABLE "{SEMANTIC}".vw_payroll_summary (
                employee_sk     INTEGER,
                department_id   INTEGER,
                branch_id       INTEGER,
                period_label    VARCHAR(7),
                net_salary      NUMERIC(12,2),
                overtime_pay    NUMERIC(12,2)
            )
            """
        )
    )
    session.execute(
        text(
            f"""
            INSERT INTO "{SEMANTIC}".vw_payroll_summary
            SELECT g, (g % 3) + 1, (g % 2) + 1, '2026-05',
                   4500.00 + (g * 120), 150.00 + (g * 10)
            FROM generate_series(1, 42) AS g
            """
        )
    )

    session.execute(
        text(
            f"""
            CREATE TABLE "{SEMANTIC}".vw_attendance_summary (
                employee_sk     INTEGER,
                department_id   INTEGER,
                branch_id       INTEGER,
                period_label    VARCHAR(7),
                scheduled_days  INTEGER,
                present_days    INTEGER,
                late_count      INTEGER,
                overtime_hours  NUMERIC(8,2)
            )
            """
        )
    )
    session.execute(
        text(
            f"""
            INSERT INTO "{SEMANTIC}".vw_attendance_summary
            SELECT g, (g % 3) + 1, (g % 2) + 1, '2026-05',
                   22, 20, CASE WHEN g % 7 = 0 THEN 1 ELSE 0 END, 4.5
            FROM generate_series(1, 42) AS g
            """
        )
    )

    session.execute(
        text(
            f"""
            CREATE TABLE "{SEMANTIC}".vw_leave_summary (
                employee_sk     INTEGER,
                department_id   INTEGER,
                branch_id       INTEGER,
                period_label    VARCHAR(7),
                days_taken      NUMERIC(8,2),
                days_entitled   NUMERIC(8,2),
                sick_days       NUMERIC(8,2)
            )
            """
        )
    )
    session.execute(
        text(
            f"""
            INSERT INTO "{SEMANTIC}".vw_leave_summary
            SELECT g, (g % 3) + 1, (g % 2) + 1, '2026-05',
                   3.0, 14.0, CASE WHEN g % 10 = 0 THEN 2.0 ELSE 0.0 END
            FROM generate_series(1, 42) AS g
            """
        )
    )

    session.execute(
        text(
            f"""
            CREATE TABLE "{SEMANTIC}".vw_performance_summary (
                employee_id     INTEGER,
                department_id   INTEGER,
                branch_id       INTEGER,
                period_label    VARCHAR(7),
                overall_score   NUMERIC(5,2),
                status          VARCHAR(32)
            )
            """
        )
    )
    session.execute(
        text(
            f"""
            INSERT INTO "{SEMANTIC}".vw_performance_summary
            SELECT g, (g % 3) + 1, (g % 2) + 1, '2026-Q1',
                   70.0 + (g % 25),
                   CASE WHEN g % 5 = 0 THEN 'high_performer' ELSE 'meets_expectations' END
            FROM generate_series(1, 42) AS g
            """
        )
    )

    session.commit()
    print(f"  semantic layer: seeded 6 views in {SEMANTIC}")


def main() -> None:
    app_url = settings.application_database_url
    print(f"Seeding local demo data (app DB -> {app_url.split('@')[-1]})")
    engine = create_postgres_engine(app_url)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    with SessionLocal() as session:
        _ensure_registry(session)
        tenant_manager.ensure_schemas_exist(session, TENANT_ID)
        _seed_semantic(session)

    engine.dispose()

    with create_postgres_engine(app_url).connect() as conn:
        hc = conn.execute(
            text(
                f'SELECT COUNT(*) FROM "{SEMANTIC}".vw_headcount WHERE status = :s'
            ),
            {"s": "active"},
        ).scalar()
    print(f"Done. Sample active headcount = {hc}")


if __name__ == "__main__":
    main()
