"""
Question-bank SQL fit eval: resolve executable SQL and score question relevance.

Used by ``tools/run_question_bank_sql_fit.py`` and pytest.

Offline mode (default): Tier A/B via mock grounding — no LLM, no warehouse.
Live mode: schema link + Tier A/B against real warehouse introspection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from ..orchestration.intent_router import ChatIntent, classify_chat_intent
from ..llm.llm_response import validate_sql_syntax
from ..domain_sql.report_spec import compile_report_spec
from ..schema_broker import BrokerMode, SchemaGrounding, build_schema_grounding, ensure_grounding_includes_tables
from ..sql.sql_answer_adequacy import (
    check_sql_output_columns,
    score_sql_output_columns,
)
from ..sql.sql_faithfulness import check_sql_faithfulness
from .link_eval import load_question_bank
from .resolve_eval import mock_grounding_from_expect, resolve_sql_offline
from .schema_link_stage import SchemaLinkInput, link_schema_for_turn
from .tier_probe import try_resolve_tier_ab
from ..validation.pipeline_validation import PipelineValidationState

import sqlglot
from sqlglot import exp

EvalMode = Literal["offline", "live"]


def _tables_from_sql_for_eval(sql: str) -> list[str]:
    """Table short names in SQL — no warehouse schema filter (offline eval safe)."""
    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
    except Exception:  # noqa: BLE001
        return []
    out: list[str] = []
    seen: set[str] = set()
    for node in tree.find_all(exp.Table):
        name = (node.name or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


@dataclass
class SqlFitCaseResult:
    section: str
    question: str
    question_preview: str
    tier: Optional[str]
    sql_source: Optional[str]
    sql: Optional[str]
    has_sql: bool
    syntax_ok: bool
    syntax_error: Optional[str]
    adequacy_ok: bool
    adequacy_error: Optional[str]
    adequacy_score: int
    faithfulness_warnings: list[str]
    tables_in_sql: list[str]
    expect_tables_hit: list[str]
    expect_tables_missing: list[str]
    tables_overlap_ok: bool
    tables_overlap_note: Optional[str]
    errors: list[str] = field(default_factory=list)

    @property
    def fit_ok(self) -> bool:
        """SQL resolves, parses, and output columns match the question."""
        return (
            self.has_sql
            and self.syntax_ok
            and self.adequacy_ok
            and not self.errors
        )

    @property
    def full_ok(self) -> bool:
        """Also requires at least one expect_tables hit when the bank declares them."""
        return self.fit_ok and self.tables_overlap_ok


@dataclass
class SqlFitReport:
    mode: str
    total: int
    passed: int
    failed: int
    with_sql: int
    tier_a: int
    tier_b: int
    unresolved: int
    results: list[SqlFitCaseResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.failed == 0


def _preview(q: str, n: int = 72) -> str:
    q = (q or "").strip()
    return q[:n] + ("…" if len(q) > n else "")


def _tables_overlap(
    sql: Optional[str],
    expect_tables: list[str],
    *,
    require_all: bool,
) -> tuple[bool, list[str], list[str]]:
    if not sql or not expect_tables:
        return True, [], []
    used = {t.lower() for t in _tables_from_sql_for_eval(sql)}
    hit: list[str] = []
    missing: list[str] = []
    for raw in expect_tables:
        short = str(raw).rsplit(".", 1)[-1].lower()
        if any(short in u or u.endswith(short) for u in used):
            hit.append(raw)
        else:
            missing.append(raw)
    if require_all:
        ok = not missing
    else:
        ok = bool(hit)
    return ok, hit, missing


def _resolve_offline(case: dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str], SchemaGrounding]:
    q = str(case["question"]).strip()
    expect = list(case.get("expect_tables") or [])
    eval_domain = str(case.get("eval_domain") or "").strip().lower()
    template = case.get("template")
    from .domain_classifier import classify_domain

    classified = classify_domain(q).domain.value
    tier, source, sql = resolve_sql_offline(
        q,
        expect_tables=expect,
        domain=classified,
        template=str(template) if template else None,
        eval_domain=eval_domain,
    )
    grounding = mock_grounding_from_expect(expect, eval_domain=eval_domain or classified)
    return tier, source, sql, grounding


def _resolve_live(case: dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str], SchemaGrounding]:
    q = str(case["question"]).strip()
    expect = list(case.get("expect_tables") or [])
    intent = classify_chat_intent(q, last_sql=None, has_prior_post_process=False)
    spec = compile_report_spec(q, chat_intent=intent or ChatIntent.NEW_QUERY)
    link = link_schema_for_turn(
        SchemaLinkInput(
            question=q,
            chat_intent=intent,
            broker_last_sql=None,
            confirmed_table_names=expect or None,
            report_spec=spec,
        )
    )
    grounding = link.grounding
    if expect:
        grounding = ensure_grounding_includes_tables(grounding, expect)
    domain = link.domain.domain.value
    pval = PipelineValidationState(question=q, report_spec=spec)
    ab = try_resolve_tier_ab(
        question=q,
        grounding=grounding,
        chat_intent=intent,
        report_spec=spec,
        is_modify=False,
        is_add_scenario=False,
        targets=[],
        pval=pval,
        domain=domain,
    )
    if ab and ab.sql:
        return ab.tier, ab.source, ab.sql, grounding
    return None, None, None, grounding


def evaluate_sql_fit_one(
    case: dict[str, Any],
    *,
    mode: EvalMode = "offline",
) -> SqlFitCaseResult:
    q = str(case["question"]).strip()
    section = str(case.get("section") or "")
    expect = list(case.get("expect_tables") or [])
    require_all = bool(case.get("require_all_tables"))
    errors: list[str] = []

    if mode == "live":
        tier, source, sql, grounding = _resolve_live(case)
    else:
        tier, source, sql, grounding = _resolve_offline(case)

    syntax_ok = False
    syntax_error: Optional[str] = None
    if sql:
        syntax_error = validate_sql_syntax(sql)
        syntax_ok = syntax_error is None
        if syntax_error:
            errors.append(f"syntax: {syntax_error}")

    adequacy_error = check_sql_output_columns(q, sql) if sql else "No SQL was produced."
    adequacy_ok = adequacy_error is None
    adequacy_score = score_sql_output_columns(q, sql) if sql else -100
    if not adequacy_ok and sql:
        errors.append(f"adequacy: {adequacy_error}")

    faith_warnings: list[str] = []
    if sql and grounding.columns_by_table:
        gen = check_sql_faithfulness(
            question=q,
            sql=sql,
            grounding=grounding,
            schema_links=[],
            binding_passed=True,
        )
        faith_warnings = list(gen.warnings or [])

    tables_in_sql = _tables_from_sql_for_eval(sql) if sql else []
    overlap_ok, hit, missing = _tables_overlap(
        sql,
        expect,
        require_all=require_all,
    )
    overlap_note: Optional[str] = None
    if sql and expect and not overlap_ok:
        overlap_note = (
            f"SQL missing expect_tables: {', '.join(missing)}"
            if require_all
            else f"SQL hits none of expect_tables: {', '.join(expect[:6])}"
        )
        # Informational only — verified Tier B SQL may use a subset of expect_tables.

    if not sql:
        errors.append("no Tier A/B SQL resolved (Tier C / LLM not run in this eval)")

    return SqlFitCaseResult(
        section=section,
        question=q,
        question_preview=_preview(q),
        tier=tier,
        sql_source=source,
        sql=sql,
        has_sql=bool(sql),
        syntax_ok=syntax_ok if sql else False,
        syntax_error=syntax_error,
        adequacy_ok=adequacy_ok,
        adequacy_error=adequacy_error if not adequacy_ok else None,
        adequacy_score=adequacy_score,
        faithfulness_warnings=faith_warnings,
        tables_in_sql=tables_in_sql,
        expect_tables_hit=hit,
        expect_tables_missing=missing,
        tables_overlap_ok=overlap_ok if sql else False,
        tables_overlap_note=overlap_note,
        errors=errors,
    )


def eval_question_bank_sql_fit(
    cases: list[dict[str, Any]] | None = None,
    *,
    bank_path=None,
    mode: EvalMode = "offline",
) -> SqlFitReport:
    if cases is None:
        _raw, cases = load_question_bank(bank_path)

    results = [evaluate_sql_fit_one(c, mode=mode) for c in cases]
    passed = sum(1 for r in results if r.fit_ok)
    tier_a = sum(1 for r in results if r.tier == "A")
    tier_b = sum(1 for r in results if r.tier == "B")
    with_sql = sum(1 for r in results if r.has_sql)
    unresolved = sum(1 for r in results if not r.has_sql)
    return SqlFitReport(
        mode=mode,
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        with_sql=with_sql,
        tier_a=tier_a,
        tier_b=tier_b,
        unresolved=unresolved,
        results=results,
    )
