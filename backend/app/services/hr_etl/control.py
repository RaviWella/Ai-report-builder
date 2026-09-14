"""HR ETL governance — run log + step log helpers.

Mirrors finance_etl/control.py pattern exactly.
All tables live in {tenant_id}_hr_control schema.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("hr_etl.control")


def _ctrl(tenant_id: str) -> str:
    from app.services.hr_etl.schema_names import control_schema

    return control_schema(tenant_id)


# ── Run log ─────────────────────────────────────────────────────────

def start_run(
    pg: Engine, tenant_id: str, run_type: str, triggered_by: str
) -> int:
    ctrl = _ctrl(tenant_id)
    with pg.begin() as conn:
        row = conn.execute(
            text(
                f'INSERT INTO "{ctrl}".hr_etl_run_log'
                " (run_type, triggered_by, status, started_at)"
                " VALUES (:rt, :tb, 'running', NOW())"
                " RETURNING run_id"
            ),
            {"rt": run_type, "tb": triggered_by},
        ).fetchone()
    return row[0]


def complete_run(
    pg: Engine,
    tenant_id: str,
    run_id: int,
    *,
    rows_extracted: int = 0,
    rows_loaded: int = 0,
    rows_transformed: int = 0,
    details: Optional[dict] = None,
) -> None:
    ctrl = _ctrl(tenant_id)
    with pg.begin() as conn:
        conn.execute(
            text(
                f'UPDATE "{ctrl}".hr_etl_run_log SET'
                " status='completed', completed_at=NOW(),"
                " rows_extracted=:re, rows_loaded=:rl, rows_transformed=:rt,"
                " details=:det"
                " WHERE run_id=:rid"
            ),
            {
                "re": rows_extracted,
                "rl": rows_loaded,
                "rt": rows_transformed,
                "det": json.dumps(details or {}),
                "rid": run_id,
            },
        )


def fail_run(
    pg: Engine,
    tenant_id: str,
    run_id: int,
    error_message: str,
    details: Optional[dict] = None,
    *,
    exc: Optional[BaseException] = None,
) -> None:
    from app.services.hr_etl.errors import format_run_error

    err = (error_message or "").strip()
    if not err and exc is not None:
        err = format_run_error(exc)
    if not err:
        err = "ETL failed with no error message recorded (check API server logs)."

    ctrl = _ctrl(tenant_id)
    with pg.begin() as conn:
        conn.execute(
            text(
                f'UPDATE "{ctrl}".hr_etl_run_log SET'
                " status='failed', completed_at=NOW(),"
                " error_message=:err, details=:det"
                " WHERE run_id=:rid"
            ),
            {
                "err": err[:2000],
                "det": json.dumps(details or {}),
                "rid": run_id,
            },
        )


# ── Step log ─────────────────────────────────────────────────────────

def start_step(
    pg: Engine, tenant_id: str, run_id: int, step_name: str, step_type: str
) -> int:
    ctrl = _ctrl(tenant_id)
    with pg.begin() as conn:
        row = conn.execute(
            text(
                f'INSERT INTO "{ctrl}".hr_etl_step_log'
                " (run_id, step_name, step_type, status, started_at)"
                " VALUES (:rid, :sn, :st, 'running', NOW())"
                " RETURNING step_id"
            ),
            {"rid": run_id, "sn": step_name, "st": step_type},
        ).fetchone()
    return row[0]


def complete_step(
    pg: Engine,
    tenant_id: str,
    step_id: int,
    *,
    rows_processed: int = 0,
    details: Optional[dict] = None,
) -> None:
    ctrl = _ctrl(tenant_id)
    with pg.begin() as conn:
        conn.execute(
            text(
                f'UPDATE "{ctrl}".hr_etl_step_log SET'
                " status='completed', completed_at=NOW(),"
                " rows_processed=:rp, details=:det"
                " WHERE step_id=:sid"
            ),
            {
                "rp": rows_processed,
                "det": json.dumps(details or {}),
                "sid": step_id,
            },
        )


def fail_step(
    pg: Engine, tenant_id: str, step_id: int, error_message: str
) -> None:
    ctrl = _ctrl(tenant_id)
    with pg.begin() as conn:
        conn.execute(
            text(
                f'UPDATE "{ctrl}".hr_etl_step_log SET'
                " status='failed', completed_at=NOW(), error_message=:err"
                " WHERE step_id=:sid"
            ),
            {"err": error_message[:2000], "sid": step_id},
        )


# ── Watermark ────────────────────────────────────────────────────────

def get_watermark(
    pg: Engine, tenant_id: str, table_name: str
) -> Optional[datetime]:
    ctrl = _ctrl(tenant_id)
    with pg.connect() as conn:
        row = conn.execute(
            text(
                f'SELECT last_value FROM "{ctrl}".hr_etl_watermark'
                " WHERE table_name = :t"
            ),
            {"t": table_name},
        ).scalar()
    return row


def set_watermark(
    pg: Engine, tenant_id: str, table_name: str, value: datetime, rows: int
) -> None:
    ctrl = _ctrl(tenant_id)
    with pg.begin() as conn:
        conn.execute(
            text(
                f'INSERT INTO "{ctrl}".hr_etl_watermark'
                " (table_name, last_value, rows_at_mark, updated_at)"
                " VALUES (:t, :v, :r, NOW())"
                " ON CONFLICT (table_name) DO UPDATE"
                " SET last_value=:v, rows_at_mark=:r, updated_at=NOW()"
            ),
            {"t": table_name, "v": value, "r": rows},
        )
