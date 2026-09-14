"""Optional seed rows copied from public template into new tenant schemas."""

from __future__ import annotations

from sqlalchemy.orm import Session

# Report Builder has no mandatory template seed rows today.
_TEMPLATE_SEED_TABLES: tuple[str, ...] = ()


def copy_template_seed_rows(
    session: Session,
    *,
    source_schema: str,
    target_schema: str,
) -> None:
    if not _TEMPLATE_SEED_TABLES:
        return
    from sqlalchemy import text

    for table in _TEMPLATE_SEED_TABLES:
        session.execute(
            text(
                f'INSERT INTO "{target_schema}"."{table}" '
                f'SELECT * FROM "{source_schema}"."{table}"'
            )
        )
