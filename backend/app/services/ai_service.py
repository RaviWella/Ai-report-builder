"""AI Service (Architecture §4.4) — orchestrates the three metadata-only AI tasks.

Responsibilities:
  - resolve the active semantic catalogue and project it to metadata for the AI
  - call the configured provider
  - VALIDATE every AI output against the Pydantic DataSpec and the catalogue
    before it is trusted (the AI's JSON is never used raw)
  - persist build-time chat to ai_sessions and the audit log (SRS §7.4)

Both input modes (chat, Excel) converge on the SAME DataSpec (FR-A7).
"""

from __future__ import annotations

import asyncio
import difflib
import re
from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.base import AIProvider, ExcelColumnMeta, FieldMetadata
from app.ai.factory import build_provider
from app.core.config import get_settings
from app.core.tenancy import TenantContext
from app.domain.enums import AuditAction, FieldRole
from app.domain.report_spec import CalculatedField, DataSpec
from app.ingestion.document_parser import parse_document
from app.query_engine import guards
from app.services.ai_config_service import AIConfigService
from app.services.audit_service import AuditService
from app.services.document_ai_runner import extract_letter_replacements_sdk
from app.services.field_suggest_ai_runner import suggest_field_sdk
from app.services.semantic_service import SemanticService


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


# A message that refines the CURRENT report (vs. naming a fresh one). Only these
# go to the LLM adjust path; everything else is resolved deterministically first.
_REFINEMENT_RE = re.compile(
    r"^\s*(?:add|also|and also|include also|plus|remove|drop|delete|only|just|now|then|"
    r"group by|grouped by|group it|break\s?down|breakdown|split|segment|by |per |"
    r"sort|order by|filter|exclude|without|change|instead|rename|make it|set )",
    re.I,
)
# A follow-up asking to break the current report down, but without naming the axis
# ("breakdown", "group it", "split it up") — we ask the user which field to use.
_BREAKDOWN_RE = re.compile(r"\b(?:break\s?down|breakdown|group it|split|segment)\b", re.I)


def _is_refinement(message: str) -> bool:
    return bool(_REFINEMENT_RE.match(message or ""))


def _wants_breakdown(message: str) -> bool:
    return bool(_BREAKDOWN_RE.search(message or ""))


# A question ABOUT the result already on screen ("what's the total of above?",
# "explain this breakdown"). These reference the previous answer, so they're
# handled conversationally (deterministic quick-answer, else the LLM) rather than
# as a fresh report.
_META_RE = re.compile(
    r"\b(?:of\s+(?:the\s+)?above|above|previous(?:ly)?|earlier|"
    r"this\s+(?:report|result|breakdown|data|list|table|number|count|figure|total)|"
    r"these\s+(?:results?|numbers?|figures?)|that\s+(?:number|count|total|figure)|"
    r"explain|summari[sz]e|what\s+does\s+(?:this|that|it)\s+mean|"
    r"which\s+[a-z ]*?(?:highest|lowest|most|least|biggest|largest|smallest|"
    r"maximum|minimum|top|bottom))\b",
    re.I,
)


def _is_meta_question(message: str) -> bool:
    return bool(_META_RE.search(message or ""))


# A question-shaped message (interrogative lead or trailing '?') — used only as a
# fallback: when it names no buildable report but a result is on screen, answer it
# about that result rather than erroring.
_QUESTION_RE = re.compile(
    r"^\s*(?:what|which|who|whose|how|why|when|is|are|do|does|did|can|could|should|would)\b"
    r"|\?\s*$",
    re.I,
)


def _looks_like_question(message: str) -> bool:
    return bool(_QUESTION_RE.search(message or ""))


def _fmt_num(x: float) -> str:
    return f"{int(x):,}" if float(x).is_integer() else f"{x:,.2f}"


def _local_match(header: str, candidates: list[tuple[str, str, str]]) -> tuple[str | None, float]:
    """Best semantic field for an Excel header by normalized text similarity.
    `candidates` = [(ref, norm_label, norm_ref_tail)]. Returns (ref, score 0..1)."""
    hn = _norm(header)
    if not hn:
        return None, 0.0
    best_ref, best = None, 0.0
    for ref, ln, rn in candidates:
        for target in (ln, rn):
            if not target:
                continue
            if hn == target:
                return ref, 1.0
            # containment (handles merged-section prefixes like 'EARNINGS Blend Allowance')
            if len(target) >= 4 and (target in hn or hn in target):
                score = 0.92
            else:
                score = difflib.SequenceMatcher(None, hn, target).ratio()
            if score > best:
                best_ref, best = ref, score
    return best_ref, best


def _rank_candidates(
    header: str, candidates: list[tuple[str, str, str]], limit: int
) -> list[tuple[str, float]]:
    """Top-`limit` semantic refs for a header by text similarity, best score per
    ref. Same scoring as `_local_match`, but returns a ranked shortlist rather than
    only the single best — used to offer suggestions for a column that didn't map."""
    hn = _norm(header)
    if not hn:
        return []
    best: dict[str, float] = {}
    for ref, ln, rn in candidates:
        for target in (ln, rn):
            if not target:
                continue
            if hn == target:
                score = 1.0
            elif len(target) >= 4 and (target in hn or hn in target):
                score = 0.92
            else:
                score = difflib.SequenceMatcher(None, hn, target).ratio()
            if score > best.get(ref, 0.0):
                best[ref] = score
    return sorted(best.items(), key=lambda kv: kv[1], reverse=True)[:limit]


@dataclass
class SpecProposal:
    data_spec: DataSpec
    rationale: str
    source: str = "llm"  # WS-2: "deterministic" (no LLM) | "llm" (fallback)


@dataclass
class ChatResponse:
    """One conversational turn. `kind="report"` carries a data_spec; `kind="reply"`
    is a plain conversational message (greeting, help, or graceful fallback)."""

    kind: str  # "report" | "reply" | "clarify"
    message: str
    data_spec: DataSpec | None = None
    source: str | None = None
    # Excel-style mapping report for a deterministic resolve: what matched, what
    # didn't, and which filters were applied — lets the UI confirm before running.
    mapping: dict | None = None
    # For kind="clarify": suggested follow-up prompts the user can click to answer.
    options: list[str] | None = None
    # Data gaps surfaced during a report turn: fields the user asked for that aren't
    # in a report mart, explained in business language (drill-down for HR users).
    # [{term, status: "in_source"|"not_captured", message}]. `in_source` → requestable.
    gaps: list[dict] | None = None


@dataclass
class MappingProposal:
    mappings: list[dict]
    rationale: str
    columns_seen: int


class AIService:
    def __init__(self, db: Session, provider: AIProvider | None = None):
        self.db = db
        self.semantic = SemanticService(db)
        self.audit = AuditService(db)
        self.config = AIConfigService(db)
        # An explicit provider override (tests / fakes) bypasses config resolution.
        self._provider_override = provider

    def _provider(self, tenant_id: str) -> AIProvider:
        if self._provider_override is not None:
            return self._provider_override
        return build_provider(self.config.resolve(tenant_id))

    def _fields(self, tenant_id: str) -> list[FieldMetadata]:
        catalog = self.semantic.get_active_catalog(tenant_id)
        allowed = {"ref", "label", "type", "role", "entity", "description", "allowed_aggregations"}
        return [
            FieldMetadata(**{k: v for k, v in m.items() if k in allowed})
            for m in catalog.metadata_for_ai()
        ]

    def _validate(self, tenant_id: str, raw_spec: dict) -> DataSpec:
        """Validate AI JSON -> Pydantic + guard against the catalogue."""
        spec = DataSpec.model_validate(raw_spec)
        catalog = self.semantic.get_active_catalog(tenant_id)
        guards.validate_refs(spec, catalog)
        guards.validate_joins(spec, catalog)
        return spec

    # WS-2 — a deterministic resolver result at/above this confidence skips the LLM.
    _DETERMINISTIC_MIN = 0.6

    def _audit_chat(self, ctx: TenantContext, request: str, *, source: str) -> None:
        self.audit.log(
            user_id=ctx.acting_user_id,
            action=AuditAction.AI_INTERACTION,
            detail={"mode": "chat", "source": source, "request": request},
        )

    def from_natural_language(self, ctx: TenantContext, request: str) -> SpecProposal:
        # WS-2 — tiered: try the deterministic intent resolver first (zero LLM). Only
        # fall back to the LLM for requests it can't confidently, validly resolve.
        from app.services.intent_resolver import resolve_intent

        catalog = self.semantic.get_active_catalog(ctx.tenant_id)
        intent = resolve_intent(request, catalog)
        if intent is not None and intent.confidence >= self._DETERMINISTIC_MIN:
            try:
                spec = self._validate(ctx.tenant_id, intent.data_spec.model_dump(mode="json"))
                self._audit_chat(ctx, request, source="deterministic")
                return SpecProposal(data_spec=spec, rationale=intent.rationale, source="deterministic")
            except guards.GuardError:
                pass  # not resolvable deterministically — fall through to the LLM

        result = self._provider(ctx.tenant_id).natural_language(request, self._fields(ctx.tenant_id))
        spec = self._validate(ctx.tenant_id, result.data_spec)
        self._audit_chat(ctx, request, source="llm")
        return SpecProposal(data_spec=spec, rationale=result.rationale, source="llm")

    def _try_learned(self, ctx: TenantContext, message: str) -> "ChatResponse | None":
        """Replay a previously-learned canonical intent for this phrasing. Returns a
        report ChatResponse on a hit (after re-validating the saved spec against the
        live catalogue), else None. A saved spec that no longer validates — the
        catalogue moved on — is forgotten so it gets re-derived fresh."""
        from app.services.learning_store import LearningStore

        store = LearningStore(self.db)
        try:
            saved = store.lookup(ctx.tenant_id, message)
        except Exception:  # noqa: BLE001 - store must never break the chat
            return None
        if saved is None:
            return None
        try:
            spec = self._validate(ctx.tenant_id, saved["spec"])
        except Exception:  # noqa: BLE001 - stale vs current catalogue
            store.forget(ctx.tenant_id, message)
            return None
        certified = bool(saved.get("certified"))
        source = "certified" if certified else "learned"
        self._audit_chat(ctx, message, source=source)
        return ChatResponse(
            kind="report",
            message=(
                "Certified report — returning the approved canonical answer."
                if certified
                else "Recognised this question — returning the saved report."
            ),
            data_spec=spec,
            source=source,
        )

    def _clarify_breakdown(self, ctx: TenantContext, current_spec: dict) -> "ChatResponse":
        """A follow-up asked to break the current report down but didn't say by which
        field — offer the current entity's usable dimensions as clickable options, so
        the conversation continues in context instead of failing."""
        catalog = self.semantic.get_active_catalog(ctx.tenant_id)
        entity = current_spec.get("entity") or (catalog.entities[0].key if catalog.entities else "")
        prefix = f"{entity}."
        options: list[str] = []
        for ref, f in catalog.field_index().items():
            if not ref.startswith(prefix) or f.role != FieldRole.DIMENSION:
                continue
            if f.pii or ref.endswith((".full_name", ".emp_no", ".nic", ".epf_no")):
                continue  # not useful breakdown axes
            if not getattr(f, "sample_values", None):
                continue  # prefer populated, low-cardinality dimensions
            options.append(f"by {f.label.lower()}")
            if len(options) >= 6:
                break
        return ChatResponse(
            kind="clarify",
            message="Sure — break it down by which field?",
            options=options or ["by department", "by grade", "by gender"],
        )

    def converse(self, ctx: TenantContext, message: str, context: dict) -> "ChatResponse":
        """Answer a question ABOUT the result already on screen. Deterministic first
        (total / average / highest / lowest computed straight from the rows — no LLM),
        then the configured model (mimo-v2.5) for open-ended questions. Degrades to a
        helpful reply if no model is reachable."""
        quick = self._quick_answer(message, context)
        if quick is not None:
            self._audit_chat(ctx, message, source="converse:deterministic")
            return ChatResponse(kind="reply", message=quick, source="deterministic")
        try:
            answer = self._provider(ctx.tenant_id).converse(message, self._format_context(context))
            self._audit_chat(ctx, message, source="converse:llm")
            return ChatResponse(kind="reply", message=answer.strip(), source="llm")
        except Exception as exc:  # noqa: BLE001 - provider/transport: degrade gracefully
            from app.core.logging import get_logger

            get_logger(__name__).warning("chat_converse_error", error=str(exc)[:200])
            return ChatResponse(
                kind="reply",
                message=(
                    "I can read totals and averages off the report above, but for that "
                    "I’d need the AI assistant connected (AI Settings). Try “what’s the "
                    "total?” or “which is highest?”."
                ),
            )

    @staticmethod
    def _numeric_column(cols: list, rows: list) -> str | None:
        def isnum(v: object) -> bool:
            try:
                float(v)  # type: ignore[arg-type]
                return True
            except (TypeError, ValueError):
                return False
        for c in reversed(cols):
            vals = [r.get(c) for r in rows if r.get(c) is not None]
            if vals and all(isnum(v) for v in vals):
                return c
        return None

    def _quick_answer(self, message: str, context: dict) -> str | None:
        """A deterministic answer to an aggregation question over the shown result —
        total / average / highest / lowest / row count. None if not that kind."""
        cols = context.get("columns") or []
        rows = context.get("rows") or []
        if not cols or not rows:
            return None
        low = message.lower()
        if re.search(r"\bhow many (?:rows|records|groups|categor)", low):
            return f"{len(rows):,} rows."
        col = self._numeric_column(cols, rows)
        if col is None:
            return None
        pairs = [(r, float(r[col])) for r in rows if r.get(col) is not None]
        if not pairs:
            return None
        nums = [v for _, v in pairs]
        dim = next((c for c in cols if c != col), None)

        def who(row: dict) -> str:
            return f"{row.get(dim)} " if dim and row.get(dim) is not None else ""

        if re.search(r"\b(total|sum|combined|altogether|overall)\b", low):
            return f"Total {col}: {_fmt_num(sum(nums))}."
        if re.search(r"\b(average|avg|mean)\b", low):
            return f"Average {col}: {_fmt_num(sum(nums) / len(nums))}."
        if re.search(r"\b(highest|max|maximum|most|top|largest|biggest)\b", low):
            r, v = max(pairs, key=lambda p: p[1])
            return f"Highest {col}: {who(r)}({_fmt_num(v)})."
        if re.search(r"\b(lowest|min|minimum|least|fewest|smallest|bottom)\b", low):
            r, v = min(pairs, key=lambda p: p[1])
            return f"Lowest {col}: {who(r)}({_fmt_num(v)})."
        return None

    @staticmethod
    def _format_context(context: dict, max_rows: int = 30) -> str:
        """A compact text rendering of the on-screen result for the model (bounded
        so it fits a small context window)."""
        cols = context.get("columns") or []
        rows = context.get("rows") or []
        head = " | ".join(str(c) for c in cols)
        body = "\n".join(
            " | ".join("" if r.get(c) is None else str(r.get(c)) for c in cols)
            for r in rows[:max_rows]
        )
        more = f"\n… (+{len(rows) - max_rows} more rows)" if len(rows) > max_rows else ""
        prompt = context.get("prompt")
        title = f"Report: {prompt}\n" if prompt else ""
        return f"{title}{head}\n{body}{more}"

    def _remember(self, ctx: TenantContext, message: str, spec: DataSpec, source: str) -> None:
        """Persist a (phrasing → canonical spec) mapping so the same question always
        replays the same answer. Best-effort; only learns LLM/deterministic results,
        not the replay of an already-learned one."""
        if source == "learned":
            return
        from app.services.learning_store import LearningStore

        LearningStore(self.db).remember(
            ctx.tenant_id, message, spec.model_dump(mode="json"),
            source=source, user_id=ctx.acting_user_id,
        )

    def chat(
        self, ctx: TenantContext, message: str, current_spec: dict | None = None,
        context: dict | None = None,
    ) -> ChatResponse:
        """Conversational entry point for the chat report builder. Routes smalltalk /
        help / off-topic to a friendly reply (no LLM, no key needed), and report
        requests through the normal NL→spec (or adjust) path. NEVER raises: any
        failure degrades to a helpful reply, so the chat can't crash on bad input,
        a missing AI key, or an unreachable provider (SaaS-graceful)."""
        from app.services.chat_intent import classify_message, reply_for

        kind = classify_message(message)
        if kind in ("smalltalk", "help"):
            self._audit_chat(ctx, message, source=f"intent:{kind}")
            return ChatResponse(kind="reply", message=reply_for(kind, message))

        # A question about the result already on screen ("total of above?", "explain
        # this") — answer it conversationally rather than as a fresh report.
        if context and context.get("rows") and _is_meta_question(message):
            return self.converse(ctx, message, context)

        has_spec = bool(current_spec and (current_spec.get("fields") or current_spec.get("aggregations")))
        is_refine = has_spec and _is_refinement(message)
        fresh = not is_refine  # a brand-new question (not a tweak of the current report)

        # Canonical-intent replay: a fresh question that was resolved before replays
        # its exact saved spec — guaranteeing the same answer for the same question,
        # with zero re-derivation. Refinements depend on the current report, so they
        # are never keyed/replayed here.
        if fresh:
            learned = self._try_learned(ctx, message)
            if learned is not None:
                return learned

        # Deterministic-first (no LLM). A refinement of an existing report ("add
        # department", "only active") is applied to the current spec; otherwise a
        # fresh field list is resolved as a new report. The LLM is the fallback for
        # whatever neither can handle.
        if is_refine:
            det = self._try_refine(ctx, message, current_spec or {})
            # A "break it down"/"group it" with no axis named → ask which field.
            if det is None and _wants_breakdown(message):
                self._audit_chat(ctx, message, source="clarify")
                return self._clarify_breakdown(ctx, current_spec or {})
        else:
            det = self._try_hybrid(ctx, message)
        if det is not None:
            if fresh and det.kind == "report" and det.data_spec is not None:
                self._remember(ctx, message, det.data_spec, det.source or "deterministic")
            return det

        # No buildable report, but a result is on screen and this reads as a question
        # → answer it about that result (the meta long-tail, e.g. "what % are permanent").
        # A refinement-shaped message ("only permanent?", "add grade") is a report tweak,
        # never a meta question — never send it to converse.
        if (
            context and context.get("rows")
            and _looks_like_question(message) and not _is_refinement(message)
        ):
            return self.converse(ctx, message, context)

        try:
            # Only a REFINEMENT adjusts the current spec; a fresh request builds a new
            # report even when a prior one is on screen (was wrongly using has_spec).
            prop = (
                self.adjust(ctx, message, current_spec or {})
                if is_refine
                else self.from_natural_language(ctx, message)
            )
            if fresh:
                self._remember(ctx, message, prop.data_spec, prop.source or "llm")
            return ChatResponse(kind="report", message=prop.rationale, data_spec=prop.data_spec, source=prop.source)
        except (ValueError, KeyError) as exc:
            # The request looked like a report but didn't resolve to a valid spec —
            # usually because it named data the semantic layer doesn't have. Surface
            # WHAT was missing (when we can tell) so the user can rephrase.
            detail = str(exc)
            missing = re.findall(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z0-9_]+", detail)
            hint = (
                f" I couldn’t find: {', '.join(sorted(set(missing)))}."
                if "Unknown semantic ref" in detail and missing
                else ""
            )
            return ChatResponse(
                kind="reply",
                message=(
                    "I couldn’t turn that into a report." + hint + " Try naming data that "
                    "exists — e.g. “employee name, department, basic salary, tenure band”, "
                    "or a metric like “headcount by department”."
                ),
            )
        except Exception as exc:  # noqa: BLE001 - provider/transport: degrade, never crash the chat
            from app.core.logging import get_logger

            get_logger(__name__).warning("chat_provider_error", error=str(exc)[:200])
            return ChatResponse(
                kind="reply",
                message=(
                    "I build reports straight from your data — I can’t chat about earlier "
                    "answers. Tell me what to show, e.g. “headcount by department” or "
                    "“active employees: name, department, basic salary”. (Free-form Q&A "
                    "needs an AI key in AI Settings.)"
                ),
            )

    # A hybrid result at/above this confidence is served without the LLM.
    _HYBRID_MIN = 0.7

    def _try_hybrid(self, ctx: TenantContext, message: str) -> "ChatResponse | None":
        """Deterministic resolve via the Excel-style hybrid matcher. Returns a
        report ChatResponse (with a mapping report) when it confidently maps to
        valid fields; None to fall back to the LLM. Never raises."""
        try:
            from app.services.nl_hybrid import hybrid_resolve

            catalog = self.semantic.get_active_catalog(ctx.tenant_id)
            res = hybrid_resolve(message, catalog)
            if res is None or res.confidence < self._HYBRID_MIN:
                return None
            spec = self._validate(ctx.tenant_id, res.data_spec.model_dump(mode="json"))
        except (ValueError, KeyError):
            return None  # didn't validate (e.g. unjoinable mix) — let the LLM try
        except Exception as exc:  # noqa: BLE001 - resolver must never break the chat
            from app.core.logging import get_logger

            get_logger(__name__).warning("hybrid_resolve_error", error=str(exc)[:160])
            return None

        # Gaps: for anything that didn't map, drill the datamart layers and explain in
        # business language (is it collected but not in reports, or not captured?), so
        # an HR user understands and can request it — no technical names.
        gaps: list[dict] = []
        if res.unmatched:
            try:
                from app.services.source_discovery import SourceDiscoveryService
                from app.services.tenant_scope import resolve_datamart_key

                dmk = resolve_datamart_key(ctx.tenant_id)
                gaps = SourceDiscoveryService().explain_gaps(dmk, res.unmatched)
            except Exception:  # noqa: BLE001 - discovery must never break the chat
                gaps = []

        msg = res.rationale
        if gaps:
            in_src = [g["term"] for g in gaps if g["status"] == "in_source"]
            not_cap = [g["term"] for g in gaps if g["status"] == "not_captured"]
            notes = []
            if in_src:
                notes.append(f"{', '.join(in_src)} — collected in your system but not in "
                             f"your reports yet (you can request it below)")
            if not_cap:
                notes.append(f"{', '.join(not_cap)} — not being collected in your data yet")
            msg += " Note: " + "; ".join(notes) + "."
        elif res.unmatched:
            msg += " I couldn’t map: " + ", ".join(res.unmatched) + "."
        self._audit_chat(ctx, message, source="deterministic")
        return ChatResponse(
            kind="report", message=msg, data_spec=spec, source="deterministic",
            gaps=gaps or None,
            mapping={
                "matched": [{"phrase": m.phrase, "ref": m.ref, "label": m.label, "score": m.score} for m in res.matched],
                "unmatched": res.unmatched,
                "filters": res.filters,
                "confidence": res.confidence,
            },
        )

    def _try_refine(self, ctx: TenantContext, message: str, current_spec: dict) -> "ChatResponse | None":
        """Deterministically apply a refinement to the current report (add/remove a
        field, add a filter). Returns None to fall back to the LLM adjust path
        (e.g. a regrouping). Never raises."""
        try:
            from app.services.nl_hybrid import refine_spec

            catalog = self.semantic.get_active_catalog(ctx.tenant_id)
            res = refine_spec(current_spec, message, catalog)
            if res is None:
                return None
            spec = self._validate(ctx.tenant_id, res.data_spec.model_dump(mode="json"))
        except (ValueError, KeyError):
            return None
        except Exception as exc:  # noqa: BLE001 - refinement must never break the chat
            from app.core.logging import get_logger

            get_logger(__name__).warning("refine_spec_error", error=str(exc)[:160])
            return None

        msg = res.rationale
        if res.unmatched:
            msg += " (couldn’t apply: " + ", ".join(res.unmatched) + ")"
        self._audit_chat(ctx, message, source="deterministic")
        return ChatResponse(
            kind="report", message=msg, data_spec=spec, source="deterministic",
            mapping={
                "matched": [{"phrase": m.phrase, "ref": m.ref, "label": m.label, "score": m.score} for m in res.matched],
                "unmatched": res.unmatched,
                "filters": res.filters,
                "confidence": res.confidence,
            },
        )

    def adjust(self, ctx: TenantContext, instruction: str, current_spec: dict) -> SpecProposal:
        result = self._provider(ctx.tenant_id).adjustment_chat(
            instruction, current_spec, self._fields(ctx.tenant_id)
        )
        spec = self._validate(ctx.tenant_id, result.data_spec)
        self.audit.log(
            user_id=ctx.acting_user_id,
            action=AuditAction.AI_INTERACTION,
            detail={"mode": "adjust", "instruction": instruction},
        )
        return SpecProposal(data_spec=spec, rationale=result.rationale)

    def derive_field(self, ctx: TenantContext, description: str, label: str | None = None) -> CalculatedField:
        """AI turns a description / rough formula into a governed CalculatedField
        (formula or banding). Validated against the model + the catalogue; the AI
        never returns SQL, and the result is compiled safely by the Query Engine."""
        raw = self._provider(ctx.tenant_id).derive_field(description, self._fields(ctx.tenant_id))
        if label:
            raw["label"] = label
        if not raw.get("name"):
            raw["name"] = (label or "custom").lower().replace(" ", "_")
        calc = CalculatedField.model_validate(raw)  # enforces exactly-one-kind

        # Every underlying ref must exist in the catalogue (no invented columns).
        catalog = self.semantic.get_active_catalog(ctx.tenant_id)
        known = set(catalog.field_index())
        refs = {c.ref for c in calc.cases}
        if calc.expression:
            import re
            refs |= {t for t in re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", calc.expression)
                     if "." in t and not t.startswith("calc.")}
        unknown = refs - known
        if unknown:
            raise ValueError(f"AI referenced unknown fields: {sorted(unknown)}")

        self.audit.log(
            user_id=ctx.acting_user_id,
            action=AuditAction.AI_INTERACTION,
            detail={"mode": "derive_field", "description": description, "name": calc.name},
        )
        return calc

    def test_connection(self, ctx: TenantContext) -> dict:
        """Validate the tenant's stored AI config by a minimal metadata-only probe.
        Returns {ok, message}; never raises so the UI can show a clean result."""
        try:
            provider = self._provider(ctx.tenant_id)
            fields = self._fields(ctx.tenant_id)[:5]
            provider.natural_language("Return a minimal report spec for the employee entity.", fields)
            return {"ok": True, "message": "Provider reachable; returned a valid response."}
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as a message
            return {"ok": False, "message": str(exc)[:400] or type(exc).__name__}

    # Map at most this many columns per AI call so a wide paysheet never overflows
    # a small model's context window.
    _MAP_CHUNK = 12
    _LOCAL_CONFIDENT = 0.90  # accept a local match outright at/above this

    def map_excel(
        self, ctx: TenantContext, content: bytes, filename: str = "", content_type: str = ""
    ) -> MappingProposal:
        """Parse an uploaded sample (Excel / PDF / image) LOCALLY (rows stripped),
        then map headers to semantic fields.

        Strategy: LOCAL fuzzy-match first (header text vs field labels) — this maps
        exact/near matches (e.g. paysheet pay items) instantly with no AI, so it
        scales to hundreds of fields and small-context models. Only ambiguous
        headers go to the AI (batched). If the AI errors, the best local guess is
        used. The parser already stripped all data rows (FR-A2, §8.2)."""
        parsed = parse_document(content, filename=filename, content_type=content_type)
        mappings = self._map_columns(ctx, parsed.columns, mode="excel")
        return MappingProposal(
            mappings=mappings, rationale="Mapped against the semantic layer.",
            columns_seen=len(parsed.columns),
        )

    def suggest_fields(self, ctx: TenantContext, header: str, limit: int = 3) -> list[dict]:
        """Rank the best candidate fields for a column that didn't auto-map, so the
        user picks from a short list instead of scanning the whole catalogue.

        Deterministic first — a fuzzy-ranked shortlist (incl. glossary aliases), no
        AI cost, always available. Only when the top match is genuinely weak (the
        ambiguous long tail) is the AI asked to choose the best ref from that same
        shortlist and say why — grounded on real fields, so it can't invent one.
        Returns [{ref, label, score, reason}], best first."""
        fields = self._fields(ctx.tenant_id)
        valid_refs = {f.ref for f in fields}
        label_by_ref = {f.ref: f.label for f in fields}
        desc_by_ref = {f.ref: (getattr(f, "description", "") or "") for f in fields}
        candidates = [(f.ref, _norm(f.label), _norm(f.ref.split(".", 1)[-1])) for f in fields]

        # Governed data-dictionary synonyms — extra phrases per field so a heading
        # like "in-hand salary" or "take home" ranks onto net pay.
        for f in fields:
            tail = _norm(f.ref.split(".", 1)[-1])
            for phrase in getattr(f, "synonyms", None) or []:
                candidates.append((f.ref, _norm(phrase), tail))

        from app.services.glossary_service import load_active_glossary

        for term in load_active_glossary(self.db, ctx.tenant_id):
            if term.ref and not term.ref.startswith("metric.") and term.ref in valid_refs:
                tail = _norm(term.ref.split(".", 1)[-1])
                for phrase in (term.term, *term.aliases):
                    candidates.append((term.ref, _norm(phrase), tail))

        shortlist = _rank_candidates(header, candidates, max(limit, 6))
        if not shortlist:
            return []
        reasons = {ref: "Closest match by name" for ref, _ in shortlist}

        # Only spend an AI call when the deterministic top is weak (ambiguous).
        top_score = shortlist[0][1]
        if top_score < 0.6:
            try:
                lines = "\n".join(
                    f"{ref}: {label_by_ref.get(ref, ref)}"
                    + (f" — {desc_by_ref[ref][:80]}" if desc_by_ref.get(ref) else "")
                    for ref, _ in shortlist
                )
                # Claude Code SDK path (tool-equipped: can check the live datamart
                # to break a tie between two plausible candidates) — same sync/
                # threadpool bridging as extract_letter_replacements.
                picked_raw = asyncio.run(
                    suggest_field_sdk(ctx, header, lines, get_settings())
                )
                picked = next((ref for ref, _ in shortlist if ref == picked_raw), None)
                if picked:
                    reasons[picked] = "AI’s best guess for this heading"
                    shortlist.sort(key=lambda kv: (kv[0] != picked, -kv[1]))
            except Exception:  # noqa: BLE001 - AI optional; deterministic order stands
                pass

        return [
            {"ref": ref, "label": label_by_ref.get(ref, ref), "score": round(score, 2),
             "reason": reasons.get(ref, "Closest match by name")}
            for ref, score in shortlist[:limit]
        ]

    def map_labels(self, ctx: TenantContext, labels: list[str]) -> list[dict]:
        """Map free-text labels (e.g. payslip line items) to semantic refs with
        the same fuzzy-first, AI-for-leftovers engine as the report Excel flow.
        Labels carry no data values, so this is safe for the payslip layout."""
        cols = [
            ExcelColumnMeta(header=lbl, inferred_type="decimal", sample_is_empty=True)
            for lbl in labels
        ]
        return self._map_columns(ctx, cols, mode="payslip")

    def build_local_matcher(self, ctx: TenantContext):
        """A PURELY LOCAL (no-AI) label->field matcher for fast, deterministic mapping.
        Returns (match, label_by_ref) where match(label) -> (ref|None, score 0..1), built
        from the field labels/refs + glossary aliases — the same signals the report Excel
        mapping uses, minus the AI leftover pass. Instant; safe for repeated calls."""
        fields = self._fields(ctx.tenant_id)
        candidates = [(f.ref, _norm(f.label), _norm(f.ref.split(".", 1)[-1])) for f in fields]
        valid_refs = {f.ref for f in fields}
        label_by_ref = {f.ref: f.label for f in fields}

        from app.services.glossary_service import load_active_glossary

        for term in load_active_glossary(self.db, ctx.tenant_id):
            if term.ref and not term.ref.startswith("metric.") and term.ref in valid_refs:
                tail = _norm(term.ref.split(".", 1)[-1])
                for phrase in (term.term, *term.aliases):
                    candidates.append((term.ref, _norm(phrase), tail))

        def match(label: str) -> tuple[str | None, float]:
            return _local_match(label, candidates)

        return match, label_by_ref

    def extract_letter_replacements(self, ctx: TenantContext, text: str) -> list[dict]:
        """Ask the AI to find a sample letter's PER-RECIPIENT dynamic values and map
        each to a semantic ref. Returns [{text, ref|None, label|None}] — verbatim spans
        the caller replaces with {{ref}} tokens. Hallucinated refs are dropped to None.
        Raises if no AI is usable (caller falls back to the deterministic heuristic)."""
        import json

        fields = self._fields(ctx.tenant_id)
        valid = {f.ref for f in fields}
        label_by_ref = {f.ref: f.label for f in fields}
        # Claude Code SDK path (tool-equipped: can check the live datamart before
        # deciding a ref doesn't fit) — same requirement this feature's own prompt
        # already states ("if unsure, still list the value with ref null"), just
        # given a real alternative to guessing. This route is sync end-to-end
        # (FastAPI runs it in a threadpool), so asyncio.run() bridges the one
        # async call cleanly — no running loop to conflict with here.
        raw = asyncio.run(
            extract_letter_replacements_sdk(ctx, text, fields, get_settings())
        )
        # Tolerate code fences / leading prose around the JSON object.
        s = (raw or "").strip()
        if "```" in s:
            s = s.split("```")[1] if s.split("```")[1:] else s
            s = s.split("\n", 1)[1] if s.lower().startswith("json") else s
        start, end = s.find("{"), s.rfind("}")
        if start == -1 or end == -1:
            return []
        try:
            data = json.loads(s[start : end + 1])
        except ValueError:
            return []
        out: list[dict] = []
        for r in data.get("replacements") or []:
            t = str(r.get("text") or "").strip()
            if not t:
                continue
            ref = r.get("ref")
            if ref and ref in valid:
                out.append({"text": t, "ref": ref, "label": label_by_ref.get(ref, ref)})
            else:
                out.append({"text": t, "ref": None, "label": None})
        return out

    def _map_columns(
        self, ctx: TenantContext, columns: list[ExcelColumnMeta], *, mode: str
    ) -> list[dict]:
        """Fuzzy-match each column's text to a semantic field; send only the
        ambiguous ones to the AI (batched); keep one joinable entity cluster."""
        fields = self._fields(ctx.tenant_id)
        # Pre-normalise the candidate field labels/refs once.
        candidates = [(f.ref, _norm(f.label), _norm(f.ref.split(".", 1)[-1])) for f in fields]
        valid_refs = {f.ref for f in fields}

        # Glossary aliases widen matching: each business synonym of a field ref —
        # including column-header corrections promoted here (Layer 1) — becomes an
        # alternative label for that ref, so a *similar* heading fuzzy-matches it
        # next time, tenant-wide. Only field-ref terms apply to column mapping.
        from app.services.glossary_service import load_active_glossary

        for term in load_active_glossary(self.db, ctx.tenant_id):
            if term.ref and not term.ref.startswith("metric.") and term.ref in valid_refs:
                tail = _norm(term.ref.split(".", 1)[-1])
                for phrase in (term.term, *term.aliases):
                    candidates.append((term.ref, _norm(phrase), tail))

        # Learned corrections win: a header a user has previously confirmed/corrected
        # is auto-mapped from memory (confidence 1.0), skipping the fuzzy/AI guess that
        # mis-mapped it. A learned ref that no longer exists in the catalogue is ignored.
        from app.services.column_mapping_store import ColumnMappingStore

        colmap = ColumnMappingStore(self.db)
        learned = colmap.lookup_all(ctx.tenant_id)
        applied_keys: list[str] = []

        mappings: list[dict] = []
        ambiguous: list[ExcelColumnMeta] = []
        for col in columns:
            hkey = ColumnMappingStore.header_key(col.header)
            if hkey in learned and (learned[hkey] is None or learned[hkey] in valid_refs):
                mappings.append({
                    "header": col.header, "suggested_ref": learned[hkey],
                    "confidence": 1.0, "source": "learned",
                })
                applied_keys.append(hkey)
                continue
            ref, score = _local_match(col.header, candidates)
            if score >= self._LOCAL_CONFIDENT:
                mappings.append({"header": col.header, "suggested_ref": ref, "confidence": round(score, 2)})
            else:
                ambiguous.append(col)

        # Ask the AI only about the leftovers (batched). Fall back to local best.
        if ambiguous:
            provider = self._provider(ctx.tenant_id)
            for i in range(0, len(ambiguous), self._MAP_CHUNK):
                chunk = ambiguous[i : i + self._MAP_CHUNK]
                try:
                    mappings.extend(provider.excel_mapping(chunk, fields).mappings)
                except Exception:  # noqa: BLE001 - AI unavailable/too large -> local guess
                    for col in chunk:
                        ref, score = _local_match(col.header, candidates)
                        mappings.append({
                            "header": col.header,
                            "suggested_ref": ref if score >= 0.6 else None,
                            "confidence": round(score, 2),
                        })

        # All picks must come from ONE joinable cluster. Keep the cluster most
        # labels mapped to and unmatch the rest, so an upload never proposes a mix
        # that can't be saved. Generic — derived from the catalogue's joins.
        self._keep_dominant_cluster(mappings, self.semantic.get_active_catalog(ctx.tenant_id))
        colmap.bump(ctx.tenant_id, applied_keys)

        self.audit.log(
            user_id=ctx.acting_user_id,
            action=AuditAction.AI_INTERACTION,
            detail={"mode": mode, "columns": len(columns), "ai_used": bool(ambiguous)},
        )
        return mappings

    @staticmethod
    def _keep_dominant_cluster(mappings: list[dict], catalog) -> None:  # noqa: ANN001
        """Union-find on the catalogue's declared joins → entity clusters. Keep the
        mappings in the cluster the most headers landed on and unmatch the rest, so
        a single upload never mixes entities that can't be joined into one report.
        Mutates `mappings` in place. Fully generic — no entity names hard-coded."""
        parent: dict[str, str] = {e.key: e.key for e in catalog.entities}

        def find(k: str) -> str:
            while parent.get(k, k) != k:
                parent[k] = parent.get(parent[k], parent[k])
                k = parent[k]
            return k

        name_to_key = {e.name: e.key for e in catalog.entities}
        for j in catalog.joins:
            a = name_to_key.get(j.left_entity, j.left_entity)
            b = name_to_key.get(j.right_entity, j.right_entity)
            if a in parent and b in parent:
                parent[find(a)] = find(b)

        # Learned picks carry the user's explicit intent, so they anchor the
        # dominant cluster (weighted heavily) and are never unmatched.
        counts: Counter[str] = Counter()
        for mp in mappings:
            ref = mp.get("suggested_ref")
            if ref:
                counts[find(ref.split(".", 1)[0])] += 100 if mp.get("source") == "learned" else 1
        if not counts:
            return
        dominant = counts.most_common(1)[0][0]
        for mp in mappings:
            ref = mp.get("suggested_ref")
            if mp.get("source") == "learned":
                continue
            if ref and find(ref.split(".", 1)[0]) != dominant:
                mp["suggested_ref"] = None
                mp["confidence"] = 0.0
