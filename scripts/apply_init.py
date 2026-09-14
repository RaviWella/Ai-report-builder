"""Apply scripts/init-local-postgres.sql to DATABASE_URL from backend/.env."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402

SQL_PATH = ROOT / "scripts" / "init-local-postgres.sql"
MIGRATION_PATH = ROOT / "scripts" / "migrate_tenant_source_type.sql"


def _statements(sql: str) -> list[str]:
    """Split SQL file into executable chunks (asyncpg allows one statement per execute)."""
    chunks: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            chunk = "\n".join(buf).strip()
            if chunk:
                chunks.append(chunk)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        chunks.append(tail)
    return chunks


async def main() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8")
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        for stmt in _statements(sql):
            await conn.execute(text(stmt))
        if MIGRATION_PATH.exists():
            mig = MIGRATION_PATH.read_text(encoding="utf-8")
            for stmt in _statements(mig):
                await conn.execute(text(stmt))
    async with engine.connect() as conn:
        row = await conn.execute(
            text(
                "SELECT 1 FROM information_schema.schemata "
                "WHERE schema_name = 'hrm_control'"
            )
        )
        ok = row.scalar() == 1
    await engine.dispose()
    print(f"Applied {SQL_PATH.name}; hrm_control present={ok}")


if __name__ == "__main__":
    asyncio.run(main())
