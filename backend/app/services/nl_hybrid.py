"""Hybrid deterministic NL → DataSpec resolver (no LLM).

The Excel-upload flow maps column *headers* to semantic fields by fuzzy text
match. A chat prompt's "include name, department, basic salary, tenure" clause is
the same shape — a list of field names — so this resolver reuses that matcher on
the prompt, then layers rule-based parsing for the parts Excel doesn't have:
filters ("active", "more than 2 years"), grouping ("by department"), and
aggregations ("total", "headcount").

It returns a DataSpec PLUS a mapping report (what matched, what didn't, which
filters were applied) so the UI can show an Excel-style confirmation instead of a
silent — possibly wrong — answer. Deterministic, per-tenant (drives off the
tenant's catalogue), zero-LLM, ms. The chat falls back to the LLM only for prompts
this can't confidently resolve.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter
from dataclasses import dataclass, field

from app.domain.enums import AggFn, FieldRole, FieldType, FilterOp
from app.domain.report_spec import AggregationSpec, DataSpec, FieldSelection, FilterClause
from app.domain.semantic import SemanticCatalog
from app.services.ai_service import _local_match, _norm
from app.services.intent_resolver import _detect_agg

# A same-entity alternative within this score margin of the global-best match is
# preferred — so a field that belongs to the report's own entity wins over a
# slightly higher-scoring lookalike on another entity ("basic salary" -> the
# employee field, not payroll's, avoiding a needless join).
_CLUSTER_MARGIN = 0.12

# A phrase must score at least this to be accepted as a field match.
_MATCH_MIN = 0.82
# Words that introduce a field list; the list region runs from here to a filter/
# grouping boundary (or end of prompt).
_LEAD = re.compile(
    r"\b(?:including|include|show(?:ing)?|list(?:ing)?|with|return|give me|columns?|fields?)\b",
    re.I,
)
# Boundaries that end the field-list region (grouping / filtering language).
_BOUNDARY = re.compile(
    r"\b(?:by|grouped by|per|where|with (?:a|an) |that|who|only|filtered|for the period|for)\b",
    re.I,
)
_SPLIT = re.compile(r",|\band\b|&|/|\bplus\b", re.I)
# Strong, explicit field-list introducers. In a prose sentence the real column
# enumeration follows one of these near the end ("…active staff, INCLUDING name,
# id, branch"), so when present we anchor the field region to the LAST of them —
# past any leading filter clause that a weak lead like "list"/"of" would mis-grab.
_STRONG_LEAD = re.compile(
    r"\b(?:including|includes?|consisting(?: of)?|comprising|containing|contains|"
    r"such as|the following|with the following|columns?|fields?)\b", re.I
)

# Default employment-status vocabulary. Used ONLY as a fallback when the tenant's
# catalogue declares no actual values for its status dimension (i.e. the datamart
# was unreachable at introspection); a real tenant's values come from the field's
# catalogue-introspected `sample_values` instead — see `_status_values`.
_DEFAULT_STATUS_WORDS = (
    "active", "inactive", "resigned", "terminated", "probation", "confirmed",
    "vacated", "suspended", "retired",
)

# Recognise a status the user named, mapping common HR phrasings/stems to a
# canonical status token. The emitted filter value is the tenant's ACTUAL stored
# value when one matches this token (correct casing); otherwise the token itself —
# so a status the data lacks (e.g. "resigned" when everyone is active) honestly
# returns 0 rather than the whole headcount.
_STATUS_SYNONYMS = [
    (re.compile(r"\b(?:inactive|not active)\b", re.I), "inactive"),
    (re.compile(r"\bactive\b", re.I), "active"),
    (re.compile(r"\bresign\w*\b", re.I), "resigned"),            # resign / resigning / resignation
    (re.compile(r"\bterminat\w*\b", re.I), "terminated"),
    (re.compile(r"\bvacat\w*\b", re.I), "vacated"),               # vacate / vacated
    (re.compile(r"\bsuspend\w*\b", re.I), "suspended"),
    (re.compile(r"\bretir\w*\b", re.I), "retired"),
    (re.compile(r"\bprobation\w*\b", re.I), "probation"),
    (re.compile(r"\bconfirmed\b", re.I), "confirmed"),
    (re.compile(r"\b(?:left|exited|departed)\b", re.I), "resigned"),
]

# Connective / generic words that should never, on their own, match a field — they
# cause spurious hits (e.g. "employees" → a "Number of Employees" summary field).
_FILLER = {
    "of", "the", "a", "an", "and", "with", "for", "to", "please", "me", "i", "my",
    "our", "give", "want", "see", "get", "show", "showing", "list", "listing",
    "all", "them", "their", "some", "each", "every", "that", "who", "report",
    "reports", "data", "records", "record", "return", "include", "including",
    "columns", "column", "fields", "field", "what", "whats", "which", "is", "are",
    "in", "at", "on", "from", "as", "this", "these", "those", "there", "can", "have",
    "company", "companies", "organization", "organisation", "org", "today", "now",
    "currently", "moment", "movement", "right", "here",
    "below", "above", "details", "detail", "following", "need", "know", "let", "please",
}
_GENERIC_NOUN = {
    "employee", "employees", "staff", "people", "person", "persons",
    "worker", "workers", "everyone", "everybody", "user", "users",
}
# Aggregation words as single tokens (the field matcher should ignore them; the
# aggregation itself is detected separately). NB: 'headcount' is a real field.
_AGG_TOKENS = {
    "total", "sum", "average", "avg", "mean", "count", "how", "many",
    "maximum", "max", "min", "minimum", "highest", "lowest",
    "full", "overall", "whole", "entire",  # quantifier adjectives for a count
}
# "number" is overloaded: "number of employees" is a COUNT, but "employee number"
# is the emp-no FIELD. So treat the count PHRASE as noise (skipped → bare count),
# while a bare "number" stays matchable (→ emp_no).
_COUNT_PHRASE = re.compile(r"\bnumber\s+of\b", re.I)
# A number followed by a time unit is a filter operand ("3 years"), never a field.
_NUM_UNIT = re.compile(r"\b\d+(?:\.\d+)?\s*(?:year|years|yr|yrs|month|months|day|days|week|weeks)\b", re.I)


def _is_status_token(tok: str) -> bool:
    """True if a token names a status (incl. stems like 'resigning'/'vacated') — so
    it's treated as filter content, never fuzzy-matched as a field."""
    return any(rx.search(tok) for rx, _ in _STATUS_SYNONYMS)


def _is_noise_phrase(phrase: str) -> bool:
    """True when a phrase carries no field-naming content — pure connective/generic
    words, an aggregation word, a status word/stem, or a number+unit operand. Such
    phrases are skipped so they can't fuzzy-hit an unrelated field."""
    if _NUM_UNIT.search(phrase) or _COUNT_PHRASE.search(phrase):
        return True
    toks = re.findall(r"[a-z0-9]+", phrase.lower())
    if not toks:
        return True
    noise = _FILLER | _GENERIC_NOUN | _AGG_TOKENS | set(_DEFAULT_STATUS_WORDS)
    return all(t in noise or _is_status_token(t) for t in toks)


@dataclass
class FieldMatch:
    phrase: str
    ref: str | None
    label: str | None
    score: float


@dataclass
class HybridResult:
    data_spec: DataSpec
    matched: list[FieldMatch] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)  # human-readable applied filters
    confidence: float = 0.0
    rationale: str = ""


def _label_of(ref: str, catalog: SemanticCatalog) -> str:
    if ref.startswith("metric."):
        m = catalog.metric_index().get(ref.split(".", 1)[1])
        return m.label if m else ref
    f = catalog.field_index().get(ref)
    return f.label if f else ref


def _entity_key(ref: str, catalog: SemanticCatalog) -> str:
    """The entity a ref clusters under. A metric resolves to its underlying field's
    entity so it joins/clusters with that entity, not a phantom 'metric' group."""
    if ref.startswith("metric."):
        for u in sorted(catalog.expand_field_refs([ref])):
            return u.split(".", 1)[0]
        return "metric"
    return ref.split(".", 1)[0]


# Fold common word-form variants BEFORE normalising, so a field's abbreviated
# label matches the verbose phrasing regardless of which the tenant used:
# "Employee No" ~ "employee number", "EPF No" ~ "EPF number", "DOB" ~ "date of
# birth". This removes a whole class of label-vs-phrasing mismatches without any
# per-field aliases or catalogue rebuild.
_SYN_FOLD = [
    (re.compile(r"\bnumbers?\b", re.I), "no"),
    (re.compile(r"\bnum\b", re.I), "no"),
    (re.compile(r"#", re.I), "no"),
    (re.compile(r"\bidentifier\b|\bidentification\b", re.I), "id"),
    (re.compile(r"\bdate of birth\b", re.I), "dob"),
]


def _fold_text(text: str) -> str:
    """Apply synonym folding (word-form only; no stripping). Underscores → spaces
    first so a ref tail like 'date_of_birth' folds the same as the phrase."""
    text = text.replace("_", " ")
    for rx, rep in _SYN_FOLD:
        text = rx.sub(rep, text)
    return text


def _mnorm(text: str) -> str:
    """Normalise for matching: fold synonyms, then strip to alphanumerics."""
    return _norm(_fold_text(text))


def _candidates(catalog: SemanticCatalog) -> list[tuple[str, str, str]]:
    """Matchable text → ref. Fields by label/ref-tail, plus governed metrics by
    label/alias, plus glossary synonyms (business language → the governed ref a term
    points at). So 'net pay' / 'take-home pay' resolve to metric.total_net etc.
    All targets are synonym-folded (see `_mnorm`) so abbreviated labels still match
    verbose phrasings."""
    cands = [
        (f.ref, _mnorm(f.label), _mnorm(f.ref.split(".", 1)[-1]))
        for e in catalog.entities
        for f in e.fields
    ]
    for m in catalog.metrics:
        ref = f"metric.{m.key}"
        cands.append((ref, _mnorm(m.label), ""))
        cands += [(ref, _mnorm(a), "") for a in m.aliases if a]
    for ref, phrases in catalog.synonyms_for_ref().items():
        cands += [(ref, _mnorm(p), "") for p in phrases if p]
    return cands


def _field_region(request: str) -> str:
    """The slice of the prompt that names fields — after a lead word, up to a
    filter/grouping boundary. Falls back to the whole prompt when there's no lead
    word (so a bare 'name, department, salary' still works).

    A colon almost always precedes the field list ("…employee details: A, B, C"),
    so we take everything after the LAST colon first. Otherwise a strong introducer
    ("including …") wins: in prose the field list trails it, so we anchor to the LAST
    strong lead and run to end — skipping a leading filter clause ("active staff who
    completed 2 years of service, including …") that a weak lead plus a "who"
    boundary would otherwise truncate to noise.
    """
    if ":" in request:
        after = request.rsplit(":", 1)[1].strip(" .,")
        if "," in after or _SPLIT.search(after):  # a colon that introduces a list
            return after
    strong = list(_STRONG_LEAD.finditer(request))
    start = strong[-1].end() if strong else (_LEAD.search(request).end() if _LEAD.search(request) else 0)
    rest = request[start:]
    boundary = _BOUNDARY.search(rest)
    return (rest[: boundary.start()] if boundary else rest).strip(" .,:")


def _split_phrases(region: str) -> list[str]:
    return [p.strip(" .,:") for p in _SPLIT.split(region) if p.strip(" .,:")]


def _status_field(catalog: SemanticCatalog) -> tuple[str, object] | None:
    """A dimension that looks like an employment-status field."""
    for ref, f in catalog.field_index().items():
        if f.role == FieldRole.DIMENSION and (
            ref.endswith(".status") or "status" in _norm(f.label)
        ) and "lifecycle" not in ref:
            return ref, f
    return None


def _status_values(field: object) -> list[str]:
    """The candidate status values to match a prompt against — the dimension's
    catalogue-introspected `sample_values` (this tenant's actual values) when known,
    else the default vocabulary. Returned values keep their stored representation so
    the emitted filter matches what's in the datamart."""
    vals = list(getattr(field, "sample_values", None) or [])
    return vals if vals else list(_DEFAULT_STATUS_WORDS)


def _tenure_field(catalog: SemanticCatalog) -> tuple[str, object] | None:
    """A measure that looks like tenure / years-of-service."""
    for ref, f in catalog.field_index().items():
        if f.role == FieldRole.MEASURE and ("tenure" in _norm(f.label) or "tenure" in ref):
            return ref, f
    return None


def _period_year_field(catalog: SemanticCatalog) -> str | None:
    """The integer period-YEAR dimension (e.g. payroll.year), if any."""
    for ref, f in catalog.field_index().items():
        ln = _norm(f.label)
        if (
            f.role == FieldRole.DIMENSION and f.type == FieldType.INTEGER
            and ("year" in ln or ref.endswith(".year")) and "birth" not in ln
        ):
            return ref
    return None


def _period_month_field(catalog: SemanticCatalog) -> str | None:
    """The integer period-MONTH dimension (e.g. payroll.month), if any."""
    for ref, f in catalog.field_index().items():
        if (
            f.role == FieldRole.DIMENSION and f.type == FieldType.INTEGER
            and ("month" in _norm(f.label) or ref.endswith(".month"))
        ):
            return ref
    return None


def _date_field(catalog: SemanticCatalog, prefer: str | None = None) -> str | None:
    """A DATE field — preferring one whose ref/label contains `prefer` (e.g. 'join'
    for 'joined in the last…'); else the first date field."""
    fallback = None
    for ref, f in catalog.field_index().items():
        if f.type == FieldType.DATE:
            if prefer and (prefer in ref.lower() or prefer in _norm(f.label)):
                return ref
            fallback = fallback or ref
    return fallback


# "last 12 months", "past 6 months", "previous 30 days", "trailing 2 years"
_LAST_N = re.compile(r"\b(?:last|past|previous|trailing)\s+(\d+)\s*(year|month|week|day)s?\b", re.I)


def _parse_period(request: str, catalog: SemanticCatalog) -> list[FilterClause]:
    """The TIME block (PPT grammar). Emits SYMBOLIC period filters (`@period:` tokens
    the compiler resolves to the current period at run time, so the spec never goes
    stale). Rolling windows ("last 12 months") bind to a DATE field; calendar
    periods ("this month", "YTD", "this year") bind to the year/month dimensions."""
    low = request.lower()
    out: list[FilterClause] = []

    # Rolling window relative to today, on a date column.
    m = _LAST_N.search(low)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        df = _date_field(catalog, prefer="join" if "join" in low else None)
        if df:
            days = {"day": n, "week": n * 7}.get(unit)
            tok = f"@period:days_ago:{days}" if days else f"@period:months_ago:{n * (12 if unit == 'year' else 1)}"
            out.append(FilterClause(ref=df, op=FilterOp.GTE, value=tok))
            return out

    yf, mf = _period_year_field(catalog), _period_month_field(catalog)
    if re.search(r"\b(year[- ]to[- ]date|ytd)\b", low) and yf:
        out.append(FilterClause(ref=yf, op=FilterOp.EQ, value="@period:current_year"))
        if mf:
            out.append(FilterClause(ref=mf, op=FilterOp.LTE, value="@period:current_month"))
    elif re.search(r"\b(this|current) month\b", low) and yf and mf:
        out.append(FilterClause(ref=yf, op=FilterOp.EQ, value="@period:current_year"))
        out.append(FilterClause(ref=mf, op=FilterOp.EQ, value="@period:current_month"))
    elif re.search(r"\b(last|previous|prior) year\b", low) and yf:
        out.append(FilterClause(ref=yf, op=FilterOp.EQ, value="@period:last_year"))
    elif re.search(r"\b(this|current)( calendar)? year\b", low) and yf:
        out.append(FilterClause(ref=yf, op=FilterOp.EQ, value="@period:current_year"))
    return out


def _parse_filters(
    request: str, catalog: SemanticCatalog, entity: str | None = None
) -> list[FilterClause]:
    """Rule-based, deterministic filter extraction for the common HR phrasings.
    `entity` (when known) scopes generic value filters to the report's entity so a
    value isn't filtered on a different entity's lookalike column."""
    low = request.lower()
    out: list[FilterClause] = []

    # status: "active employees", "resigned staff", … First try the values the
    # catalogue actually carries (correct casing). If none match but the prompt
    # clearly names a known status word the tenant's data lacks (e.g. "resigned"
    # when only "active" exists), STILL emit a filter on that word — so the answer
    # is honest (0 resigned) instead of silently counting everyone.
    sf = _status_field(catalog)
    if sf:
        values = _status_values(sf[1])
        chosen = None
        # 1. Match an ACTUAL stored value (correct casing) named in the prompt.
        for value in values:
            toks = re.findall(r"[a-z0-9]+", _norm(value))
            if toks and all(re.search(rf"\b{re.escape(t)}\b", low) for t in toks):
                chosen = value
                break
        # 2. Else recognise a status word/stem ("resigning", "vacated", …) and map
        #    it to its canonical token — preferring a stored value of the same
        #    token (casing), else the token itself (→ honest 0 if the data lacks it).
        if chosen is None:
            for rx, token in _STATUS_SYNONYMS:
                if rx.search(low):
                    chosen = next((v for v in values if _norm(v) == _norm(token)), token)
                    break
        if chosen is not None:
            out.append(FilterClause(ref=sf[0], op=FilterOp.EQ, value=chosen))

    # tenure: "more than 2 years (of service)", "over 5 years", "at least 3 years"
    tf = _tenure_field(catalog)
    if tf:
        m = re.search(
            r"\b(more than|over|greater than|at least|>=?|above)\s*(\d+(?:\.\d+)?)\s*year", low
        )
        if m:
            op = FilterOp.GTE if m.group(1) in ("at least", ">=") else FilterOp.GT
            out.append(FilterClause(ref=tf[0], op=op, value=float(m.group(2))))

    # time/period block — "this month", "YTD", "joined in the last 12 months", …
    out.extend(_parse_period(request, catalog))

    # generic value filters — "only permanent", "male", "Core - 1 grade", a branch:
    # any DIMENSION of the report's entity whose introspected sample value the
    # prompt names. Scoped to `entity` so it doesn't filter a lookalike column on
    # another entity (e.g. a summary mart's gender).
    if entity:
        out.extend(_parse_value_filters(request, catalog, {c.ref for c in out}, entity))
    return out


def _parse_value_filters(
    request: str, catalog: SemanticCatalog, skip: set[str], entity: str
) -> list[FilterClause]:
    """Match a prompt against the ACTUAL values of the ENTITY's low-cardinality
    dimensions (catalogue `sample_values`) and emit equality filters — so "only
    permanent", "male staff", "Core - 1 grade", "Colombo branch" filter the right
    column. A value matches only when ALL its tokens appear in the prompt (precise).
    Status-like dimensions are handled separately; generic-noun values ("staff")
    and lone short tokens are ignored to avoid false matches."""
    ptoks = set(re.findall(r"[a-z0-9]+", request.lower()))
    out: list[FilterClause] = []
    used = set(skip)
    for ref, f in catalog.field_index().items():
        if ref in used or f.role != FieldRole.DIMENSION or _entity_key(ref, catalog) != entity:
            continue
        if ref.endswith(".status") or "status" in _norm(f.label):
            continue  # status is resolved by the status block (incl. synonyms)
        for v in (getattr(f, "sample_values", None) or []):
            vtoks = re.findall(r"[a-z0-9]+", str(v).lower())
            if not vtoks:
                continue
            if len(vtoks) == 1 and (len(vtoks[0]) < 3 or vtoks[0] in (_GENERIC_NOUN | _FILLER)):
                continue  # too trivial / generic to match safely (e.g. "staff", "a")
            if all(t in ptoks for t in vtoks):
                out.append(FilterClause(ref=ref, op=FilterOp.EQ, value=v))
                used.add(ref)
                break
    return out


_PERIOD_LABELS = {
    "@period:current_year": "this year",
    "@period:last_year": "last year",
    "@period:current_month": "this month",
}


def _describe(clause: FilterClause, catalog: SemanticCatalog) -> str:
    fld = catalog.field_index().get(clause.ref)
    label = fld.label if fld else clause.ref
    sym = {FilterOp.EQ: "=", FilterOp.GT: ">", FilterOp.GTE: "≥", FilterOp.LT: "<", FilterOp.LTE: "≤"}
    val = clause.value
    if isinstance(val, str) and val.startswith("@period:"):
        if val.startswith("@period:months_ago:"):
            val = f"last {val.rsplit(':', 1)[1]} months"
        elif val.startswith("@period:days_ago:"):
            val = f"last {val.rsplit(':', 1)[1]} days"
        else:
            val = _PERIOD_LABELS.get(val, val)
        return f"{label}: {val}"
    return f"{label} {sym.get(clause.op, clause.op.value)} {val}"


def _group_ref(request: str, catalog: SemanticCatalog) -> str | None:
    """The dimension to group by — named after 'by'/'per'/'grouped by' ('headcount
    by department') or with the '<dim>-wise' idiom ('department wise breakdown').
    Searched across ALL catalogue dimensions (the group key often sits outside the
    field-list region)."""
    low = request.lower()
    m = re.search(r"\b(?:grouped by|by|per)\b", low)
    if m:
        tail_text = request[m.end():]
    else:
        wm = re.search(r"\bwise\b", low)  # "department wise", "grade-wise", "category wise"
        if not wm:
            return None
        before = request[: wm.start()].strip(" -")
        tail_text = " ".join(before.split()[-2:])  # the 1-2 words right before "wise"
    tail = _norm(tail_text)
    if not tail:
        return None
    dims = [
        (ref, f) for ref, f in catalog.field_index().items() if f.role == FieldRole.DIMENSION
    ]
    # 1) precise: a dimension label that appears verbatim in the tail.
    best = None
    for ref, f in dims:
        ln = _norm(f.label)
        if ln and len(ln) >= 4 and ln in tail and (best is None or len(ln) > best[1]):
            best = (ref, len(ln))
    if best:
        return best[0]
    # 2) fuzzy: closest dimension to the tail phrase ("employment category" →
    #    Employee Category), so near-synonyms still resolve to a group axis.
    cands = [(ref, _norm(f.label), _norm(ref.split(".", 1)[-1])) for ref, f in dims]
    ref, score = _local_match(tail_text, cands)
    return ref if ref and score >= _MATCH_MIN else None


_ADD_RE = re.compile(r"\b(?:add|also|include|append|plus|show)\b\s+(.+)", re.I)
_RM_RE = re.compile(r"\b(?:remove|drop|delete|without|exclude|hide)\b\s+(.+)", re.I)


def refine_spec(current: dict, message: str, catalog: SemanticCatalog) -> "HybridResult | None":
    """Apply a refinement to the CURRENT report deterministically (no LLM):
    "only active" / "more than 3 years" → add a filter; "add department" → add a
    field; "remove gender" → drop a field. Returns None when nothing applies (so
    the caller can fall back to the LLM, e.g. for a regrouping refinement)."""
    try:
        spec = DataSpec.model_validate(current)
    except Exception:  # noqa: BLE001 - malformed current spec
        return None

    cands = _candidates(catalog)
    changes: list[str] = []
    added: list[str] = []
    unmatched: list[str] = []

    # Filters ("only active", "more than 5 years", "only permanent") — scoped to the
    # current report's entity so value filters hit the right column.
    for f in _parse_filters(message, catalog, spec.entity):
        if not any(x.ref == f.ref and x.op == f.op for x in spec.filters):
            spec.filters.append(f)
            changes.append("filter " + _describe(f, catalog))

    rm = _RM_RE.search(message)
    if rm:
        for ph in _split_phrases(rm.group(1)):
            if _is_noise_phrase(ph):
                continue
            ref, sc = _local_match(_fold_text(ph), cands)
            if ref and sc >= _MATCH_MIN and any(fs.ref == ref for fs in spec.fields):
                spec.fields = [fs for fs in spec.fields if fs.ref != ref]
                changes.append("removed " + _label_of(ref, catalog))
            else:
                unmatched.append(ph)

    add = _ADD_RE.search(message)
    if add:
        for ph in _split_phrases(add.group(1)):
            if _is_noise_phrase(ph):
                continue
            ref, sc = _local_match(_fold_text(ph), cands)
            if ref and sc >= _MATCH_MIN:
                if not any(fs.ref == ref for fs in spec.fields):
                    spec.fields.append(FieldSelection(ref=ref, label=_label_of(ref, catalog)))
                    added.append(ref)
                    changes.append("added " + _label_of(ref, catalog))
            else:
                unmatched.append(ph)

    # Regroup / breakdown: "breakdown by department", "group by grade", "by gender".
    # Break the current numbers down by that dimension (counting records if the
    # report has no measure yet), so a follow-up continues the previous question.
    grp = _group_ref(message, catalog)
    if grp is not None and grp not in spec.group_by:
        lbl = _label_of(grp, catalog)
        if not any(fs.ref == grp for fs in spec.fields):
            spec.fields.insert(0, FieldSelection(ref=grp, label=lbl))
        spec.group_by = [grp]
        fidx = catalog.field_index()
        has_measure = bool(spec.aggregations) or any(
            fs.ref.startswith("metric.")
            or (fidx.get(fs.ref) and fidx[fs.ref].role == FieldRole.MEASURE)
            for fs in spec.fields
        )
        if not has_measure:
            cnt = _count_capable_ref(catalog, spec.entity)
            if cnt:
                spec.aggregations = [AggregationSpec(ref=cnt, fn=AggFn.COUNT, label="Count")]
        changes.append("broke down by " + lbl)

    if not changes:
        return None  # nothing actionable — caller may clarify or fall back
    return HybridResult(
        data_spec=spec,
        matched=[FieldMatch("", r, _label_of(r, catalog), 1.0) for r in added],
        unmatched=unmatched,
        filters=[_describe(c, catalog) for c in spec.filters],
        confidence=0.9,
        rationale="Updated report: " + ", ".join(changes) + ".",
    )


def _cluster_finder(catalog: SemanticCatalog):
    """Return a `find(entity_key)` that maps an entity to its joinable-cluster root,
    via union-find over the catalogue's declared joins. Two entities in the same
    cluster can be combined in one report; entities in different clusters cannot."""
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
    return find


def _rank_matches(phrase: str, cands: list[tuple[str, str, str]]) -> list[tuple[str, float]]:
    """All candidate refs for a phrase, scored 0..1, sorted best-first with a
    DETERMINISTIC tie-break: a governed metric beats a raw field (concept-lock),
    then catalogue order (core entities precede standalone summary entities, as the
    catalogue lists them). So the same phrase always ranks the same way — the
    routing is reproducible (consistency) and the top is the canonical concept."""
    hn = _mnorm(phrase)  # synonym-folded to match the folded candidate targets
    if not hn:
        return []
    best: dict[str, float] = {}
    first_idx: dict[str, int] = {}
    for i, (ref, ln, rn) in enumerate(cands):
        s = 0.0
        for target in (ln, rn):
            if not target:
                continue
            if hn == target:
                s = max(s, 1.0)
            elif len(target) >= 4 and (target in hn or hn in target):
                s = max(s, 0.92)
            else:
                s = max(s, difflib.SequenceMatcher(None, hn, target).ratio())
        if s > best.get(ref, 0.0):
            best[ref] = s
        first_idx.setdefault(ref, i)
    return sorted(
        best.items(),
        key=lambda kv: (-kv[1], 0 if kv[0].startswith("metric.") else 1, first_idx[kv[0]]),
    )


def _dominant_cluster(
    matched: list[FieldMatch], catalog: SemanticCatalog
) -> tuple[list[FieldMatch], list[FieldMatch]]:
    """Keep the matched fields in the single largest joinable entity-cluster; return
    the rest as dropped. A noise word ('employees') can fuzzy-hit a standalone
    summary entity that can't be joined with the real cluster; this drops that
    spurious match instead of failing the whole resolve."""
    find = _cluster_finder(catalog)
    groups: dict[str, list[FieldMatch]] = {}
    for m in matched:
        groups.setdefault(find(_entity_key(m.ref, catalog)), []).append(m)
    if len(groups) <= 1:
        return matched, []
    dom = max(groups, key=lambda k: len(groups[k]))
    kept = [m for m in matched if find(_entity_key(m.ref, catalog)) == dom]
    dropped = [m for m in matched if find(_entity_key(m.ref, catalog)) != dom]
    return kept, dropped


def _identifier_field(catalog: SemanticCatalog, entity_key: str) -> str | None:
    """A representative identifying dimension for an entity — a 'name' field if one
    exists, else its first dimension. Used to give a filter-only prompt some columns."""
    fidx = catalog.field_index()
    for ref, f in fidx.items():
        if ref.startswith(entity_key + ".") and f.role == FieldRole.DIMENSION and "name" in _norm(f.label):
            return ref
    for ref, f in fidx.items():
        if ref.startswith(entity_key + ".") and f.role == FieldRole.DIMENSION:
            return ref
    return None


def _filter_only_spec(
    filters: list[FilterClause], catalog: SemanticCatalog
) -> "HybridResult | None":
    """Build a list report for a prompt that carries filters but names no fields
    ("employees who joined in the last 12 months", "active employees"): show a
    representative identifier plus each filtered field of that entity."""
    ent = _entity_key(filters[0].ref, catalog)
    ident = _identifier_field(catalog, ent)
    if not ident:
        return None
    fidx = catalog.field_index()
    fields = [FieldSelection(ref=ident, label=_label_of(ident, catalog))]
    for f in filters:
        if f.ref in fidx and f.ref != ident and _entity_key(f.ref, catalog) == ent:
            fields.append(FieldSelection(ref=f.ref, label=_label_of(f.ref, catalog)))
    spec = DataSpec(entity=ent, fields=fields, filters=filters)
    return HybridResult(
        data_spec=spec,
        matched=[FieldMatch("", fs.ref, fs.label or fs.ref, 1.0) for fs in fields],
        filters=[_describe(c, catalog) for c in filters],
        confidence=0.8,
        rationale=f"Listed {_label_of(ident, catalog)} with {len(filters)} filter(s).",
    )


def _period_grained_entities(catalog: SemanticCatalog) -> set[str]:
    """Entity keys that hold one row per subject PER PERIOD (attendance, leave,
    payroll marts) — detected by an explicit period_grain or year+month/period
    dimensions. Measures from these must be aggregated when combined with a
    non-period dimension, else the join explodes to a row per month."""
    out: set[str] = set()
    for e in catalog.entities:
        if getattr(e, "period_grain", None):
            out.add(e.key)
            continue
        labels = [_norm(f.label) for f in e.fields if f.role == FieldRole.DIMENSION]
        if any("year" in ln for ln in labels) and any(("month" in ln or "period" in ln) for ln in labels):
            out.add(e.key)
    return out


def _count_capable_ref(catalog: SemanticCatalog, entity_key: str) -> str | None:
    """A measure in `entity_key` that can be COUNTed (e.g. employee.headcount over
    the always-present employee_sk) — used to count records without depending on a
    possibly-empty grouping column."""
    for ref, f in catalog.field_index().items():
        if (
            ref.startswith(entity_key + ".")
            and f.role == FieldRole.MEASURE
            and AggFn.COUNT in (f.allowed_aggregations or [])
        ):
            return ref
    return None


def _bare_count_spec(
    filters: list[FilterClause], catalog: SemanticCatalog, fidx: dict
) -> tuple[DataSpec, str, str] | None:
    """Build an ungrouped COUNT report for "how many active employees" style
    prompts. Prefers a governed count metric; else counts a count-capable measure
    (e.g. `employee.headcount`) in the entity the filters target, defaulting to the
    employee entity. Returns (spec, ref, label) or None when nothing countable
    exists in the catalogue."""
    hc = next((m for m in catalog.metrics if getattr(m, "kind", None) == "count"), None)
    if hc is not None:
        ref = f"metric.{hc.key}"
        spec = DataSpec(
            entity=_entity_key(ref, catalog),
            fields=[FieldSelection(ref=ref, label=hc.label)],
            filters=filters,
        )
        return spec, ref, hc.label

    ent_key = filters[0].ref.split(".", 1)[0] if filters else "employee"
    for ref, f in fidx.items():
        if (
            ref.startswith(ent_key + ".")
            and f.role == FieldRole.MEASURE
            and AggFn.COUNT in (f.allowed_aggregations or [])
        ):
            spec = DataSpec(
                entity=ent_key,
                fields=[],
                aggregations=[AggregationSpec(ref=ref, fn=AggFn.COUNT, label="Count")],
                filters=filters,
            )
            return spec, ref, f.label
    return None


def hybrid_resolve(request: str, catalog: SemanticCatalog) -> HybridResult | None:
    """Resolve a prompt deterministically. Returns None when nothing maps at all
    (so the caller can fall to the LLM); otherwise a HybridResult whose
    `confidence` and `unmatched` let the caller decide whether to serve it or ask
    the user to confirm / fall back."""
    cands = _candidates(catalog)
    fidx = catalog.field_index()

    region = _field_region(request)
    phrases = _split_phrases(region)
    unmatched: list[str] = []

    # Pass 1 — rank each phrase's candidates (deterministic) and take the best.
    ranked_by_phrase: dict[str, list[tuple[str, float]]] = {}
    provisional: list[tuple[str, str, float]] = []  # (phrase, ref, score)
    for ph in phrases:
        if len(_norm(ph)) < 3 or _is_noise_phrase(ph):
            continue  # connective / generic / aggregation / operand text — not a field
        ranked = [(r, s) for (r, s) in _rank_matches(ph, cands) if s >= _MATCH_MIN]
        if not ranked:
            unmatched.append(ph)
            continue
        ranked_by_phrase[ph] = ranked
        provisional.append((ph, ranked[0][0], ranked[0][1]))

    # Pass 2 — concept-lock to the dominant ENTITY: if a phrase's best match sits in
    # a different entity from the one most other matches agree on, prefer a
    # same-entity alternative within margin. Keeps "name, department, basic salary"
    # entirely in Employee (no needless Payroll join), while a payroll report
    # ("basic, gross, deductions by group") keeps the Payroll fields. Entity-level,
    # not cluster-level, because joinable entities share a cluster yet a same-entity
    # match still avoids an unnecessary join.
    counts = Counter(_entity_key(ref, catalog) for _, ref, _ in provisional)
    dominant = counts.most_common(1)[0][0] if counts else None
    matched: list[FieldMatch] = []
    seen_refs: set[str] = set()
    for ph, ref, score in provisional:
        if dominant is not None and _entity_key(ref, catalog) != dominant:
            for alt_ref, alt_s in ranked_by_phrase[ph]:
                if _entity_key(alt_ref, catalog) == dominant and alt_s >= score - _CLUSTER_MARGIN:
                    ref, score = alt_ref, alt_s
                    break
        if ref in seen_refs:
            continue
        seen_refs.add(ref)
        matched.append(FieldMatch(ph, ref, _label_of(ref, catalog), round(score, 2)))

    # Drop any still-cross-cluster stragglers (no same-cluster alternative existed).
    matched, dropped = _dominant_cluster(matched, catalog)
    unmatched += [m.phrase for m in dropped]

    # Structure: filters, grouping, aggregation (computed from the full prompt).
    # The report's entity (dominant among matches, else a group dim's, else the
    # primary entity) scopes generic value filters to the right columns.
    group_ref0 = _group_ref(request, catalog)
    ent_counts = Counter(_entity_key(m.ref, catalog) for m in matched)
    target_entity = (
        ent_counts.most_common(1)[0][0] if ent_counts
        else _entity_key(group_ref0, catalog) if group_ref0
        else (catalog.entities[0].key if catalog.entities else None)
    )
    filters = _parse_filters(request, catalog, target_entity)
    agg = _detect_agg(request.lower())
    group_ref = group_ref0
    # "breakdown by X" / "X-wise breakdown" with no explicit measure means count.
    if group_ref and not agg and re.search(r"\bbreak\s?down\b", request.lower()):
        agg = AggFn.COUNT

    metric_matches = [m for m in matched if m.ref.startswith("metric.")]
    field_matches = [m for m in matched if not m.ref.startswith("metric.")]
    measures = [(m.ref, fidx[m.ref]) for m in field_matches if fidx[m.ref].role == FieldRole.MEASURE]
    rollup = bool(agg and group_ref and not metric_matches)

    # Bare count: "how many active employees", "active user count", "number of
    # staff" — a COUNT with optional filters but NO grouping dimension and no named
    # fields. Resolve to an ungrouped count rather than falling through to the LLM.
    if not matched and agg == AggFn.COUNT and not group_ref:
        bc = _bare_count_spec(filters, catalog, fidx)
        if bc is not None:
            spec, ref, label = bc
            return HybridResult(
                data_spec=spec,
                matched=[FieldMatch("", ref, label, 1.0)],
                filters=[_describe(c, catalog) for c in filters],
                confidence=0.9,
                rationale="Counted records"
                + (f" with {len(filters)} filter(s)" if filters else "")
                + ".",
            )

    # Filter-only: a prompt that named NO fields (and none were left unmatched) but
    # carries filters — "employees who joined in the last 12 months", "active
    # employees". Build a sensible list rather than falling to the LLM. Gated on
    # `not unmatched` so it never masks a field the user named that we couldn't map.
    if not matched and not agg and not group_ref and filters and not unmatched:
        fo = _filter_only_spec(filters, catalog)
        if fo is not None:
            return fo

    # Nothing to build: no fields AND not a "<agg> by <dimension>" roll-up.
    if not matched and not (agg and group_ref):
        return None

    aggregations: list[AggregationSpec] = []
    group_by: list[str] = []

    if metric_matches:
        # Shape M: governed metric(s), grouped by a dimension if named. The compiler
        # treats a metric ref as aggregated and auto-groups the selected dimensions,
        # so no explicit aggregation/group_by is set here.
        fields = []
        if group_ref:
            fields.append(FieldSelection(ref=group_ref, label=_label_of(group_ref, catalog)))
        for d in field_matches:
            if fidx[d.ref].role == FieldRole.DIMENSION and d.ref != group_ref:
                fields.append(FieldSelection(ref=d.ref, label=d.label))
        fields += [FieldSelection(ref=m.ref, label=m.label) for m in metric_matches]
        entity = _entity_key(group_ref, catalog) if group_ref else _entity_key(metric_matches[0].ref, catalog)
    elif rollup:
        # roll-up: <measure(s)> by <dimension>, or count by <dimension>
        entity = group_ref.split(".", 1)[0]
        fields = [FieldSelection(ref=group_ref, label=_label_of(group_ref, catalog))]
        group_by = [group_ref]
        if measures:
            aggregations = [
                AggregationSpec(ref=r, fn=agg, label=f"{agg.value.title()} {f.label}")
                for (r, f) in measures
            ]
        else:
            # Count records — over a guaranteed-populated key (e.g. employee_sk via
            # the headcount field), NOT the grouping column, which may be empty
            # (a data-capture gap) and would make every group count 0.
            cnt = _count_capable_ref(catalog, entity) or group_ref
            aggregations = [AggregationSpec(ref=cnt, fn=AggFn.COUNT, label="Count")]
    else:
        # Plain field list. If it mixes a dimension (e.g. Employee Name) with
        # measures from a PERIOD-GRAINED entity (attendance/leave/payroll — many
        # rows per employee per month), aggregate (SUM) those measures grouped by
        # the dimension(s) so the report is one row per employee, not a row per
        # month (which would explode the join and read as blank/duplicated).
        dim_matches = [m for m in matched if fidx[m.ref].role == FieldRole.DIMENSION]
        pg = _period_grained_entities(catalog)
        pg_measures = [(r, f) for (r, f) in measures if _entity_key(r, catalog) in pg]
        if dim_matches and pg_measures and not agg:
            fields = [FieldSelection(ref=d.ref, label=d.label) for d in dim_matches]
            group_by = [d.ref for d in dim_matches]
            aggregations = [
                AggregationSpec(ref=r, fn=AggFn.SUM, label=f"Total {f.label}")
                for (r, f) in pg_measures
            ]
            entity = _entity_key(dim_matches[0].ref, catalog)
        else:
            fields = [FieldSelection(ref=m.ref, label=m.label) for m in matched]
            entity = _entity_key(matched[0].ref, catalog)

    spec = DataSpec(
        entity=entity, fields=fields, filters=filters,
        group_by=group_by, aggregations=aggregations,
    )

    # Confidence: coverage of the named fields, plus signal from filters/grouping.
    total = len(matched) + len(unmatched)
    coverage = (len(matched) / total) if total else (1.0 if (agg and group_ref) else 0.0)
    confidence = round(min(0.95, 0.55 + 0.4 * coverage + (0.1 if (filters or group_ref) else 0.0)), 2)

    if metric_matches:
        bits = [f"{len(metric_matches)} metric(s)"]
        if group_ref:
            bits.append(f"by {_label_of(group_ref, catalog)}")
    elif rollup and not measures:
        bits = [f"count grouped by {_label_of(group_ref, catalog)}"]
    else:
        bits = [f"{len(matched)} field(s)"]
        if rollup:
            bits.append(f"grouped by {_label_of(group_ref, catalog)}")
    if filters:
        bits.append(f"{len(filters)} filter(s)")
    rationale = "Matched " + ", ".join(bits) + "."

    return HybridResult(
        data_spec=spec,
        matched=matched,
        unmatched=unmatched,
        filters=[_describe(c, catalog) for c in filters],
        confidence=confidence,
        rationale=rationale,
    )
