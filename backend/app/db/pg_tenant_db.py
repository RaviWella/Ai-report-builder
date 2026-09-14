"""PostgreSQL schema-per-tenant utilities."""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

SYSTEM_SCHEMAS = frozenset(
    {
        "public",
        "information_schema",
        "pg_catalog",
        "pg_toast",
        "platform",
    }
)

SYSTEM_SCHEMA_PREFIXES = ("pg_",)


def schema_lock_id(schema_name: str) -> int:
    digest = hashlib.md5(schema_name.encode()).hexdigest()
    return int(digest[:8], 16) & 0x7FFFFFFF


def is_tenant_schema(schema_name: str) -> bool:
    if schema_name in SYSTEM_SCHEMAS:
        return False
    if any(schema_name.startswith(p) for p in SYSTEM_SCHEMA_PREFIXES):
        return False
    return True


def restore_search_path(session: Session, schema_name: str, *, fallback: str = "public") -> None:
    session.execute(text(f'SET search_path TO "{schema_name}", {fallback}'))


def schema_exists(session: Session, schema_name: str) -> bool:
    row = session.execute(
        text(
            "SELECT 1 FROM information_schema.schemata "
            "WHERE schema_name = :schema_name"
        ),
        {"schema_name": schema_name},
    ).scalar_one_or_none()
    return row is not None


def list_tenant_schemas(session: Session) -> list[str]:
    rows = session.execute(
        text("SELECT schema_name FROM information_schema.schemata ORDER BY schema_name")
    ).scalars().all()
    return sorted(s for s in rows if is_tenant_schema(s))


def seed_tenant_alembic_version(session: Session, tenant_schema: str) -> None:
    version_table = f"alembic_version__{tenant_schema}"
    session.execute(
        text(
            f'CREATE TABLE IF NOT EXISTS public."{version_table}" '
            f"(version_num VARCHAR(32) NOT NULL)"
        )
    )
    existing = session.execute(
        text(f'SELECT version_num FROM public."{version_table}" LIMIT 1')
    ).scalar_one_or_none()
    if existing is not None:
        return

    head = session.execute(
        text("SELECT version_num FROM public.alembic_version LIMIT 1")
    ).scalar_one_or_none()
    if head:
        session.execute(
            text(f'INSERT INTO public."{version_table}" (version_num) VALUES (:ver)'),
            {"ver": head},
        )
        logger.info("Seeded alembic version for %s at %s", tenant_schema, head)


def clone_foreign_keys(
    session: Session,
    *,
    source_schema: str,
    target_schema: str,
) -> None:
    rows = session.execute(
        text("""
            SELECT DISTINCT
                tc.table_name,
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                rc.delete_rule
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            JOIN information_schema.referential_constraints AS rc
                ON rc.constraint_name = tc.constraint_name
                AND rc.constraint_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = :schema_name
        """),
        {"schema_name": source_schema},
    ).fetchall()

    for table_name, constraint_name, column_name, fk_table, fk_column, delete_rule in rows:
        try:
            session.execute(
                text(f"""
                ALTER TABLE "{target_schema}"."{table_name}"
                ADD CONSTRAINT "{constraint_name}"
                FOREIGN KEY ("{column_name}")
                REFERENCES "{target_schema}"."{fk_table}"("{fk_column}")
                ON DELETE {delete_rule}
            """)
            )
        except Exception as exc:
            if "already exists" not in str(exc).lower():
                logger.debug("FK %s on %s: %s", constraint_name, table_name, exc)
