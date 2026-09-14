"""Seed semantic catalogue for the HR datamart (verified against mint_sejaya).

A starting, tech-team-managed mapping (SRS §4.1) built against the denormalised
`mart` schema (report-ready `mart_*` tables). This is the OFFLINE fallback used
when the live datamart is unreachable — the primary path auto-introspects the
same `mart` schema via semantic_autobuild.

Key facts about the mart layout:
- The `mart` schema is fully denormalised: every consumer table carries the
  employee attributes (department, designation, branch, …) alongside its measures,
  so most entities are self-contained and need no joins.
- Employee-grained marts share the conformed `employee_sk`, so Payroll / Attendance
  / Leave-balance join to Employee on `employee_sk`.
- Period marts are grained by (`year_no`, `month_no`); the compiler aligns
  period-to-period joins on those so two period marts don't cross-multiply.

Business concepts -> physical columns. Only this file (and the catalogue it
produces) knows physical names; everything upstream uses the `ref`.
"""

from __future__ import annotations

from app.domain.enums import AggFn, FieldRole, FieldType
from app.domain.semantic import (
    Entity,
    JoinDef,
    PeriodGrain,
    PhysicalColumn,
    SemanticCatalog,
    SemanticField,
)

MART = "mart"  # denormalised consumer schema (report-ready mart_* tables)
_MONEY = [AggFn.SUM, AggFn.AVG, AggFn.MIN, AggFn.MAX]
_NUM = [AggFn.SUM, AggFn.AVG, AggFn.MIN, AggFn.MAX]
_PERIOD = PeriodGrain(year_column="year_no", month_column="month_no")


def _f(ref, label, type_, role, table, column, *, schema=MART, aggs=None, pii=False, desc=None):
    return SemanticField(
        ref=ref,
        label=label,
        type=type_,
        role=role,
        description=desc,
        physical=PhysicalColumn(table=table, column=column, schema_name=schema),
        allowed_aggregations=aggs or [],
        pii=pii,
    )


def build_seed_catalog(tenant_id: str, version: int = 1) -> SemanticCatalog:
    EMP = "mart_employee"
    employee = Entity(
        name="Employee",
        key="employee",
        base_schema=MART,
        base_table=EMP,
        primary_key="employee_sk",
        description="Current employee profile (wide denormalised mart).",
        fields=[
            _f("employee.emp_no", "Employee Number", FieldType.STRING, FieldRole.DIMENSION, EMP, "employee_no",
               desc="Employee number / ID (a.k.a. Employee No, EMP No)."),
            _f("employee.full_name", "Employee Name", FieldType.STRING, FieldRole.DIMENSION, EMP, "full_name", pii=True),
            _f("employee.display_name", "Display Name", FieldType.STRING, FieldRole.DIMENSION, EMP, "display_name", pii=True),
            _f("employee.gender", "Gender", FieldType.STRING, FieldRole.DIMENSION, EMP, "gender"),
            _f("employee.date_of_birth", "Date of Birth", FieldType.DATE, FieldRole.DIMENSION, EMP, "date_of_birth", pii=True),
            _f("employee.age", "Age", FieldType.INTEGER, FieldRole.MEASURE, EMP, "age_years",
               aggs=[AggFn.AVG, AggFn.MIN, AggFn.MAX], desc="Precomputed in the mart (today − date_of_birth)."),
            _f("employee.nic", "NIC", FieldType.STRING, FieldRole.DIMENSION, EMP, "nic_no", pii=True),
            _f("employee.epf_no", "EPF No", FieldType.STRING, FieldRole.DIMENSION, EMP, "epf_no", pii=True),
            _f("employee.status", "Employment Status", FieldType.STRING, FieldRole.DIMENSION, EMP, "employment_status",
               desc="active / inactive / resigned / etc."),
            _f("employee.lifecycle_status", "Lifecycle Status", FieldType.STRING, FieldRole.DIMENSION, EMP, "lifecycle_status"),
            _f("employee.is_active", "Is Active", FieldType.BOOLEAN, FieldRole.DIMENSION, EMP, "is_active"),
            _f("employee.designation", "Designation", FieldType.STRING, FieldRole.DIMENSION, EMP, "designation"),
            _f("employee.department", "Department", FieldType.STRING, FieldRole.DIMENSION, EMP, "department"),
            _f("employee.sub_department", "Sub Department", FieldType.STRING, FieldRole.DIMENSION, EMP, "sub_department"),
            _f("employee.grade", "Grade", FieldType.STRING, FieldRole.DIMENSION, EMP, "grade"),
            _f("employee.category", "Employee Category", FieldType.STRING, FieldRole.DIMENSION, EMP, "employee_category"),
            _f("employee.employment_type", "Employment Type", FieldType.STRING, FieldRole.DIMENSION, EMP, "employment_type"),
            _f("employee.branch", "Branch", FieldType.STRING, FieldRole.DIMENSION, EMP, "branch"),
            _f("employee.legal_entity", "Legal Entity", FieldType.STRING, FieldRole.DIMENSION, EMP, "legal_entity"),
            _f("employee.cost_center", "Cost Center", FieldType.STRING, FieldRole.DIMENSION, EMP, "cost_center"),
            _f("employee.payroll_group", "Payroll Group", FieldType.STRING, FieldRole.DIMENSION, EMP, "payroll_group"),
            _f("employee.position", "Job Position", FieldType.STRING, FieldRole.DIMENSION, EMP, "job_position"),
            _f("employee.civil_status", "Civil Status", FieldType.STRING, FieldRole.DIMENSION, EMP, "civil_status"),
            _f("employee.nationality", "Nationality", FieldType.STRING, FieldRole.DIMENSION, EMP, "nationality"),
            _f("employee.religion", "Religion", FieldType.STRING, FieldRole.DIMENSION, EMP, "religion"),
            _f("employee.join_date", "Join Date", FieldType.DATE, FieldRole.DIMENSION, EMP, "join_date"),
            _f("employee.is_confirmed", "Confirmed", FieldType.BOOLEAN, FieldRole.DIMENSION, EMP, "is_confirmed"),
            _f("employee.tenure_years", "Tenure (years)", FieldType.DECIMAL, FieldRole.MEASURE, EMP, "tenure_years", aggs=[AggFn.AVG, AggFn.MIN, AggFn.MAX]),
            _f("employee.current_basic", "Current Basic Salary", FieldType.DECIMAL, FieldRole.MEASURE, EMP, "basic_salary", aggs=_MONEY, pii=True),
            _f("employee.mobile", "Mobile", FieldType.STRING, FieldRole.DIMENSION, EMP, "mobile_no", pii=True),
            _f("employee.work_email", "Work Email", FieldType.STRING, FieldRole.DIMENSION, EMP, "work_email", pii=True),
            _f("employee.headcount", "Headcount", FieldType.INTEGER, FieldRole.MEASURE, EMP, "employee_sk",
               aggs=[AggFn.COUNT, AggFn.COUNT_DISTINCT]),
        ],
    )

    PAY = "mart_payroll_summary"
    payroll = Entity(
        name="Payroll",
        key="payroll",
        base_schema=MART,
        base_table=PAY,
        primary_key="employee_sk",
        description="Processed payroll summary per employee × period.",
        period_grain=_PERIOD,
        fields=[
            _f("payroll.period", "Pay Period", FieldType.STRING, FieldRole.DIMENSION, PAY, "pay_period"),
            _f("payroll.year_month", "Year-Month", FieldType.STRING, FieldRole.DIMENSION, PAY, "year_month"),
            _f("payroll.year", "Payroll Year", FieldType.INTEGER, FieldRole.DIMENSION, PAY, "year_no"),
            _f("payroll.month", "Payroll Month", FieldType.INTEGER, FieldRole.DIMENSION, PAY, "month_no"),
            _f("payroll.group", "Payroll Group", FieldType.STRING, FieldRole.DIMENSION, PAY, "payroll_group"),
            _f("payroll.branch", "Branch", FieldType.STRING, FieldRole.DIMENSION, PAY, "branch"),
            _f("payroll.currency", "Currency", FieldType.STRING, FieldRole.DIMENSION, PAY, "currency_code"),
            _f("payroll.basic", "Basic Salary", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "basic_salary", aggs=_MONEY, pii=True),
            _f("payroll.gross", "Gross Salary", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "gross_salary", aggs=_MONEY, pii=True),
            _f("payroll.additions", "Total Additions", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "total_additions", aggs=_MONEY),
            _f("payroll.fixed_allowances", "Fixed Allowances", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "fixed_allowances", aggs=_MONEY),
            _f("payroll.variable_allowances", "Variable Allowances", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "variable_allowances", aggs=_MONEY),
            _f("payroll.overtime", "Overtime Amount", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "overtime_amount", aggs=_MONEY),
            _f("payroll.deductions", "Total Deductions", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "total_deductions", aggs=_MONEY),
            _f("payroll.loan_deduction", "Loan Deduction", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "loan_deduction", aggs=_MONEY),
            _f("payroll.nopay", "No-Pay Amount", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "nopay_amount", aggs=_MONEY),
            _f("payroll.net", "Net Salary", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "net_salary", aggs=_MONEY, pii=True),
            _f("payroll.tax", "PAYE Tax", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "paye_tax", aggs=_MONEY),
            _f("payroll.epf_employee", "EPF (Employee 8%)", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "epf_employee_8", aggs=_MONEY),
            _f("payroll.epf_employer", "EPF (Employer 12%)", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "epf_employer_12", aggs=_MONEY),
            _f("payroll.etf", "ETF (3%)", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "etf_3", aggs=_MONEY),
            _f("payroll.employer_cost", "Total Employer Cost", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "total_employer_cost", aggs=_MONEY),
            _f("payroll.bank_transfer", "Bank Transfer Amount", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "bank_transfer_amount", aggs=_MONEY),
            _f("payroll.worked_days", "Worked Days", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "worked_days", aggs=_NUM),
            _f("payroll.nopay_days", "No-Pay Days", FieldType.DECIMAL, FieldRole.MEASURE, PAY, "nopay_days", aggs=_NUM),
        ],
    )

    ATT = "mart_attendance_monthly"
    attendance = Entity(
        name="Attendance",
        key="attendance",
        base_schema=MART,
        base_table=ATT,
        primary_key="employee_sk",
        description="Monthly attendance rollup per employee.",
        period_grain=_PERIOD,
        fields=[
            _f("attendance.period", "Period", FieldType.STRING, FieldRole.DIMENSION, ATT, "year_month"),
            _f("attendance.year", "Year", FieldType.INTEGER, FieldRole.DIMENSION, ATT, "year_no"),
            _f("attendance.month", "Month", FieldType.INTEGER, FieldRole.DIMENSION, ATT, "month_no"),
            _f("attendance.working_days", "Working Days", FieldType.INTEGER, FieldRole.MEASURE, ATT, "working_days", aggs=_NUM),
            _f("attendance.present_days", "Present Days", FieldType.DECIMAL, FieldRole.MEASURE, ATT, "days_present", aggs=_NUM),
            _f("attendance.absent_days", "Absent Days", FieldType.DECIMAL, FieldRole.MEASURE, ATT, "days_absent", aggs=_NUM),
            _f("attendance.leave_days", "Leave Days", FieldType.DECIMAL, FieldRole.MEASURE, ATT, "days_leave", aggs=_NUM),
            _f("attendance.nopay_days", "No-Pay Days", FieldType.DECIMAL, FieldRole.MEASURE, ATT, "days_nopay", aggs=_NUM),
            _f("attendance.holiday_days", "Holiday Days", FieldType.DECIMAL, FieldRole.MEASURE, ATT, "days_holiday", aggs=_NUM),
            _f("attendance.worked_hours", "Worked Hours", FieldType.DECIMAL, FieldRole.MEASURE, ATT, "worked_hours", aggs=_NUM),
            _f("attendance.ot_hours", "Overtime Hours", FieldType.DECIMAL, FieldRole.MEASURE, ATT, "overtime_hours", aggs=_NUM),
            _f("attendance.late_minutes", "Late Minutes", FieldType.INTEGER, FieldRole.MEASURE, ATT, "late_minutes", aggs=_NUM),
            _f("attendance.late_count", "Late Occurrences", FieldType.INTEGER, FieldRole.MEASURE, ATT, "late_occurrences", aggs=_NUM),
            _f("attendance.absent_count", "Absent Occurrences", FieldType.INTEGER, FieldRole.MEASURE, ATT, "absent_occurrences", aggs=_NUM),
            _f("attendance.attendance_pct", "Attendance %", FieldType.DECIMAL, FieldRole.MEASURE, ATT, "attendance_percentage", aggs=[AggFn.AVG, AggFn.MIN, AggFn.MAX]),
        ],
    )

    LB = "mart_leave_balance"
    leave = Entity(
        name="Leave Balance",
        key="leave",
        base_schema=MART,
        base_table=LB,
        primary_key="employee_sk",
        description="Leave entitlement / taken / balance per employee × type × cycle.",
        fields=[
            _f("leave.type", "Leave Type", FieldType.STRING, FieldRole.DIMENSION, LB, "leave_type"),
            _f("leave.category", "Leave Category", FieldType.STRING, FieldRole.DIMENSION, LB, "leave_category"),
            _f("leave.cycle_year", "Cycle Year", FieldType.INTEGER, FieldRole.DIMENSION, LB, "cycle_year"),
            _f("leave.entitled", "Entitled Days", FieldType.DECIMAL, FieldRole.MEASURE, LB, "entitled_days", aggs=_NUM),
            _f("leave.carried_forward", "Carried Forward Days", FieldType.DECIMAL, FieldRole.MEASURE, LB, "carried_forward_days", aggs=_NUM),
            _f("leave.taken", "Taken Days", FieldType.DECIMAL, FieldRole.MEASURE, LB, "taken_days", aggs=_NUM),
            _f("leave.pending", "Pending Days", FieldType.DECIMAL, FieldRole.MEASURE, LB, "pending_days", aggs=_NUM),
            _f("leave.balance", "Balance Days", FieldType.DECIMAL, FieldRole.MEASURE, LB, "balance_days", aggs=_NUM),
            _f("leave.utilisation_pct", "Utilisation %", FieldType.DECIMAL, FieldRole.MEASURE, LB, "utilisation_percentage", aggs=[AggFn.AVG, AggFn.MIN, AggFn.MAX]),
        ],
    )

    # ------------------------------------------------------------------ #
    # Standalone marts — fully denormalised, reported FROM directly (no joins).
    # ------------------------------------------------------------------ #
    standalone = [
        _view_entity(
            "Payslip", "payslip", "mart_payslip", "employee_sk",
            "Payslip component lines per employee × period × pay component.",
            [
                ("emp_no", "Employee No", FieldType.STRING, FieldRole.DIMENSION, "employee_no"),
                ("employee_name", "Employee Name", FieldType.STRING, FieldRole.DIMENSION, "full_name", True),
                ("department", "Department", FieldType.STRING, FieldRole.DIMENSION, "department"),
                ("designation", "Designation", FieldType.STRING, FieldRole.DIMENSION, "designation"),
                ("branch", "Branch", FieldType.STRING, FieldRole.DIMENSION, "branch"),
                ("period", "Pay Period", FieldType.STRING, FieldRole.DIMENSION, "pay_period"),
                ("year", "Year", FieldType.INTEGER, FieldRole.DIMENSION, "year_no"),
                ("month", "Month", FieldType.INTEGER, FieldRole.DIMENSION, "month_no"),
                ("component", "Component", FieldType.STRING, FieldRole.DIMENSION, "component_name"),
                ("component_type", "Component Type", FieldType.STRING, FieldRole.DIMENSION, "component_type"),
                ("component_code", "Component Code", FieldType.STRING, FieldRole.DIMENSION, "component_code"),
                ("amount", "Amount", FieldType.DECIMAL, FieldRole.MEASURE, "amount", True, _MONEY),
                ("is_taxable", "Taxable", FieldType.BOOLEAN, FieldRole.DIMENSION, "is_taxable"),
                ("is_epf_liable", "EPF Liable", FieldType.BOOLEAN, FieldRole.DIMENSION, "is_epf_liable"),
            ],
        ),
        _view_entity(
            "Leave Request", "leave_request", "mart_leave_request", "employee_sk",
            "One row per leave application (history + approval workflow).",
            [
                ("emp_no", "Employee No", FieldType.STRING, FieldRole.DIMENSION, "employee_no"),
                ("employee_name", "Employee Name", FieldType.STRING, FieldRole.DIMENSION, "full_name", True),
                ("department", "Department", FieldType.STRING, FieldRole.DIMENSION, "department"),
                ("designation", "Designation", FieldType.STRING, FieldRole.DIMENSION, "designation"),
                ("branch", "Branch", FieldType.STRING, FieldRole.DIMENSION, "branch"),
                ("leave_type", "Leave Type", FieldType.STRING, FieldRole.DIMENSION, "leave_type"),
                ("leave_category", "Leave Category", FieldType.STRING, FieldRole.DIMENSION, "leave_category"),
                ("is_paid", "Paid Leave", FieldType.BOOLEAN, FieldRole.DIMENSION, "is_paid_leave"),
                ("start_date", "Start Date", FieldType.DATE, FieldRole.DIMENSION, "start_date"),
                ("end_date", "End Date", FieldType.DATE, FieldRole.DIMENSION, "end_date"),
                ("applied_date", "Applied Date", FieldType.DATE, FieldRole.DIMENSION, "applied_date"),
                ("year", "Year", FieldType.INTEGER, FieldRole.DIMENSION, "year_no"),
                ("month", "Month", FieldType.INTEGER, FieldRole.DIMENSION, "month_no"),
                ("status", "Status", FieldType.STRING, FieldRole.DIMENSION, "leave_status"),
                ("is_approved", "Approved", FieldType.BOOLEAN, FieldRole.DIMENSION, "is_approved"),
                ("is_pending", "Pending", FieldType.BOOLEAN, FieldRole.DIMENSION, "is_pending"),
                ("requested_days", "Requested Days", FieldType.DECIMAL, FieldRole.MEASURE, "requested_days", False, _NUM),
                ("approved_days", "Approved Days", FieldType.DECIMAL, FieldRole.MEASURE, "approved_days", False, _NUM),
                ("pending_days", "Pending Days", FieldType.DECIMAL, FieldRole.MEASURE, "pending_days", False, _NUM),
                ("nopay_days", "No-Pay Days", FieldType.DECIMAL, FieldRole.MEASURE, "nopay_days", False, _NUM),
                ("reason", "Reason", FieldType.STRING, FieldRole.DIMENSION, "leave_reason"),
            ],
        ),
        _view_entity(
            "Headcount", "headcount", "mart_headcount_monthly", "employee_sk",
            "Monthly per-employee headcount / joiner / leaver metrics.",
            [
                ("period", "Period", FieldType.STRING, FieldRole.DIMENSION, "year_month"),
                ("year", "Year", FieldType.INTEGER, FieldRole.DIMENSION, "year_no"),
                ("month", "Month", FieldType.INTEGER, FieldRole.DIMENSION, "month_no"),
                ("department", "Department", FieldType.STRING, FieldRole.DIMENSION, "department"),
                ("designation", "Designation", FieldType.STRING, FieldRole.DIMENSION, "designation"),
                ("branch", "Branch", FieldType.STRING, FieldRole.DIMENSION, "branch"),
                ("gender", "Gender", FieldType.STRING, FieldRole.DIMENSION, "gender"),
                ("employment_status", "Employment Status", FieldType.STRING, FieldRole.DIMENSION, "employment_status"),
                ("employment_type", "Employment Type", FieldType.STRING, FieldRole.DIMENSION, "employment_type"),
                ("category", "Employee Category", FieldType.STRING, FieldRole.DIMENSION, "employee_category"),
                ("headcount", "Headcount", FieldType.INTEGER, FieldRole.MEASURE, "headcount", False, _NUM),
                ("fte", "FTE", FieldType.DECIMAL, FieldRole.MEASURE, "fte", False, _NUM),
                ("is_joiner", "Joiner", FieldType.BOOLEAN, FieldRole.DIMENSION, "is_joiner"),
                ("is_leaver", "Leaver", FieldType.BOOLEAN, FieldRole.DIMENSION, "is_leaver"),
                ("leaver_reason", "Leaver Reason", FieldType.STRING, FieldRole.DIMENSION, "leaver_reason"),
            ],
        ),
        _view_entity(
            "Employment Event", "employment_event", "mart_employment_event", "employee_sk",
            "Hire / transfer / promotion / salary-change / exit events.",
            [
                ("emp_no", "Employee No", FieldType.STRING, FieldRole.DIMENSION, "employee_no"),
                ("employee_name", "Employee Name", FieldType.STRING, FieldRole.DIMENSION, "full_name", True),
                ("department", "Department", FieldType.STRING, FieldRole.DIMENSION, "department"),
                ("branch", "Branch", FieldType.STRING, FieldRole.DIMENSION, "branch"),
                ("event_type", "Event Type", FieldType.STRING, FieldRole.DIMENSION, "event_type"),
                ("event_date", "Event Date", FieldType.DATE, FieldRole.DIMENSION, "event_date"),
                ("effective_date", "Effective Date", FieldType.DATE, FieldRole.DIMENSION, "effective_date"),
                ("year", "Year", FieldType.INTEGER, FieldRole.DIMENSION, "year_no"),
                ("month", "Month", FieldType.INTEGER, FieldRole.DIMENSION, "month_no"),
                ("designation_from", "Designation (From)", FieldType.STRING, FieldRole.DIMENSION, "designation_from"),
                ("designation_to", "Designation (To)", FieldType.STRING, FieldRole.DIMENSION, "designation_to"),
                ("department_from", "Department (From)", FieldType.STRING, FieldRole.DIMENSION, "department_from"),
                ("department_to", "Department (To)", FieldType.STRING, FieldRole.DIMENSION, "department_to"),
                ("salary_before", "Salary Before", FieldType.DECIMAL, FieldRole.MEASURE, "salary_before", True, _MONEY),
                ("salary_after", "Salary After", FieldType.DECIMAL, FieldRole.MEASURE, "salary_after", True, _MONEY),
                ("salary_change", "Salary Change", FieldType.DECIMAL, FieldRole.MEASURE, "salary_change_amount", True, _MONEY),
                ("salary_change_pct", "Salary Change %", FieldType.DECIMAL, FieldRole.MEASURE, "salary_change_percentage", False, [AggFn.AVG, AggFn.MIN, AggFn.MAX]),
                ("reason", "Reason", FieldType.STRING, FieldRole.DIMENSION, "reason"),
            ],
        ),
    ]

    # Declared joins — Payroll / Attendance / Leave-balance hang off the conformed
    # employee_sk. (Standalone marts above are self-contained; no joins.)
    joins = [
        JoinDef(left_entity="Employee", right_entity="Payroll",
                left_key="employee_sk", right_key="employee_sk", join_type="left"),
        JoinDef(left_entity="Employee", right_entity="Attendance",
                left_key="employee_sk", right_key="employee_sk", join_type="left"),
        JoinDef(left_entity="Employee", right_entity="Leave Balance",
                left_key="employee_sk", right_key="employee_sk", join_type="left"),
    ]

    return SemanticCatalog(
        tenant_id=tenant_id,
        version=version,
        entities=[employee, payroll, attendance, leave, *standalone],
        joins=joins,
    )


def _view_entity(name, key, table, pk, description, fields_spec):
    """Build a standalone `mart` entity from a compact field spec.

    fields_spec: list of tuples
        (ref_suffix, label, FieldType, FieldRole, column, [pii=False], [aggs=None])
    """
    fields = []
    for spec in fields_spec:
        ref_suffix, label, ftype, role, column = spec[:5]
        pii = spec[5] if len(spec) > 5 else False
        aggs = spec[6] if len(spec) > 6 else None
        fields.append(
            _f(f"{key}.{ref_suffix}", label, ftype, role, table, column, aggs=aggs, pii=pii)
        )
    return Entity(
        name=name, key=key, base_schema=MART, base_table=table,
        primary_key=pk, description=description, fields=fields,
    )
