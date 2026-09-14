"""Canonical target registry for the MintHRM Data Intake layer.

A ``CanonicalTarget`` describes a domain-specific shape that incoming HR
files can be mapped to.  Each target carries:

- ``data_type``   : stable identifier, e.g. ``hr.employee_master``.
- ``domain``      : always ``"hr"`` in this platform.
- ``description`` : human-readable label shown in the review UI.
- ``fields``      : ordered ``CanonicalField`` list — name, aliases,
                    required flag, dtype.
- ``natural_key`` : tuple of canonical field names used for duplicate
                    detection.  Empty tuple = event-style (no dedup).

Alias matching is case-insensitive after stripping non-alphanumeric
characters, so ``"Emp. No."`` and ``"emp_no"`` resolve to the same field.

Field names are derived from the staging columns already produced by
``extractors.py`` so the intake layer and the ETL layer speak the same
language.  When a customer uploads a flat file (CSV / Excel) the mapper
resolves their column headers to these canonical names; the row validator
then applies the same rules the ETL pipeline would.

Adding a new target:
  1. Append a ``_ct(...)`` call to ``CANONICAL_TARGETS``.
  2. Add a ``_validate_<data_type_slug>`` function in ``row_validator.py``
     and register it in ``_DISPATCH``.
  3. If the concept is not yet wired, add it to ``ontology.py`` with
     ``status="not_wired"`` until the validator exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

UNKNOWN_DATA_TYPE = "unknown"


# ── Core data-classes ─────────────────────────────────────────────


@dataclass(frozen=True)
class CanonicalField:
    name: str
    aliases: Tuple[str, ...] = ()
    required: bool = False
    dtype: str = "any"   # "string" | "numeric" | "date" | "any"


@dataclass(frozen=True)
class CanonicalTarget:
    data_type: str
    domain: str
    description: str
    fields: Tuple[CanonicalField, ...]
    natural_key: Tuple[str, ...] = ()

    def field_aliases(self) -> dict[str, str]:
        """Flat alias → canonical-field-name map (normalised keys)."""
        out: dict[str, str] = {}
        for f in self.fields:
            out[_norm(f.name)] = f.name
            for a in f.aliases:
                out[_norm(a)] = f.name
        return out

    def required_field_names(self) -> Tuple[str, ...]:
        return tuple(f.name for f in self.fields if f.required)


# ── Builder helpers ───────────────────────────────────────────────


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _ct(
    data_type: str,
    domain: str,
    description: str,
    *fields: CanonicalField,
    natural_key: Tuple[str, ...] = (),
) -> CanonicalTarget:
    return CanonicalTarget(
        data_type=data_type,
        domain=domain,
        description=description,
        fields=tuple(fields),
        natural_key=natural_key,
    )


def _f(
    name: str,
    *aliases: str,
    required: bool = False,
    dtype: str = "any",
) -> CanonicalField:
    return CanonicalField(
        name=name,
        aliases=tuple(aliases),
        required=required,
        dtype=dtype,
    )


# ── Canonical target registry ─────────────────────────────────────
#
# Each entry maps to one staging table produced by extractors.py.
# The aliases list covers the column labels customers actually use in
# their flat files — the more aliases, the higher the auto-mapping hit
# rate.  Required fields drive the classifier score and the row
# validator's mandatory-blank check.

CANONICAL_TARGETS: Tuple[CanonicalTarget, ...] = (

    # ── hr.employee_master ────────────────────────────────────────
    # Maps to: stg_employees
    # Natural key: employee_id (one row per employee)
    _ct(
        "hr.employee_master", "hr",
        "Employee master — one row per active or historical employee",
        _f("employee_id",
           "emp id", "emp no", "employee no", "employee number",
           "employee code", "staff id", "staff no", "personnel no",
           "emp code", "id",
           required=True),
        _f("first_name",
           "first name", "given name", "fname"),
        _f("last_name",
           "last name", "surname", "family name", "lname"),
        _f("full_name",
           "name", "full name", "employee name", "staff name"),
        _f("gender",
           "sex", "gender"),
        _f("date_of_birth",
           "dob", "birth date", "date of birth", "birthdate",
           dtype="date"),
        _f("national_id",
           "nic", "nric", "national id", "id number", "passport no"),
        _f("email",
           "email address", "work email", "corporate email"),
        _f("phone",
           "mobile", "phone number", "contact number", "tel"),
        _f("department_id",
           "dept id", "department id", "department code"),
        _f("designation_id",
           "designation id", "job title id", "position id"),
        _f("branch_id",
           "branch id", "branch code", "location id"),
        _f("employment_type",
           "emp type", "employment type", "contract type",
           "type of employment", "staff type",
           required=True),
        _f("employment_status",
           "status", "emp status", "employment status",
           "active status"),
        _f("date_joined",
           "doj", "join date", "date of joining", "start date",
           "commencement date", "hire date",
           required=True, dtype="date"),
        _f("date_confirmed",
           "confirmation date", "confirmed date", "probation end",
           dtype="date"),
        _f("date_resigned",
           "resignation date", "date resigned", "last working day",
           dtype="date"),
        _f("date_terminated",
           "termination date", "date terminated",
           dtype="date"),
        _f("reporting_to",
           "manager id", "supervisor id", "reports to",
           "line manager id"),
        natural_key=("employee_id",),
    ),

    # ── hr.department ─────────────────────────────────────────────
    # Maps to: stg_departments
    # Natural key: department_id
    _ct(
        "hr.department", "hr",
        "Department / division master",
        _f("department_id",
           "dept id", "department id", "department code", "dept code",
           required=True),
        _f("department_name",
           "dept name", "department name", "division", "name"),
        _f("parent_id",
           "parent dept id", "parent department", "parent id"),
        _f("head_employee_id",
           "dept head", "head id", "department head id"),
        _f("is_active",
           "active", "status"),
        natural_key=("department_id",),
    ),

    # ── hr.designation ────────────────────────────────────────────
    # Maps to: stg_designations
    # Natural key: designation_id
    _ct(
        "hr.designation", "hr",
        "Designation / job title master",
        _f("designation_id",
           "designation id", "job title id", "position id", "title id",
           required=True),
        _f("designation_title",
           "title", "job title", "designation", "position", "role"),
        _f("grade",
           "grade", "pay grade", "salary grade", "band"),
        _f("department_id",
           "dept id", "department id"),
        natural_key=("designation_id",),
    ),

    # ── hr.branch ─────────────────────────────────────────────────
    # Maps to: stg_branches
    # Natural key: branch_id
    _ct(
        "hr.branch", "hr",
        "Branch / office / location master",
        _f("branch_id",
           "branch id", "branch code", "location id", "office id",
           required=True),
        _f("branch_name",
           "branch name", "location", "office", "name"),
        _f("region",
           "region", "area", "zone"),
        _f("country",
           "country", "country code"),
        natural_key=("branch_id",),
    ),

    # ── hr.attendance ─────────────────────────────────────────────
    # Maps to: stg_attendance
    # Event-style: no natural key (one row per employee per day)
    _ct(
        "hr.attendance", "hr",
        "Daily attendance records — check-in / check-out per employee",
        _f("employee_id",
           "emp id", "emp no", "employee id", "employee code",
           required=True),
        _f("attendance_date",
           "date", "attendance date", "work date", "day",
           required=True, dtype="date"),
        _f("check_in",
           "check in", "time in", "clock in", "in time"),
        _f("check_out",
           "check out", "time out", "clock out", "out time"),
        _f("status",
           "attendance status", "status", "present absent"),
        _f("late_minutes",
           "late", "late minutes", "tardiness", "minutes late",
           dtype="numeric"),
        _f("early_leave_minutes",
           "early leave", "early departure", "early leave minutes",
           dtype="numeric"),
        _f("overtime_minutes",
           "ot minutes", "overtime", "overtime minutes",
           dtype="numeric"),
        _f("work_hours",
           "hours worked", "work hours", "total hours",
           dtype="numeric"),
        _f("shift_id",
           "shift", "shift id", "shift code"),
    ),

    # ── hr.leave_request ─────────────────────────────────────────
    # Maps to: stg_leave_requests
    # Natural key: employee_id + start_date + leave_type_id
    _ct(
        "hr.leave_request", "hr",
        "Leave requests — one row per approved or pending leave application",
        _f("employee_id",
           "emp id", "emp no", "employee id", "employee code",
           required=True),
        _f("leave_type_id",
           "leave type id", "leave type", "type id"),
        _f("start_date",
           "start date", "from date", "leave from", "leave start",
           required=True, dtype="date"),
        _f("end_date",
           "end date", "to date", "leave to", "leave end",
           dtype="date"),
        _f("days_requested",
           "days", "days requested", "no of days", "leave days",
           dtype="numeric"),
        _f("days_approved",
           "days approved", "approved days",
           dtype="numeric"),
        _f("status",
           "leave status", "status", "approval status"),
        _f("approved_by",
           "approved by", "approver id", "manager id"),
        _f("reason",
           "reason", "remarks", "purpose"),
        natural_key=("employee_id", "start_date", "leave_type_id"),
    ),

    # ── hr.leave_type ─────────────────────────────────────────────
    # Maps to: stg_leave_types
    # Natural key: leave_type_id
    _ct(
        "hr.leave_type", "hr",
        "Leave type master — annual, sick, maternity, etc.",
        _f("leave_type_id",
           "leave type id", "type id", "id",
           required=True),
        _f("leave_type_code",
           "code", "leave code", "type code"),
        _f("leave_type_name",
           "name", "leave type", "type name", "leave name",
           required=True),
        _f("is_paid",
           "paid", "is paid", "paid leave"),
        _f("max_days_per_year",
           "max days", "entitlement", "annual entitlement",
           dtype="numeric"),
        _f("carry_forward",
           "carry forward", "cf", "rollover"),
        natural_key=("leave_type_id",),
    ),

    # ── hr.payroll_run ────────────────────────────────────────────
    # Maps to: stg_payroll_runs
    # Natural key: run_code (one row per payroll run)
    _ct(
        "hr.payroll_run", "hr",
        "Payroll run header — one row per processed payroll period",
        _f("run_code",
           "run code", "payroll run", "run id", "payroll id",
           required=True),
        _f("payroll_month",
           "month", "payroll month", "pay month",
           required=True, dtype="numeric"),
        _f("payroll_year",
           "year", "payroll year", "pay year",
           required=True, dtype="numeric"),
        _f("status",
           "run status", "status"),
        _f("total_gross",
           "total gross", "gross total", "total gross salary",
           dtype="numeric"),
        _f("total_deductions",
           "total deductions", "deductions total",
           dtype="numeric"),
        _f("total_net",
           "total net", "net total", "total net salary",
           dtype="numeric"),
        _f("processed_by",
           "processed by", "run by", "prepared by"),
        _f("processed_at",
           "processed at", "run date", "processing date",
           dtype="date"),
        natural_key=("run_code",),
    ),

    # ── hr.payroll_detail ─────────────────────────────────────────
    # Maps to: stg_payroll_details
    # Natural key: employee_id + payroll_run_id
    _ct(
        "hr.payroll_detail", "hr",
        "Payroll detail — per-employee earnings and deductions for one run",
        _f("employee_id",
           "emp id", "emp no", "employee id", "employee code",
           required=True),
        _f("payroll_run_id",
           "run id", "payroll run id", "run code",
           required=True),
        _f("basic_salary",
           "basic", "basic salary", "base salary", "base pay",
           required=True, dtype="numeric"),
        _f("allowances",
           "allowances", "total allowances", "additions",
           dtype="numeric"),
        _f("overtime_pay",
           "ot pay", "overtime pay", "overtime",
           dtype="numeric"),
        _f("bonuses",
           "bonus", "bonuses", "incentive",
           dtype="numeric"),
        _f("gross_salary",
           "gross", "gross salary", "gross pay", "gross earnings",
           dtype="numeric"),
        _f("tax_deduction",
           "tax", "paye", "income tax", "tax deduction",
           dtype="numeric"),
        _f("other_deductions",
           "deductions", "other deductions", "total deductions",
           dtype="numeric"),
        _f("net_salary",
           "net", "net salary", "net pay", "take home",
           dtype="numeric"),
        natural_key=("employee_id", "payroll_run_id"),
    ),

    # ── hr.performance_review ─────────────────────────────────────
    # Maps to: stg_performance_reviews
    # Natural key: employee_id + review_period + review_year
    _ct(
        "hr.performance_review", "hr",
        "Performance review — one row per employee per review cycle",
        _f("employee_id",
           "emp id", "emp no", "employee id", "employee code",
           required=True),
        _f("reviewer_id",
           "reviewer", "reviewer id", "appraiser id", "manager id"),
        _f("review_period",
           "period", "review period", "cycle", "review cycle",
           required=True),
        _f("review_year",
           "year", "review year",
           required=True, dtype="numeric"),
        _f("overall_score",
           "score", "overall score", "total score", "final score",
           dtype="numeric"),
        _f("rating",
           "rating", "grade", "performance rating", "appraisal rating"),
        _f("status",
           "review status", "status"),
        _f("review_date",
           "review date", "appraisal date", "date of review",
           dtype="date"),
        natural_key=("employee_id", "review_period", "review_year"),
    ),

    # ── hr.training_record ────────────────────────────────────────
    # Maps to: stg_training_records
    # Natural key: employee_id + training_id
    _ct(
        "hr.training_record", "hr",
        "Training record — one row per employee per training programme",
        _f("employee_id",
           "emp id", "emp no", "employee id", "employee code",
           required=True),
        _f("training_id",
           "training id", "course id", "programme id"),
        _f("training_name",
           "training", "course", "programme", "training name",
           "course name"),
        _f("training_type",
           "type", "training type", "category"),
        _f("start_date",
           "start date", "training start", "from date",
           dtype="date"),
        _f("end_date",
           "end date", "training end", "to date",
           dtype="date"),
        _f("status",
           "status", "completion status"),
        _f("score",
           "score", "result", "grade", "marks",
           dtype="numeric"),
        _f("cost",
           "cost", "training cost", "fee",
           dtype="numeric"),
        natural_key=("employee_id", "training_id"),
    ),

    # ── hr.leave_balance ─────────────────────────────────────────
    # Flat-file upload shape (not a live extract — customers upload
    # opening balances or year-end snapshots).
    # Natural key: employee_id + leave_type
    _ct(
        "hr.leave_balance", "hr",
        "Leave balance snapshot — entitlement vs taken per employee per type",
        _f("employee_id",
           "emp id", "emp no", "employee id", "employee code",
           required=True),
        _f("leave_type",
           "leave type", "type", "leave name",
           required=True),
        _f("entitled",
           "entitlement", "entitled days", "annual entitlement",
           dtype="numeric"),
        _f("taken",
           "taken", "used", "leave taken", "days taken",
           dtype="numeric"),
        _f("balance",
           "balance", "remaining", "leave balance", "days remaining",
           dtype="numeric"),
        natural_key=("employee_id", "leave_type"),
    ),
)


# ── Index ─────────────────────────────────────────────────────────

_TARGET_INDEX: dict[str, CanonicalTarget] = {
    t.data_type: t for t in CANONICAL_TARGETS
}


def get_target(data_type: str) -> CanonicalTarget | None:
    return _TARGET_INDEX.get(data_type)


def all_targets() -> Tuple[CanonicalTarget, ...]:
    return CANONICAL_TARGETS


def domains() -> Tuple[str, ...]:
    seen: list[str] = []
    for t in CANONICAL_TARGETS:
        if t.domain not in seen:
            seen.append(t.domain)
    return tuple(seen)
