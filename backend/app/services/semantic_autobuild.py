"""Auto-build semantic entities from the datamart's PHYSICAL layer (`hr` marts and
dims) — zero dependency on the hand-made `hr_semantic` views.

Why: the curated view-based seed doesn't auto-update when the datamart gains a
field, and the views can miss columns the marts already have. Introspecting the
materialised `hr` marts + dims instead means the semantic layer reflects the data
automatically (via the nightly refresh) and stays complete.

This module is the introspection engine only — it turns a physical mart/dim table
into a governed `Entity` (fields, roles, PII, physical mapping) using nothing but
`information_schema` and naming heuristics. Join derivation is deliberately
CONSERVATIVE: only the conformed `employee_sk` key is auto-joined (it is reliable
across marts); irregular keys (e.g. `shift_id` -> `dim_shift.source_shift_id`) are
NOT guessed — they need a curated hint, so we never silently produce a wrong join.
"""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.orm import Session  # noqa: F401 - kept for symmetry / future use

from app.core.config import settings
from app.core.logging import get_logger
from app.db.datamart import get_datamart_engine
from app.domain.enums import AggFn, FieldRole, FieldType
from app.domain.semantic import (
    Entity, JoinDef, PeriodGrain, PhysicalColumn, SemanticCatalog, SemanticField,
)

log = get_logger(__name__)


def _mart_schema() -> str:
    """The denormalised, report-ready consumer schema (the `mart_*` tables) — read
    from settings so a datamart re-layout is a config change, not a code change."""
    return settings.datamart_schema_semantic

# Only the denormalised, report-ready consumer objects become entities (per the
# Marts+Dims decision). Facts (fct_/fact_) are grain-level and skipped.
_ENTITY_PREFIXES = ("mart_", "dim_")
# The conformed key every employee-grained mart/dim shares — the one reliable
# auto-join (irregular keys like shift_id->source_shift_id are NOT guessed).
_CONFORMED_EMPLOYEE_KEY = "employee_sk"
# Preferred physical table for the Employee anchor (a denormalised employee mart),
# discovered by convention; falls back to dim_employee.
_EMPLOYEE_MART = "mart_employee"

# Plumbing columns that carry no reporting value — hidden from the catalogue.
_INTERNAL_EXACT = {
    "tenant_id", "source_system", "dbt_scd_id", "valid_from", "valid_to",
    "is_current", "version_number", "_refreshed_at", "_loaded_at",
    "_source_updated_at",
}
# Surrogate/foreign keys: hidden from user-facing fields, but usable as join keys.
_KEY_SUFFIXES = ("_sk", "_id")
# Non-measure numerics — numeric by type but dimensional in meaning.
_NUMERIC_DIMS = {"year", "month", "month_number", "day", "week", "quarter", "half",
                 "day_of_week", "day_of_month", "week_of_year"}
# Numeric columns whose NAME reads like an identifier/label, not a quantity to sum.
_NUMERIC_DIM_SUFFIX = ("_id", "_sk", "_no", "_code", "_number", "_level", "_order",
                       "_sequence", "_year", "_month", "_half", "_flag")

_PG_NUMERIC = {"integer", "bigint", "smallint", "numeric", "decimal", "double precision", "real"}
_PG_TYPE_MAP = {
    "integer": FieldType.INTEGER, "bigint": FieldType.INTEGER, "smallint": FieldType.INTEGER,
    "numeric": FieldType.DECIMAL, "decimal": FieldType.DECIMAL, "double precision": FieldType.DECIMAL,
    "real": FieldType.DECIMAL, "boolean": FieldType.BOOLEAN, "date": FieldType.DATE,
    "timestamp with time zone": FieldType.DATE, "timestamp without time zone": FieldType.DATE,
}
# A JSON/JSONB column (e.g. a tenant's dynamic "extra fields" blob) isn't exposed
# as one opaque field — its keys are discovered from the data and each becomes its
# own field instead. See _json_key_fields().
_PG_JSON_TYPES = {"json", "jsonb"}
_JSON_KEY_SAMPLE_ROWS = 2000  # bounded sample, never a full scan
_JSON_KEY_MAX_FIELDS = 50  # cap a runaway/garbage blob from exploding the catalogue
_JSON_KEY_SANITIZE_RE = re.compile(r"[^a-z0-9_]+")

# Conservative PII heuristic (no data dictionary): a column whose name contains any
# of these is treated as PII and never exposed to the AI. Err toward privacy.
_PII_HINTS = (
    "nic", "passport", "salary", "email", "mobile", "phone", "dob", "birth",
    "fullname", "surname", "firstname", "lastname", "full_name", "address",
    "account", "bank", "epf", "nationality",
)



# Generic display rules (language-level, not per-field mappings): acronyms shown
# upper-case, common HR/payroll abbreviations expanded, small words lower-cased.
_ACRONYMS = {"nic", "epf", "id", "ot", "ytd", "mtd", "kpi", "hr", "uid", "etf", "paye"}
_ABBREV = {
    "emp": "Employee", "dept": "Department", "desig": "Designation", "mgr": "Manager",
    "dob": "Date of Birth", "amt": "Amount", "qty": "Quantity", "num": "Number",
    "addr": "Address", "org": "Org", "fullname": "Full Name", "init": "Initial",
    "pct": "%", "yr": "Year", "mth": "Month", "avg": "Avg", "min": "Min", "max": "Max",
}
_SMALL_WORDS = {"of", "and", "per", "to", "the"}


def _label(col: str) -> str:
    """Human label from a physical column name, via generic display rules."""
    words = col.replace("_", " ").split()
    out: list[str] = []
    for i, w in enumerate(words):
        lw = w.lower()
        if lw in _ABBREV:
            out.append(_ABBREV[lw])
        elif lw in _ACRONYMS:
            out.append(w.upper())
        elif lw in _SMALL_WORDS and i > 0:
            out.append(lw)
        else:
            out.append(w.capitalize())
    return " ".join(out).replace(" %", " %").strip()


def _is_measure(col: str, data_type: str) -> bool:
    """A numeric column is a MEASURE by default (salary, hours, days, amounts…),
    unless its name reads like an identifier/period/label (…_id, year, month, …_code)."""
    lc = col.lower()
    if data_type not in _PG_NUMERIC:
        return False
    if lc in _NUMERIC_DIMS or lc.endswith(_NUMERIC_DIM_SUFFIX):
        return False
    return True


def _is_pii(col: str) -> bool:
    lc = col.lower()
    return any(h in lc for h in _PII_HINTS)


def _columns(datamart_key: str, table: str) -> list[tuple[str, str]]:
    eng = get_datamart_engine(datamart_key)
    with eng.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        rows = c.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = :t ORDER BY ordinal_position"
            ),
            {"s": _mart_schema(), "t": table},
        ).fetchall()
    return [(r[0], r[1]) for r in rows]


def _safe_key_fragment(key: str) -> str:
    frag = _JSON_KEY_SANITIZE_RE.sub("_", key.strip().lower()).strip("_")
    return frag or "field"


def _json_keys(datamart_key: str, table: str, column: str) -> list[str]:
    """Distinct top-level keys present in a JSON/JSONB column, from a bounded
    sample of rows (never a full scan) — this reflects what the data actually
    has right now, not a fixed schema, since the whole point of a JSON "extra
    fields" column is that its shape is tenant/record-specific and evolves
    without a migration. Non-object rows (an array, a scalar, null) in the
    sample are simply skipped, not treated as an error."""
    eng = get_datamart_engine(datamart_key)
    sem = _mart_schema()
    with eng.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        rows = c.execute(
            text(
                # The object-type check MUST happen before jsonb_object_keys() is
                # ever called on a row (inside the same subquery, not as an outer
                # filter after the LATERAL join) — jsonb_object_keys() raises for
                # a non-object value, and a WHERE clause applied after the join
                # doesn't stop that call from already having run on that row.
                f'SELECT DISTINCT key FROM ('
                f'  SELECT "{column}"::jsonb AS doc FROM "{sem}"."{table}" '
                f'  WHERE "{column}" IS NOT NULL '
                f'    AND jsonb_typeof("{column}"::jsonb) = \'object\' '
                f'  LIMIT :sample'
                f') sampled, LATERAL jsonb_object_keys(sampled.doc) AS key '
                f"ORDER BY key LIMIT :maxfields"
            ),
            {"sample": _JSON_KEY_SAMPLE_ROWS, "maxfields": _JSON_KEY_MAX_FIELDS},
        ).fetchall()
    return [r[0] for r in rows]


def _json_key_fields(
    datamart_key: str, table: str, entity_key: str, column: str,
) -> list[SemanticField]:
    """One SemanticField per key discovered in a JSON/JSONB column — e.g. a
    dynamic "extra fields" blob — bound to `column ->> 'key'` (see
    query_engine.sql_builder.TableRegistry.col_for), never the raw blob
    itself. Best-effort: any failure (a malformed column, an unsupported
    JSON shape) yields no fields for that column rather than failing the
    whole catalogue build."""
    try:
        keys = _json_keys(datamart_key, table, column)
    except Exception as exc:  # noqa: BLE001 - best-effort, never fatal to a rebuild
        log.warning("json_key_discovery_failed", table=table, column=column, error=str(exc)[:200])
        return []
    fields: list[SemanticField] = []
    seen_frags: set[str] = set()
    for raw_key in keys:
        frag = _safe_key_fragment(raw_key)
        if frag in seen_frags:
            continue  # two raw keys sanitizing to the same fragment — keep the first
        seen_frags.add(frag)
        fields.append(
            SemanticField(
                ref=f"{entity_key}.{column}__{frag}",
                label=_label(frag),
                type=FieldType.STRING,
                role=FieldRole.DIMENSION,
                physical=PhysicalColumn(
                    table=table, column=column, schema_name=_mart_schema(), json_key=raw_key,
                ),
                pii=_is_pii(frag),
            )
        )
    if fields:
        log.info("json_key_fields_built", table=table, column=column, fields=len(fields))
    return fields


def _load_dictionary(datamart_key: str) -> dict[tuple[str, str], dict]:
    """Governed column metadata from `<mart>.vw_data_dictionary`, if the warehouse
    exposes it. Returns {(object_name, field_name): {label, description, role, pii}}.
    Absent (older warehouse) -> {} and the caller falls back to naming heuristics."""
    sem = _mart_schema()
    try:
        eng = get_datamart_engine(datamart_key)
        with eng.connect() as c:
            c.execute(text("SET TRANSACTION READ ONLY"))
            rows = c.execute(
                text(
                    f'SELECT object_name, field_name, label, description, role, pii, synonyms '
                    f'FROM "{sem}".vw_data_dictionary'
                )
            ).fetchall()
        out = {
            (r[0], r[1]): {"label": r[2], "description": r[3], "role": r[4],
                           "pii": r[5], "synonyms": list(r[6] or [])}
            for r in rows
        }
        log.info("data_dictionary_loaded", entries=len(out))
        return out
    except Exception as exc:  # noqa: BLE001 - dictionary optional; heuristics fall back
        log.info("data_dictionary_absent", error=str(exc))
        return {}


def build_mart_entity(
    datamart_key: str,
    table: str,
    key: str,
    name: str,
    *,
    primary_key: str = "employee_sk",
    description: str | None = None,
    dictionary: dict[tuple[str, str], dict] | None = None,
) -> Entity | None:
    """Introspect one physical mart/dim table into a governed Entity.

    Hidden: plumbing columns and surrogate/foreign keys. Field metadata prefers
    the governed `mart.vw_data_dictionary` (label / description / role / PII) when
    present, and falls back to naming heuristics otherwise. Returns None if the
    table has no reportable columns."""
    cols = _columns(datamart_key, table)
    if not cols:
        return None
    dictionary = dictionary or {}

    fields: list[SemanticField] = []
    for col, dtype in cols:
        lc = col.lower()
        if lc in _INTERNAL_EXACT or lc.endswith(_KEY_SUFFIXES):
            continue  # plumbing / keys — not user-facing fields
        if dtype in _PG_JSON_TYPES:
            # Not one opaque blob field — each key found in the data becomes its
            # own field (see _json_key_fields). The blob itself stays hidden;
            # raw JSON text isn't reportable/mappable.
            fields.extend(_json_key_fields(datamart_key, table, key, col))
            continue
        ftype = _PG_TYPE_MAP.get(dtype, FieldType.STRING)
        meta = dictionary.get((table, col), {})
        # Governed dictionary wins; heuristics fill the gaps.
        role = meta.get("role")
        measure = (role == "measure") if role in ("measure", "dimension") else _is_measure(col, dtype)
        pii = meta.get("pii")
        pii = _is_pii(col) if pii is None else bool(pii)
        fields.append(
            SemanticField(
                ref=f"{key}.{col}",
                label=meta.get("label") or _label(col),
                description=meta.get("description"),
                type=ftype,
                role=FieldRole.MEASURE if measure else FieldRole.DIMENSION,
                physical=PhysicalColumn(table=table, column=col, schema_name=_mart_schema()),
                allowed_aggregations=[AggFn.SUM, AggFn.AVG, AggFn.MIN, AggFn.MAX] if measure else [],
                synonyms=meta.get("synonyms") or [],
                pii=pii,
            )
        )
    if not fields:
        return None

    # Primary key: prefer the requested one if present, else the first *_sk column.
    have = {c for c, _ in cols}
    pk = primary_key if primary_key in have else next(
        (c for c, _ in cols if c.lower().endswith("_sk")), fields[0].physical.column
    )
    # Period grain: a mart with year + month columns is one row per period, so the
    # compiler aligns period-to-period joins and doesn't cross-multiply rows.
    def _pick(cands: tuple[str, ...]) -> str | None:
        return next((c for c in cands if c in have), None)
    year_c = _pick(("year_no", "year", "payroll_year", "proc_year"))
    month_c = _pick(("month_no", "month", "month_number", "payroll_month", "proc_month"))
    grain = PeriodGrain(year_column=year_c, month_column=month_c) if year_c and month_c else None

    log.info("mart_entity_built", table=table, key=key, fields=len(fields), pk=pk)
    return Entity(
        name=name, key=key, base_schema=_mart_schema(), base_table=table,
        primary_key=pk, description=description, fields=fields, period_grain=grain,
    )


def _list_entity_tables(datamart_key: str) -> list[str]:
    """All mart_/dim_ tables in the core schema (the report-ready consumer layer)."""
    eng = get_datamart_engine(datamart_key)
    with eng.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        rows = c.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = :s ORDER BY table_name"
            ),
            {"s": _mart_schema()},
        ).fetchall()
    return [r[0] for r in rows if r[0].startswith(_ENTITY_PREFIXES)]


def _entity_key(table: str) -> str:
    """Derive a stable entity key from a physical table name (prefix stripped)."""
    for p in _ENTITY_PREFIXES:
        if table.startswith(p):
            return table[len(p):]
    return table


def _entity_name(key: str) -> str:
    return key.replace("_", " ").title()


def build_catalog(tenant_id: str, datamart_key: str, version: int = 1) -> SemanticCatalog:
    """Build the full catalogue by auto-introspecting the datamart's `hr` marts and
    dims — zero `hr_semantic` dependency, no hand-listed fields. New columns/tables
    appear automatically on the next refresh.

    Joins are derived ONLY from the conformed `employee_sk` key: every employee-
    grained entity left-joins the Employee anchor, so a report can combine any mart
    with employee attributes. Irregular keys are left unjoined (never guessed)."""
    tables = _list_entity_tables(datamart_key)
    dictionary = _load_dictionary(datamart_key)  # governed metadata; {} if absent

    # Pick the Employee anchor by convention (denormalised current mart, else the
    # employee dim), so employee attributes live under one stable `employee.*` key.
    anchor_table = _EMPLOYEE_MART if _EMPLOYEE_MART in tables else (
        "dim_employee" if "dim_employee" in tables else None
    )

    # Anchor first so it claims the "employee" key; any other table that derives to
    # a key already taken (e.g. dim_employee vs the mart anchor) is a redundant
    # source and skipped — one entity per key.
    ordered = ([anchor_table] if anchor_table else []) + [t for t in tables if t != anchor_table]
    entities: list[Entity] = []
    seen: set[str] = set()
    for table in ordered:
        key = "employee" if table == anchor_table else _entity_key(table)
        if key in seen:
            log.info("autocatalog_skip_dup", table=table, key=key)
            continue
        # Standalone lookup dims (dim_* with no conformed employee_sk) can't join to
        # Employee — exposing them as entities only causes "can't combine" errors and
        # mis-maps (e.g. "Payroll Period" -> dim_payroll_period, "Shift" -> dim_shift).
        # Their attributes are already denormalised into the marts, so skip them.
        # Marts are always kept (report-ready, standalone or joinable).
        if table != anchor_table and table.startswith("dim_") \
                and not _has_column(datamart_key, table, _CONFORMED_EMPLOYEE_KEY):
            log.info("autocatalog_skip_lookup_dim", table=table)
            continue
        name = "Employee" if key == "employee" else _entity_name(key)
        ent = build_mart_entity(datamart_key, table, key, name, dictionary=dictionary)
        if ent is not None:
            entities.append(ent)
            seen.add(key)

    # Auto-join: any entity (other than Employee) carrying the conformed employee
    # key joins the Employee anchor. Reliable — same key name, same meaning.
    joins: list[JoinDef] = []
    if anchor_table is not None:
        emp_ent = next((e for e in entities if e.key == "employee"), None)
        if emp_ent and _has_column(datamart_key, anchor_table, _CONFORMED_EMPLOYEE_KEY):
            for ent in entities:
                if ent.key == "employee":
                    continue
                if _has_column(datamart_key, ent.base_table, _CONFORMED_EMPLOYEE_KEY):
                    joins.append(JoinDef(
                        left_entity="Employee", right_entity=ent.name,
                        left_key=_CONFORMED_EMPLOYEE_KEY, right_key=_CONFORMED_EMPLOYEE_KEY,
                        join_type="left",
                    ))

    log.info("autocatalog_built", tenant_id=tenant_id, entities=len(entities), joins=len(joins))
    return SemanticCatalog(tenant_id=tenant_id, version=version, entities=entities, joins=joins)


def _has_column(datamart_key: str, table: str, column: str) -> bool:
    eng = get_datamart_engine(datamart_key)
    with eng.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        return c.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = :t AND column_name = :c LIMIT 1"
            ),
            {"s": _mart_schema(), "t": table, "c": column},
        ).first() is not None
