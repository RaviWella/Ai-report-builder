"""
Semantic layer — maps business language to warehouse tables, columns, joins, and metrics.

Phase 3: feeds schema broker seeds and a compact SEMANTIC GUIDANCE block for the LLM.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

from ..config import SEARCH_STOP_WORDS
from ..workspace.runtime_context import get_datamart_context, mart_schema_for_hints
from .semantic_catalog_paths import resolve_semantic_catalog_path

logger = logging.getLogger("ai_services.datamart.semantic")

_SEMANTIC_PROMPT_MAX_CHARS = 900

# Any one table in a group satisfies the whole group for retrieval validation.
_TABLE_REQUIREMENT_ALTERNATIVES: tuple[frozenset[str], ...] = (
    frozenset({"vw_attendance_summary", "mart_attendance_monthly_summary"}),
    frozenset({"fact_attendance", "fct_daily_attendance"}),
    frozenset({"mart_employee_current", "dim_employee", "snap_employee"}),
    frozenset({"fact_leave_balance", "fact_leave_transaction", "vw_leave_summary"}),
    frozenset({"vw_payroll_summary", "mart_processed_payroll_summary", "fact_payroll"}),
)


def collapse_alternative_table_requirements(
    required: set[str],
    *,
    grounded_short_names: list[str] | None = None,
) -> set[str]:
    """Drop alternative-group members when grounding already has any table from that group."""
    if not required:
        return required
    grounded = {t.lower() for t in (grounded_short_names or [])}
    out = set(required)
    for group in _TABLE_REQUIREMENT_ALTERNATIVES:
        if out & group and grounded & group:
            out -= group
    return out


@dataclass
class SemanticResolution:
    """Output of resolving a user question against the semantic catalog."""

    seed_tables: list[str] = field(default_factory=list)
    topics_matched: list[str] = field(default_factory=list)
    dimensions_matched: list[str] = field(default_factory=list)
    metrics_matched: list[str] = field(default_factory=list)
    join_hints: list[str] = field(default_factory=list)
    prompt_block: str = ""
    """(dimension_name, table_short, column_name) for table-scoped LLM prompts."""
    dimension_bindings: list[tuple[str, str, str]] = field(default_factory=list)


def clear_catalog_cache() -> None:
    """Test helper — reload catalog from disk."""
    _load_catalog_cached.cache_clear()


def active_catalog_path() -> Path:
    """Resolved catalog file for the current datamart runtime context."""
    return resolve_semantic_catalog_path()


@lru_cache(maxsize=32)
def _load_catalog_cached(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    if not path.is_file():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load semantic catalog %s: %s", path, exc)
        return {}


def _load_catalog() -> dict[str, Any]:
    return _load_catalog_cached(str(resolve_semantic_catalog_path()))


def _question_tokens(question: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-z0-9_]+", question.lower())
        if t not in SEARCH_STOP_WORDS and len(t) > 2
    }


def _phrase_in_question(phrase: str, question: str, tokens: set[str]) -> bool:
    p = phrase.lower().strip().replace("_", " ")
    if not p:
        return False
    if p in question:
        return True
    if " " in p:
        return False
    return p in tokens


def _match_topics(question: str, tokens: set[str]) -> list[str]:
    catalog = _load_catalog()
    topics: dict[str, Any] = catalog.get("topics") or {}
    matched: list[str] = []
    for name, spec in topics.items():
        if not isinstance(spec, dict):
            continue
        keywords = spec.get("keywords") or []
        name_hit = _phrase_in_question(name.replace("_", " "), question, tokens) or name in tokens
        kw_hit = any(
            _phrase_in_question(str(kw), question, tokens) for kw in keywords if isinstance(kw, str)
        )
        if name_hit or kw_hit:
            matched.append(name)
    return matched


def _match_dimensions(question: str, tokens: set[str]) -> list[tuple[str, str, str]]:
    catalog = _load_catalog()
    dimensions: dict[str, Any] = catalog.get("dimensions") or {}
    out: list[tuple[str, str, str]] = []
    for dim_name, spec in dimensions.items():
        if not isinstance(spec, dict):
            continue
        table = str(spec.get("table") or "")
        column = str(spec.get("column") or "")
        if not table or not column:
            continue
        synonyms = [dim_name.replace("_", " ")] + list(spec.get("synonyms") or [])
        if any(_phrase_in_question(str(s), question, tokens) for s in synonyms):
            out.append((dim_name, table, column))
    return out


def _match_metrics(question: str, tokens: set[str]) -> list[tuple[str, dict[str, Any]]]:
    catalog = _load_catalog()
    metrics: dict[str, Any] = catalog.get("metrics") or {}
    out: list[tuple[str, dict[str, Any]]] = []
    for metric_name, spec in metrics.items():
        if not isinstance(spec, dict):
            continue
        name_hit = _phrase_in_question(metric_name.replace("_", " "), question, tokens)
        desc = str(spec.get("description") or "").lower()
        desc_hit = any(t in desc for t in tokens if len(t) > 3)
        if "count" in tokens and "count" in metric_name:
            name_hit = True
        if "average" in tokens or "avg" in tokens:
            if "average" in metric_name or "salary" in metric_name:
                name_hit = True
        if "top" in tokens and "top" in metric_name:
            name_hit = True
        if name_hit or desc_hit:
            out.append((metric_name, spec))
    return out


def _semantic_schema_prefix(table_short: str) -> str:
    """Qualified schema for catalog hints (hr mart vs legacy audit schema)."""
    ctx = get_datamart_context()
    if ctx is not None and ctx.is_tenant_etl:
        if table_short.lower().startswith("vw_"):
            return "hr_semantic"
        if table_short.lower().startswith("snap_"):
            return "hr_snap"
        return mart_schema_for_hints()
    return mart_schema_for_hints()


def _qualified_table(short_name: str) -> str:
    schema = _semantic_schema_prefix(short_name)
    return f"{schema}.{short_name}"


def _table_has_column(
    columns_by_table: dict[str, list[str]],
    table_short: str,
    column: str,
) -> bool:
    col_l = (column or "").strip().lower()
    short_l = (table_short or "").strip().lower()
    if not col_l or not short_l:
        return False
    for qualified, cols in columns_by_table.items():
        if qualified.rsplit(".", 1)[-1].lower() != short_l:
            continue
        return col_l in {c.lower() for c in cols if c}
    return False


def catalog_join_hints_for_tables(
    table_short_names: list[str],
    *,
    columns_by_table: Optional[dict[str, list[str]]] = None,
) -> list[str]:
    """Build join hint lines from catalog for the selected table set."""
    catalog = _load_catalog()
    joins: list[Any] = catalog.get("joins") or []
    lowered = {t.lower() for t in table_short_names}
    out: list[str] = []
    for j in joins:
        if not isinstance(j, dict):
            continue
        left_table = str(j.get("left_table") or "")
        right_table = str(j.get("right_table") or "")
        lt = left_table.lower()
        rt = right_table.lower()
        if not lt or not rt:
            continue
        if not any(lt in t for t in lowered) or not any(rt in t for t in lowered):
            continue
        lc = str(j.get("left_column") or "employee_id")
        rc = str(j.get("right_column") or "employee_id")
        if columns_by_table is not None:
            if not _table_has_column(columns_by_table, left_table, lc):
                continue
            if not _table_has_column(columns_by_table, right_table, rc):
                continue
        purpose = j.get("purpose") or ""
        left_q = _qualified_table(left_table)
        right_q = _qualified_table(right_table)
        if lt == "fact_leave_transaction" and rt == "dim_leave_type":
            line = (
                f"Aliases: flt = {left_q}, dlt = {right_q}. "
                f"JOIN dlt ON flt.{lc}::text = dlt.{rc}::text"
            )
        else:
            line = f"{left_q}.{lc} = {right_q}.{rc}"
        if purpose:
            line += f" — {purpose}"
        out.append(line)
    return out


def resolve_semantics(question: str) -> SemanticResolution:
    """
    Match question text to topics, dimensions, metrics, and table seeds.
    """
    q = question.lower().strip()
    tokens = _question_tokens(q)
    catalog = _load_catalog()

    topics_matched = _match_topics(q, tokens)
    dimensions_matched = _match_dimensions(q, tokens)
    metrics_matched = _match_metrics(q, tokens)

    seed_tables: list[str] = []
    seen: set[str] = set()

    def add_table(name: str) -> None:
        key = name.lower()
        if key in seen:
            return
        seen.add(key)
        seed_tables.append(name)

    topics_block: dict[str, Any] = catalog.get("topics") or {}
    for topic in topics_matched:
        spec = topics_block.get(topic) or {}
        for t in spec.get("tables") or []:
            if isinstance(t, str):
                add_table(t)

    for _dim, table, _col in dimensions_matched:
        add_table(table)

    for _metric, spec in metrics_matched:
        for t in spec.get("tables") or []:
            if isinstance(t, str):
                add_table(t)

    join_hints = catalog_join_hints_for_tables(seed_tables)

    prompt_lines = [
        "SEMANTIC GUIDANCE (business terms → use matching physical columns from grounded schema only):",
    ]
    for dim_name, table, column in dimensions_matched[:12]:
        schema = _semantic_schema_prefix(table)
        prompt_lines.append(
            f'- "{dim_name.replace("_", " ")}" → {schema}.{table}.{column}'
        )
    for metric_name, spec in metrics_matched[:6]:
        desc = spec.get("description")
        if desc:
            prompt_lines.append(f"- Metric [{metric_name}]: {desc}")
    if topics_matched:
        prompt_lines.append(f"- Topics detected: {', '.join(topics_matched)}")
    if join_hints:
        prompt_lines.append("- Preferred joins:")
        for hint in join_hints[:4]:
            prompt_lines.append(f"  · {hint}")

    prompt_block = "\n".join(prompt_lines).strip()
    if len(prompt_block) > _SEMANTIC_PROMPT_MAX_CHARS:
        prompt_block = prompt_block[:_SEMANTIC_PROMPT_MAX_CHARS].rstrip() + "\n…"

    logger.debug(
        "Semantic resolve: topics=%s dimensions=%d tables=%s",
        topics_matched,
        len(dimensions_matched),
        seed_tables,
    )

    return SemanticResolution(
        seed_tables=seed_tables,
        topics_matched=topics_matched,
        dimensions_matched=[d[0] for d in dimensions_matched],
        metrics_matched=[m[0] for m in metrics_matched],
        join_hints=join_hints,
        prompt_block=prompt_block,
        dimension_bindings=[
            (dim_name, table, column) for dim_name, table, column in dimensions_matched[:16]
        ],
    )


def semantic_seed_tables(question: str) -> list[str]:
    """Backward-compatible: table seeds only."""
    return resolve_semantics(question).seed_tables


def required_tables_for_question(
    question: str,
    *,
    grounded_short_names: Optional[list[str]] = None,
    chat_intent: Optional["ChatIntent"] = None,
) -> set[str]:
    """
    Tables that retrieval validation expects in grounding before SQL generation.

    Used by the schema broker (must-include) and retrieval repair.
    """
    from ..orchestration.intent_router import ChatIntent
    from ..domain_sql.metric_templates import question_wants_row_detail

    # Modify / post-process follow-ups should not be blocked by domain table heuristics.
    # In these modes we anchor on the prior SQL for grounding rather than enforcing
    # new must-include tables from the shortened follow-up message.
    if chat_intent in (ChatIntent.REFINE_SQL, ChatIntent.POST_PROCESS_ONLY):
        return set()

    semantics = resolve_semantics(question)
    grounded = grounded_short_names or []
    required: set[str] = set()
    catalog = _load_catalog()

    if question_wants_row_detail(question):
        topics_block = catalog.get("topics") or {}
        topic_tables: set[str] = set()
        for topic in semantics.topics_matched:
            spec = topics_block.get(topic) or {}
            for t in spec.get("tables") or []:
                if isinstance(t, str) and t.strip():
                    topic_tables.add(t.lower())
        grounded_lower = {t.lower() for t in grounded}
        if topic_tables and not (topic_tables & grounded_lower):
            return topic_tables
        return set()

    metrics_block = catalog.get("metrics") or {}
    for metric_name in semantics.metrics_matched:
        spec = metrics_block.get(metric_name) or {}
        for t in spec.get("tables") or []:
            if isinstance(t, str) and t.strip():
                required.add(t.lower())

    if not required and semantics.seed_tables:
        required.add(semantics.seed_tables[0].lower())

    q = question.lower()
    if re.search(r"\battendance\b", q):
        grounded_lower = {t.lower() for t in grounded}
        attendance_sources = {
            "vw_attendance_summary",
            "mart_attendance_monthly_summary",
            "fact_attendance",
            "fct_daily_attendance",
        }
        if not (grounded_lower & attendance_sources):
            required.add("vw_attendance_summary")
        if question_wants_row_detail(question) and re.search(
            r"\b(?:employee|employees|staff|assigned)\b", q
        ):
            employee_sources = {"mart_employee_current", "dim_employee", "snap_employee"}
            if not (grounded_lower & employee_sources):
                required.add("mart_employee_current")
    if re.search(r"\bleave\b", q) and re.search(
        r"\b(?:transaction|type|start|end|status|approved|combining|include)\b", q
    ):
        for t in ("fact_leave_balance", "vw_leave_summary", "mart_employee_current"):
            required.add(t)
    if re.search(r"\bprobation\b", q) and question_wants_row_detail(question):
        required.add("mart_employee_current")
    if re.search(r"\bbank\b", q) and re.search(
        r"\b(?:detail|details|code|name|account|passbook|instruction)\b", q
    ):
        for t in (
            "dim_bank",
            "dim_bank_branch",
            "fct_salary_bank_instruction",
            "mart_employee_current",
        ):
            required.add(t)
    if re.search(r"\bemployment\b", q) and re.search(
        r"\b(?:category|type)\b", q
    ):
        required.add("mart_employee_current")
    if question_wants_row_detail(question) and re.search(
        r"\b(?:employee|employees|staff|workforce)\b", q
    ) and not re.search(
        r"\b(?:leave|attendance|payroll|payslip|attrition|turnover)\b", q
    ):
        required.add("mart_employee_current")
    if re.search(r"\bshift\b", q) and re.search(
        r"\b(?:employee|employees|staff|emp)\b", q
    ):
        required.update({"mart_employee_current", "dim_shift"})
    if re.search(
        r"\b(?:recruitment|recruit|hiring|candidate|candidates|pipeline|linkedin|referral)\b",
        q,
    ):
        required.update(
            {
                "fact_recruitment_pipeline",
                "dim_candidate",
                "dim_org_unit",
            }
        )
    if re.search(
        r"\b(?:payslip|pay\s+slip|gross\s+pay|net\s+pay|payroll\s+summary)\b", q
    ) and question_wants_row_detail(question):
        for t in ("vw_payroll_summary", "mart_employee_current"):
            required.add(t)
    if re.search(r"\b(?:epf|etf|tax)\b", q) and re.search(r"\bpayroll\b", q):
        for t in ("vw_payroll_summary", "mart_processed_payroll_summary"):
            required.add(t)
    if re.search(r"\bloan\b", q) and re.search(r"\b(?:deduction|installment)\b", q):
        for t in (
            "fct_processed_loan_deduction",
            "mart_processed_payroll_summary",
            "mart_employee_current",
        ):
            required.add(t)
    if re.search(r"\bovertime\b", q) or re.search(r"\bot\s+hours?\b", q):
        for t in ("fct_overtime", "vw_attendance_summary", "mart_employee_current"):
            required.add(t)
    if re.search(r"\battrition\b|\bturnover\b", q):
        for t in ("vw_turnover", "vw_headcount", "mart_employee_current"):
            required.add(t)
    if re.search(r"\bleave\b", q) and re.search(
        r"\b(?:balance|entitlement|remaining)\b", q
    ):
        for t in ("fact_leave_balance", "vw_leave_summary", "mart_employee_current"):
            required.add(t)
    if re.search(r"\bleave\b", q) and re.search(
        r"\b(?:application|transaction|request|taken|approved)\b", q
    ):
        for t in ("fact_leave_balance", "vw_leave_summary", "mart_employee_current"):
            required.add(t)

    from .. import config as dm_config

    if dm_config.DATAMART_REPORT_SPEC_ENABLED:
        from ..domain_sql.report_spec import compile_report_spec, spec_required_tables

        required |= spec_required_tables(
            compile_report_spec(question, chat_intent=chat_intent)
        )

    return collapse_alternative_table_requirements(
        required, grounded_short_names=grounded
    )
