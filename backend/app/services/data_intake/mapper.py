"""Deterministic mapper for the MintHRM Data Intake layer.

Maps source headers in a profiled file to canonical fields of the chosen
HR target.  Pure and reproducible — no LLM, no row inspection, no network.

Confidence ladder (deterministic):

    canonical-name exact match     → 1.0
    tenant / customer override     → 1.0   (overrides win over both)
    alias match                    → 0.8
    no match                       → 0.0

Header normalisation lower-cases and strips non-alphanumerics, so
``"Emp. No."`` and ``"emp_no"`` collide on the same key.

Tenant overrides shape::

    {data_type: {canonical_field: [override_alias, ...]}}

Overrides are layered on top of the canonical registry; they never mutate it.

Ported from mint-analytics data_intake/mapper.py — domain changed to HR,
logic unchanged.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional, Sequence

from app.services.data_intake.canonical_targets import (
    UNKNOWN_DATA_TYPE,
    CanonicalTarget,
    get_target,
)
from app.services.data_intake.classifier import ClassificationResult

MATCH_CANONICAL = "canonical"
MATCH_OVERRIDE = "tenant_override"
MATCH_ALIAS = "alias"
MATCH_TEMPLATE_SUGGESTION = "template_suggestion"

CONFIDENCE_CANONICAL = 1.0
CONFIDENCE_OVERRIDE = 1.0
CONFIDENCE_ALIAS = 0.8

TenantOverrides = Mapping[str, Mapping[str, Sequence[str]]]


# ── Result types ──────────────────────────────────────────────────


@dataclass
class MappedField:
    canonical_field: str
    source_header: str
    match_kind: str       # MATCH_CANONICAL | MATCH_OVERRIDE | MATCH_ALIAS
    confidence: float
    required: bool
    dtype: str


@dataclass
class AmbiguousField:
    canonical_field: str
    chosen_source_header: str
    chosen_match_kind: str
    other_source_headers: list[str]


@dataclass
class MappingResult:
    data_type: str
    sheet_used: str
    mapped_fields: list[MappedField]
    unmapped_source_fields: list[str]
    missing_required_fields: list[str]
    ambiguous_fields: list[AmbiguousField]
    confidence_per_field: dict[str, float]
    mapping_confidence: float

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["mapping_confidence"] = round(self.mapping_confidence, 4)
        d["confidence_per_field"] = {
            k: round(v, 4) for k, v in self.confidence_per_field.items()
        }
        for m in d["mapped_fields"]:
            m["confidence"] = round(m["confidence"], 4)
        return d


# ── Public API ────────────────────────────────────────────────────


def build_mapping_result(
    profile: "FileProfile",  # noqa: F821
    classification: ClassificationResult,
    *,
    tenant_overrides: Optional[TenantOverrides] = None,
    tenant_config: Any = None,
) -> Optional[MappingResult]:
    """Return ``None`` for unknown / unclassifiable inputs; otherwise a
    deterministic mapping.

    When ``tenant_config`` is supplied its ``aliases`` are merged under
    ``tenant_overrides``.  Explicit ``tenant_overrides`` win on conflict.
    """
    if classification.detected_data_type == UNKNOWN_DATA_TYPE:
        return None
    target = get_target(classification.detected_data_type)
    if target is None:
        return None

    sheet = _pick_sheet(profile, classification.sheet_used)
    if sheet is None:
        return None

    merged_overrides = _merge_overrides(tenant_overrides, tenant_config)
    overrides_for_target: Mapping[str, Sequence[str]] = (
        merged_overrides.get(target.data_type, {}) if merged_overrides else {}
    )
    return _map(target, sheet, overrides_for_target)


# ── Internal ──────────────────────────────────────────────────────


def _merge_overrides(
    explicit: Optional[TenantOverrides],
    tenant_config: Any,
) -> Optional[dict[str, dict[str, list[str]]]]:
    config_aliases = (
        getattr(tenant_config, "aliases", None) if tenant_config is not None else None
    )
    if not explicit and not config_aliases:
        return None
    merged: dict[str, dict[str, list[str]]] = {}
    if config_aliases:
        for dt, fields in config_aliases.items():
            merged.setdefault(dt, {})
            for canonical, aliases in fields.items():
                merged[dt][canonical] = list(aliases)
    if explicit:
        for dt, fields in explicit.items():
            merged.setdefault(dt, {})
            for canonical, aliases in fields.items():
                merged[dt][canonical] = list(aliases)
    return merged


def _pick_sheet(profile: "FileProfile", name: str) -> Optional["SheetProfile"]:  # noqa: F821
    for s in profile.sheets:
        if s.name == name:
            return s
    return profile.sheets[0] if profile.sheets else None


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _kind_priority(kind: str) -> int:
    return {MATCH_OVERRIDE: 3, MATCH_CANONICAL: 2, MATCH_ALIAS: 1}.get(kind, 0)


def _confidence_for(kind: str) -> float:
    if kind == MATCH_CANONICAL:
        return CONFIDENCE_CANONICAL
    if kind == MATCH_OVERRIDE:
        return CONFIDENCE_OVERRIDE
    if kind == MATCH_ALIAS:
        return CONFIDENCE_ALIAS
    return 0.0


def _build_alias_index(
    target: CanonicalTarget,
    overrides: Mapping[str, Sequence[str]],
) -> dict[str, list[tuple[str, str]]]:
    """Returns ``norm(alias) -> [(canonical_field, match_kind), ...]`` in priority order."""
    idx: dict[str, list[tuple[str, str]]] = {}
    for f in target.fields:
        idx.setdefault(_norm(f.name), []).append((f.name, MATCH_CANONICAL))
        for a in f.aliases:
            idx.setdefault(_norm(a), []).append((f.name, MATCH_ALIAS))
    for canonical_name, alias_list in overrides.items():
        for a in alias_list:
            idx.setdefault(_norm(a), []).insert(0, (canonical_name, MATCH_OVERRIDE))
    return idx


def _map(
    target: CanonicalTarget,
    sheet: "SheetProfile",  # noqa: F821
    overrides: Mapping[str, Sequence[str]],
) -> MappingResult:
    alias_index = _build_alias_index(target, overrides)

    candidates: dict[str, list[tuple[str, str]]] = {}
    matched_headers: set[str] = set()

    for h in sheet.headers:
        if not h:
            continue
        entries = alias_index.get(_norm(h))
        if not entries:
            continue
        canonical_name, match_kind = entries[0]
        candidates.setdefault(canonical_name, []).append((h, match_kind))
        matched_headers.add(h)

    field_by_name = {f.name: f for f in target.fields}
    mapped: list[MappedField] = []
    ambiguous: list[AmbiguousField] = []

    for canonical_name, options in candidates.items():
        winner_idx = max(
            range(len(options)),
            key=lambda i: (_kind_priority(options[i][1]), -i),
        )
        winner_h, winner_kind = options[winner_idx]
        f = field_by_name[canonical_name]
        mapped.append(MappedField(
            canonical_field=canonical_name,
            source_header=winner_h,
            match_kind=winner_kind,
            confidence=_confidence_for(winner_kind),
            required=f.required,
            dtype=f.dtype,
        ))
        losers = [options[i][0] for i in range(len(options)) if i != winner_idx]
        if losers:
            ambiguous.append(AmbiguousField(
                canonical_field=canonical_name,
                chosen_source_header=winner_h,
                chosen_match_kind=winner_kind,
                other_source_headers=losers,
            ))

    cpf: dict[str, float] = {f.name: 0.0 for f in target.fields}
    for m in mapped:
        cpf[m.canonical_field] = m.confidence

    required_names = [f.name for f in target.fields if f.required]
    base_avg = sum(cpf.values()) / len(cpf) if cpf else 0.0
    if required_names:
        req_avg = sum(cpf[n] for n in required_names) / len(required_names)
        mapping_confidence = 0.6 * base_avg + 0.4 * req_avg
    else:
        mapping_confidence = base_avg

    missing_required = [n for n in required_names if cpf[n] == 0.0]
    unmapped = [h for h in sheet.headers if h and h not in matched_headers]

    mapped.sort(key=lambda m: m.canonical_field)
    ambiguous.sort(key=lambda a: a.canonical_field)

    return MappingResult(
        data_type=target.data_type,
        sheet_used=sheet.name,
        mapped_fields=mapped,
        unmapped_source_fields=unmapped,
        missing_required_fields=missing_required,
        ambiguous_fields=ambiguous,
        confidence_per_field=cpf,
        mapping_confidence=mapping_confidence,
    )
