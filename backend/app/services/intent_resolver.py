"""WS-2 — deterministic NL → DataSpec resolver (no LLM).

Mirrors mint-analytics' keyword/fuzzy intent engine. It pattern-matches a plain
request against the catalogue's field labels/refs to build a DataSpec for the
common report shapes — field lists and "<measure> by <dimension>" roll-ups —
with zero LLM calls. Reuses the same normalize helper as the Excel mapper.

Tiered use (see AIService.from_natural_language): try this first; if it returns a
confident, guard-valid spec, serve it (source="deterministic"); otherwise fall
back to the LLM (source="llm"). It never runs at report *run* time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.enums import AggFn, FieldRole
from app.domain.report_spec import AggregationSpec, DataSpec, FieldSelection
from app.domain.semantic import SemanticCatalog
from app.services.ai_service import _norm

# Aggregation intent keywords → function. Order matters: longer/more specific first.
_AGG_KEYWORDS: list[tuple[AggFn, tuple[str, ...]]] = [
    (AggFn.AVG, ("average", "avg", "mean")),
    (AggFn.SUM, ("total", "sum of", "sum")),
    (AggFn.MAX, ("maximum", "highest", "max")),
    (AggFn.MIN, ("minimum", "lowest", "min")),
    # COUNT last so "total … late count" reads as SUM. No bare "count" (it appears
    # in field names like "late count"); use explicit count phrasings instead.
    (AggFn.COUNT, ("number of", "how many", "headcount", "head count", "count of",
                   "employee count", "user count", "staff count", "people count")),
]


@dataclass
class ResolvedIntent:
    data_spec: DataSpec
    confidence: float
    rationale: str


def _detect_agg(low: str) -> AggFn | None:
    for fn, words in _AGG_KEYWORDS:
        if any(re.search(rf"\b{re.escape(w)}\b", low) for w in words):
            return fn
    return None


def _overlaps(span: tuple[int, int], covered: list[tuple[int, int]]) -> bool:
    return any(not (span[1] <= s or span[0] >= e) for s, e in covered)


def _best_span(rnorm: str, phrases: list[str], min_len: int) -> tuple[int, int] | None:
    """Earliest containment match of any phrase; prefers the longest phrase."""
    best: tuple[int, int] | None = None
    for ph in phrases:
        pn = _norm(ph)
        if len(pn) < min_len:
            continue
        pos = rnorm.find(pn)
        if pos >= 0 and (best is None or len(pn) > best[1]):
            best = (pos, len(pn))
    return best


def _matched_metrics(
    request: str, catalog: SemanticCatalog, synonyms: dict[str, list[str]]
) -> tuple[list[tuple[object, int]], list[tuple[int, int]]]:
    """Metrics whose label, alias, or a GLOSSARY synonym appears in the request.
    Returns the chosen (metric, position) in request order plus the spans they
    cover, so the field matcher can skip those words — a governed metric wins over
    re-deriving it, and business language ('in-hand salary') maps onto it."""
    rnorm = _norm(request)
    raw: list[tuple[object, int, int]] = []  # metric, pos, len
    for m in catalog.metrics:
        phrases = [m.label, *m.aliases, *synonyms.get(f"metric.{m.key}", [])]
        span = _best_span(rnorm, phrases, min_len=3)
        if span is not None:
            raw.append((m, span[0], span[1]))
    raw.sort(key=lambda h: -h[2])  # longest phrase first wins an overlap
    chosen: list[tuple[object, int]] = []
    covered: list[tuple[int, int]] = []
    for m, pos, ln in raw:
        if _overlaps((pos, pos + ln), covered):
            continue
        covered.append((pos, pos + ln))
        chosen.append((m, pos))
    chosen.sort(key=lambda h: h[1])  # request order
    return chosen, covered


def _matched_fields(
    request: str, catalog: SemanticCatalog, blocked: list[tuple[int, int]] | None = None,
    synonyms: dict[str, list[str]] | None = None,
) -> list[tuple[str, object, int]]:
    """Fields whose (normalised) label — or a GLOSSARY synonym pointing at them —
    appears verbatim in the (normalised) request. Returns (ref, field, position)
    sorted by position. `blocked` spans (e.g. words a metric already claimed) are
    skipped. Containment keeps it precise — no fuzzy guessing in the build path."""
    rnorm = _norm(request)
    syn = synonyms or {}
    hits: list[tuple[str, object, int, int]] = []  # ref, field, pos, match_len
    for ref, f in catalog.field_index().items():
        # Field labels need 4+ chars (avoid noise); curated synonyms 3+.
        label_span = _best_span(rnorm, [f.label], min_len=4)
        syn_span = _best_span(rnorm, syn.get(ref, []), min_len=3)
        span = max([s for s in (label_span, syn_span) if s], key=lambda s: s[1], default=None)
        if span is not None:
            hits.append((ref, f, span[0], span[1]))
    # When two labels match the same span, keep the longer (more specific) one.
    hits.sort(key=lambda h: (h[2], -h[3]))
    chosen: list[tuple[str, object, int]] = []
    covered: list[tuple[int, int]] = list(blocked or [])
    for ref, f, pos, ln in hits:
        span = (pos, pos + ln)
        if _overlaps(span, covered):
            continue  # overlaps a metric span or an already-chosen, longer label
        covered.append(span)
        chosen.append((ref, f, pos))
    return chosen


def _group_dimension(request: str, dims: list[tuple[str, object, int]]) -> str | None:
    """A dimension that appears after the word 'by' becomes the group key."""
    m = re.search(r"\bby\b", request.lower())
    if not m:
        return None
    tail = _norm(request[m.end():])
    for ref, f, _pos in dims:
        if _norm(f.label) in tail:
            return ref
    return None


def resolve_intent(request: str, catalog: SemanticCatalog) -> ResolvedIntent | None:
    low = request.lower()
    # Governed metrics win: match them first and hide the words they claim from the
    # field matcher, so "headcount by department" becomes metric.headcount (one
    # agreed definition) rather than a freshly re-derived count.
    # The glossary contributes business-language synonyms onto governed refs, so
    # "in-hand salary" resolves to whatever ref the tenant's "Take-home Pay" term
    # points at (a metric or a field) — grounded, not guessed.
    synonyms = catalog.synonyms_for_ref()
    metric_hits, metric_spans = _matched_metrics(request, catalog, synonyms)
    matched = _matched_fields(request, catalog, blocked=metric_spans, synonyms=synonyms)
    if not metric_hits and not matched:
        return None

    dims = [(r, f, p) for (r, f, p) in matched if f.role == FieldRole.DIMENSION]
    measures = [(r, f, p) for (r, f, p) in matched if f.role == FieldRole.MEASURE]
    agg = _detect_agg(low)
    group_ref = _group_dimension(request, dims)

    # Shape M — a canonical metric is named: select metric.<key>, grouped by the
    # "by <dimension>" if present. The compiler treats a metric ref as aggregated
    # and auto-groups the selected dimension, so no explicit aggregation is needed.
    if metric_hits:
        fields: list[FieldSelection] = []
        entity: str | None = None
        if group_ref:
            group_field = catalog.resolve(group_ref)
            fields.append(FieldSelection(ref=group_ref, label=group_field.label))
            entity = group_ref.split(".", 1)[0]
        for metric, _pos in metric_hits:
            fields.append(FieldSelection(ref=f"metric.{metric.key}", label=metric.label))
        if entity is None:
            # No grouping dimension — anchor on the first metric's source entity.
            underlying = catalog.expand_field_refs([f"metric.{metric_hits[0][0].key}"])
            entity = next(iter(sorted(underlying)), "employee").split(".", 1)[0]
        names = ", ".join(m.label for m, _ in metric_hits)
        rationale = f"Used governed metric{'s' if len(metric_hits) > 1 else ''}: {names}"
        if group_ref:
            rationale += f" by {catalog.resolve(group_ref).label}"
        return ResolvedIntent(DataSpec(entity=entity, fields=fields), 0.92, rationale + ".")

    # Shape A — a roll-up: "<measure> by <dimension>" or "headcount by <dimension>".
    if agg and group_ref:
        group_field = catalog.resolve(group_ref)
        if agg == AggFn.COUNT and not measures:
            aggs = [AggregationSpec(ref=group_ref, fn=AggFn.COUNT, label="Count")]
        elif measures:
            aggs = [AggregationSpec(ref=r, fn=agg, label=f"{agg.value.title()} {f.label}")
                    for (r, f, _p) in measures]
        else:
            return None
        spec = DataSpec(
            entity=group_ref.split(".", 1)[0],
            fields=[FieldSelection(ref=group_ref, label=group_field.label)],
            group_by=[group_ref],
            aggregations=aggs,
        )
        return ResolvedIntent(spec, 0.9, f"Grouped {', '.join(a.label for a in aggs)} by {group_field.label}.")

    # Shape B — a plain field list: pick the matched fields, in request order.
    if matched:
        fields = [FieldSelection(ref=r, label=f.label) for (r, f, _p) in matched]
        # Confidence scales with how much of the request we explained; one weak hit
        # alone isn't enough to skip the LLM.
        confidence = 0.8 if len(matched) >= 2 else 0.55
        return ResolvedIntent(
            DataSpec(entity=matched[0][0].split(".", 1)[0], fields=fields),
            confidence, "Selected the fields named in the request.",
        )

    return None
