"""MintHRM Ingestion Ontology Layer.

Mirrors mint-analytics data_intake/ontology.py for the HR domain.

For every source header the mapper couldn't resolve, this layer asks:
"do we *recognise* the business concept even though we can't map it?"

Wired concepts (status="wired") have at least one canonical landing field
and produce no warning — the alias-mapping path already handles them.

Not-wired concepts (status="not_wired") surface a ``ConceptWarning`` on
``OrchestrationResult.concept_warnings`` so the review UI can tell the
analyst "we see this column but don't know where to put it yet".

Determinism guarantees:
  * Word-boundary regex per synonym — "overtime" matches "overtime" but
    not "overtime_pay" unless explicitly listed.
  * Concept ids are stable; new concepts are appended, never reordered.
  * No I/O, no LLM, no engine call — pure data + functions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# ── Data-classes ──────────────────────────────────────────────────


@dataclass(frozen=True)
class Concept:
    """Declared HR business concept the system can recognise in source headers.

    ``status``:
      * ``wired``     — canonical_targets already covers this concept.
      * ``not_wired`` — concept is real and recognised, but no canonical
                        landing field exists yet.
    """
    concept_id: str
    status: str                        # "wired" | "not_wired"
    description: str
    synonyms: Tuple[str, ...] = ()
    related_canonical_fields: Tuple[str, ...] = ()
    fallback_message: Optional[str] = None


@dataclass(frozen=True)
class ConceptMatch:
    header: str
    concept_id: str
    matched_synonym: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "header":          self.header,
            "concept_id":      self.concept_id,
            "matched_synonym": self.matched_synonym,
        }


@dataclass(frozen=True)
class ConceptWarning:
    concept_id: str
    status: str
    headers_matched: Tuple[str, ...]
    message: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "concept_id":      self.concept_id,
            "status":          self.status,
            "headers_matched": list(self.headers_matched),
            "message":         self.message,
        }


# ── Registry ──────────────────────────────────────────────────────

_REGISTRY: Tuple[Concept, ...] = (

    # ── Wired — already covered by canonical targets ───────────────

    Concept(
        concept_id="employee_identity",
        status="wired",
        description="Employee ID / code / number — the primary key of the employee master.",
        synonyms=(
            "employee id", "emp id", "emp no", "employee number",
            "employee code", "staff id", "staff no", "personnel no",
        ),
        related_canonical_fields=("employee_id",),
    ),
    Concept(
        concept_id="payroll_earnings",
        status="wired",
        description="Gross pay, basic salary, allowances, overtime — covered by hr.payroll_detail.",
        synonyms=(
            "basic salary", "basic pay", "gross salary", "gross pay",
            "allowances", "overtime pay", "ot pay", "bonuses", "incentive",
        ),
        related_canonical_fields=(
            "basic_salary", "gross_salary", "allowances", "overtime_pay", "bonuses",
        ),
    ),
    Concept(
        concept_id="payroll_deductions",
        status="wired",
        description="Tax, statutory deductions — covered by hr.payroll_detail.",
        synonyms=(
            "tax", "paye", "income tax", "epf", "etf", "socso",
            "deductions", "other deductions", "net salary", "net pay",
        ),
        related_canonical_fields=(
            "tax_deduction", "other_deductions", "net_salary",
        ),
    ),
    Concept(
        concept_id="attendance_time",
        status="wired",
        description="Check-in / check-out, work hours — covered by hr.attendance.",
        synonyms=(
            "check in", "check out", "time in", "time out",
            "clock in", "clock out", "work hours", "hours worked",
            "late minutes", "overtime minutes",
        ),
        related_canonical_fields=(
            "check_in", "check_out", "work_hours",
            "late_minutes", "overtime_minutes",
        ),
    ),
    Concept(
        concept_id="leave_entitlement",
        status="wired",
        description="Leave days entitled, taken, balance — covered by hr.leave_balance.",
        synonyms=(
            "leave balance", "leave entitlement", "annual leave",
            "sick leave", "leave taken", "leave remaining",
            "days entitled", "days taken",
        ),
        related_canonical_fields=("entitled", "taken", "balance"),
    ),
    Concept(
        concept_id="performance_score",
        status="wired",
        description="Performance rating / score — covered by hr.performance_review.",
        synonyms=(
            "performance score", "overall score", "appraisal score",
            "kpi score", "rating", "performance rating",
        ),
        related_canonical_fields=("overall_score", "rating"),
    ),

    # ── Not-wired — recognised but no canonical landing yet ────────

    Concept(
        concept_id="salary_band",
        status="not_wired",
        description=(
            "Salary band / pay scale / grade range. "
            "hr.designation has 'grade' but not the numeric band boundaries."
        ),
        synonyms=(
            "salary band", "pay band", "pay scale", "salary range",
            "min salary", "max salary", "salary min", "salary max",
            "pay grade min", "pay grade max",
        ),
        fallback_message=(
            "Salary band / pay scale headers are recognised but not wired. "
            "The closest canonical field is hr.designation.grade (text grade label). "
            "Add canonical fields for numeric band boundaries before automating."
        ),
    ),
    Concept(
        concept_id="probation_status",
        status="not_wired",
        description=(
            "Probation period tracking: probation end date, probation status. "
            "hr.employee_master has date_confirmed but not a probation_status flag."
        ),
        synonyms=(
            "probation", "probation status", "probation end",
            "probation period", "on probation", "confirmed",
        ),
        fallback_message=(
            "Probation status headers are recognised but not wired. "
            "The closest canonical field is hr.employee_master.date_confirmed. "
            "Map manually or extend the canonical schema."
        ),
    ),
    Concept(
        concept_id="disciplinary_record",
        status="not_wired",
        description=(
            "Disciplinary actions, warnings, show-cause letters. "
            "No canonical target exists for disciplinary records yet."
        ),
        synonyms=(
            "disciplinary", "warning", "show cause", "misconduct",
            "suspension", "disciplinary action", "infraction",
        ),
        fallback_message=(
            "Disciplinary record headers are recognised but not wired. "
            "No canonical target covers disciplinary actions today. "
            "Add hr.disciplinary_record to canonical_targets.py before automating."
        ),
    ),
    Concept(
        concept_id="benefits_enrollment",
        status="not_wired",
        description=(
            "Employee benefits: medical, dental, insurance enrollment. "
            "No canonical target exists for benefits enrollment yet."
        ),
        synonyms=(
            "medical", "dental", "insurance", "benefit", "benefits",
            "medical insurance", "health insurance", "group insurance",
            "enrollment", "enrolled",
        ),
        fallback_message=(
            "Benefits enrollment headers are recognised but not wired. "
            "No canonical target covers employee benefits today. "
            "Add hr.benefits_enrollment to canonical_targets.py before automating."
        ),
    ),
    Concept(
        concept_id="shift_schedule",
        status="not_wired",
        description=(
            "Shift patterns, rosters, scheduled hours. "
            "hr.attendance has shift_id but no shift schedule / roster target."
        ),
        synonyms=(
            "shift", "shift name", "shift type", "roster",
            "scheduled hours", "shift schedule", "work schedule",
            "shift pattern",
        ),
        fallback_message=(
            "Shift / roster headers are recognised but not wired. "
            "hr.attendance.shift_id captures the FK but no canonical target "
            "covers shift schedules or rosters today."
        ),
    ),
    Concept(
        concept_id="cost_center",
        status="not_wired",
        description=(
            "Cost centre allocation for payroll / headcount reporting. "
            "hr.employee_master has branch_id but not a cost_center canonical field."
        ),
        synonyms=(
            "cost center", "cost centre", "cc", "cost code",
            "cost center code", "cost centre code",
        ),
        fallback_message=(
            "Cost centre headers are recognised but not wired. "
            "The closest canonical field is hr.employee_master.branch_id. "
            "Add cost_center_id to hr.employee_master if cost-centre-level "
            "reporting is required."
        ),
    ),
    Concept(
        concept_id="fx_currency",
        status="not_wired",
        description=(
            "Multi-currency payroll: original currency, exchange rate. "
            "The canonical schema is currency-agnostic today."
        ),
        synonyms=(
            "currency", "original currency", "fx rate", "exchange rate",
            "fx", "rate of exchange", "reporting currency",
        ),
        fallback_message=(
            "Multi-currency / FX headers are recognised but not wired. "
            "Numbers are assumed to be in the tenant's reporting currency. "
            "No canonical field for original currency or exchange rate exists yet."
        ),
    ),
)


# ── Synonym index (compiled once at module load) ──────────────────


def _compile_synonym(s: str) -> re.Pattern[str]:
    parts = re.split(r"\s+", s.strip())
    body = r"\s+".join(re.escape(p) for p in parts if p)
    return re.compile(rf"\b{body}\b", re.IGNORECASE)


_SYNONYM_INDEX: Tuple[Tuple[str, str, re.Pattern[str]], ...] = tuple(
    (cap.concept_id, syn, _compile_synonym(syn))
    for cap in _REGISTRY
    for syn in cap.synonyms
)
_BY_ID: Dict[str, Concept] = {c.concept_id: c for c in _REGISTRY}


# ── Public API ────────────────────────────────────────────────────


def get_all_concepts() -> Tuple[Concept, ...]:
    return _REGISTRY


def get_concept(concept_id: str) -> Optional[Concept]:
    return _BY_ID.get(concept_id)


def detect_concepts(headers: List[str]) -> List[ConceptMatch]:
    """Return one ``ConceptMatch`` per (header, concept_id) hit."""
    if not headers:
        return []
    out: List[ConceptMatch] = []
    for h in headers:
        if not isinstance(h, str) or not h.strip():
            continue
        for cid, syn, pat in _SYNONYM_INDEX:
            if pat.search(h):
                out.append(ConceptMatch(header=h, concept_id=cid, matched_synonym=syn))
    return out


def warnings_for_unmapped_headers(
    unmapped_headers: List[str],
) -> List[ConceptWarning]:
    """Aggregate concept hits into one ``ConceptWarning`` per concept_id.

    Only ``not_wired`` concepts produce warnings.
    """
    if not unmapped_headers:
        return []
    by_concept: Dict[str, List[str]] = {}
    for m in detect_concepts(unmapped_headers):
        cap = _BY_ID.get(m.concept_id)
        if cap is None or cap.status != "not_wired":
            continue
        bucket = by_concept.setdefault(m.concept_id, [])
        if m.header not in bucket:
            bucket.append(m.header)

    out: List[ConceptWarning] = []
    for cid, headers in by_concept.items():
        cap = _BY_ID[cid]
        out.append(ConceptWarning(
            concept_id=cid,
            status=cap.status,
            headers_matched=tuple(headers),
            message=(
                cap.fallback_message
                or _DEFAULT_NOT_WIRED_MESSAGE.format(concept=cid)
            ),
        ))
    out.sort(key=lambda w: w.concept_id)
    return out


_DEFAULT_NOT_WIRED_MESSAGE = (
    "Headers matching the {concept!r} concept were recognised but "
    "the concept has no canonical landing field today. Map manually "
    "or extend the canonical schema before automating it."
)
