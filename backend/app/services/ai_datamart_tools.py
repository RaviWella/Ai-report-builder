"""Safe, read-only, tenant-scoped tools the AI can call mid-conversation to
verify a field or value against the tenant's own live datamart — instead of
guessing from the static catalogue reference alone, or asking the analyst
blind (which is all the AI could do before this).

Generic across any tenant's schema: nothing here is hardcoded to one
warehouse's specific tables/columns. Both tools validate the schema/table
against information_schema (mirrors legacy_sql_converter/catalogue.py's
guard) before touching data.

HARD BOUNDARY (SRS §8.1 "the AI never receives PII" / "never receives
row-level data" — the central privacy guarantee that makes calling an
external AI provider acceptable at all, per SRS §8.1/§484): these tools
must never hand the model an actual employee's record. That is why there
is deliberately NO free-form/arbitrary-SQL tool here — a `run_readonly_query`
escape hatch was considered and rejected, since any SELECT the model can
shape can also project raw per-employee columns straight into its context.
`list_columns` returns information_schema metadata only (names/types, never
values). `sample_distinct_values` returns real column VALUES, so it is
additionally restricted to non-PII-looking column names via
`_PII_COLUMN_RE` — it exists to check a legacy/category code's real values
(e.g. a holiday-type or shift code), not to read individual records.

Every call is logged (tool, tenant_id, session_id, args, row_count) — this
closes a governance gap too: a tech lead can see exactly what the AI
queried, not just what it concluded.

Tenant scope is closed over from a server-derived TenantContext at build
time — the model is never given a tenant/schema parameter that could
influence which tenant's data it reads.
"""

from __future__ import annotations

import json
import re

from claude_agent_sdk import SdkMcpTool, ToolAnnotations, tool
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.core.tenancy import TenantContext
from app.db.datamart import datamart_connection
from app.services.tenant_scope import resolve_datamart_key

log = get_logger(__name__)

_ALLOWED_SCHEMAS = {settings.datamart_schema_semantic, settings.datamart_schema_core}
_TABLE_PREFIX_RE = re.compile(r"^(mart_|fct_|dim_)")
_COLUMN_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_PII_COLUMN_RE = re.compile(
    r"(name|nic|national_id|passport|address|phone|mobile|email|salary|"
    r"basic_pay|bank|account_no|iban|dob|birth|ssn|tax_id|emergency_contact)"
)
_SAMPLE_MAX_ROWS = 20
_READ_ONLY = ToolAnnotations(read_only_hint=True, maxResultSizeChars=20_000)


def _ok(payload: object) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, default=str)}]}


def _err(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "is_error": True}


def _validate_schema_table(schema: str, table: str) -> str | None:
    """None if schema/table is an allowed reportable object; else an error
    message. Only mart_*/core.fct_*/core.dim_* — no raw/staging access."""
    if schema not in _ALLOWED_SCHEMAS:
        return f"Schema {schema!r} isn't accessible — use one of {sorted(_ALLOWED_SCHEMAS)}."
    if not _TABLE_PREFIX_RE.match(table or ""):
        return f"Table {table!r} doesn't look like a reportable object (expected mart_*/fct_*/dim_*)."
    return None


def query_table_columns(ctx: TenantContext, datamart_key: str, schema: str, table: str) -> list[dict]:
    """The columns (name + data type) of one mart/core table — the same query
    the `list_columns` chat tool below runs, extracted so a plain REST route
    (`GET /ai/source-columns`, for the builder's field pickers) can reuse it
    without going through the MCP tool wrapper. Caller must have already
    validated schema/table via `_validate_schema_table`; raises on a DB
    error, same as any other read."""
    with datamart_connection(ctx, datamart_key) as conn:
        rows = conn.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = :t ORDER BY ordinal_position"
            ),
            {"s": schema, "t": table},
        ).fetchall()
    return [{"column": r[0], "type": r[1]} for r in rows]


def build_datamart_tools(ctx: TenantContext, *, session_id: str = "") -> list[SdkMcpTool]:
    """Build the tool set for one chat/enhance turn, scoped to ctx.tenant_id.
    A fresh set per call is cheap (resolve_datamart_key is Redis-cached) and
    keeps tenant scope unambiguous — it is never a tool argument the model
    supplies, only ever this closure's own ctx."""
    datamart_key = resolve_datamart_key(ctx.tenant_id)

    def _log(name: str, args: dict, row_count: int | None, error: str | None = None) -> None:
        log.info(
            "ai_datamart_tool_call",
            tool=name, tenant_id=ctx.tenant_id, session_id=session_id,
            args=args, row_count=row_count, error=error,
        )

    @tool(
        "list_columns",
        "List the columns (name + data type) of one mart/core table in this "
        "tenant's own datamart. Use this to confirm a field actually exists, "
        "and its exact spelling, before assuming a name.",
        {"schema": str, "table": str},
        annotations=_READ_ONLY,
    )
    async def list_columns(args: dict) -> dict:
        schema, table = args.get("schema", ""), args.get("table", "")
        bad = _validate_schema_table(schema, table)
        if bad:
            _log("list_columns", args, None, bad)
            return _err(bad)
        try:
            cols = query_table_columns(ctx, datamart_key, schema, table)
        except Exception as exc:  # noqa: BLE001 - best-effort tool, never crash the turn
            _log("list_columns", args, None, str(exc)[:200])
            return _err(f"Could not read {schema}.{table}: {exc}"[:300])
        _log("list_columns", args, len(cols))
        if not cols:
            return _err(f"{schema}.{table} has no columns, or doesn't exist.")
        return _ok(cols)

    @tool(
        "sample_distinct_values",
        "Sample the distinct values actually present in one column of a "
        "mart/core table (bounded, read-only, grouped with counts). Use this "
        "to check what a legacy code or category field's real values look "
        "like before mapping to it — never guess.",
        {"schema": str, "table": str, "column": str},
        annotations=_READ_ONLY,
    )
    async def sample_distinct_values(args: dict) -> dict:
        schema, table, column = args.get("schema", ""), args.get("table", ""), args.get("column", "")
        bad = _validate_schema_table(schema, table)
        if bad:
            _log("sample_distinct_values", args, None, bad)
            return _err(bad)
        if not _COLUMN_NAME_RE.match(column or ""):
            _log("sample_distinct_values", args, None, "bad column name")
            return _err(f"Column name {column!r} doesn't look valid.")
        if _PII_COLUMN_RE.search(column):
            _log("sample_distinct_values", args, None, "PII-looking column blocked")
            return _err(
                f"Column {column!r} looks like it may hold personal data — this tool "
                "only samples non-personal reference/category columns (codes, types, "
                "statuses), never names/contact/financial identifiers."
            )
        try:
            with datamart_connection(ctx, datamart_key) as conn:
                exists = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_schema = :s AND table_name = :t AND column_name = :c"
                    ),
                    {"s": schema, "t": table, "c": column},
                ).fetchone()
                if not exists:
                    _log("sample_distinct_values", args, None, "unknown column")
                    return _err(f"{schema}.{table} has no column {column!r}.")
                rows = conn.execute(
                    text(
                        f'SELECT DISTINCT "{column}", count(*) FROM "{schema}"."{table}" '
                        f'GROUP BY "{column}" ORDER BY 2 DESC LIMIT :lim'
                    ),
                    {"lim": _SAMPLE_MAX_ROWS},
                ).fetchall()
        except Exception as exc:  # noqa: BLE001 - best-effort tool, never crash the turn
            _log("sample_distinct_values", args, None, str(exc)[:200])
            return _err(f"Could not sample {schema}.{table}.{column}: {exc}"[:300])
        _log("sample_distinct_values", args, len(rows))
        return _ok([{"value": r[0], "count": r[1]} for r in rows])

    return [list_columns, sample_distinct_values]
