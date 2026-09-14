"""Drop sample semantic TABLES so dbt can create real views after ETL.

Usage:
  cd backend && python ../scripts/clear_demo_semantic.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402

TENANT_ID = "demo_tenant"
SEMANTIC = f"{TENANT_ID}_hr_semantic"
VIEWS = (
    "vw_headcount",
    "vw_turnover",
    "vw_payroll_summary",
    "vw_attendance_summary",
    "vw_leave_summary",
    "vw_performance_summary",
)


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        for name in VIEWS:
            await conn.execute(
                text(f'DROP TABLE IF EXISTS "{SEMANTIC}".{name} CASCADE')
            )
            await conn.execute(
                text(f'DROP VIEW IF EXISTS "{SEMANTIC}".{name} CASCADE')
            )
    await engine.dispose()
    print(f"Cleared demo objects in {SEMANTIC}")


if __name__ == "__main__":
    asyncio.run(main())
