# Datamart Mart Spec — Report Builder (denormalised, join-free, fast)

> For the datamart / ETL developer. The Report Builder auto-introspects the `hr`
> schema's `mart_*` (entities) and `dim_*` (lookups) — **no `hr_semantic` views**.
> Reports are FAST and JOIN-FREE when every column a user needs lives in ONE mart.
> So each mart below is **denormalised**: it carries the employee identity + the
> dimension NAMES inline, not just keys. Grain is one row per the stated key.
>
> Conventions the app relies on (keep these so new columns auto-appear):
> - `hr` schema, `mart_*` / `dim_*` names.
> - conformed `employee_sk` on every employee-grained mart (drives auto-join to Employee).
> - clean business column names (they become field labels): `shift_name`, `days_present`.
> - hidden automatically: `*_sk`, `*_id`, `tenant_id`, `_refreshed_at`, `_loaded_at`,
>   `valid_from/to`, `is_current`, `version_number`, `source_system`, `dbt_scd_id`.
> - period marts: include `year` + `month` columns (period-join alignment).
> - PII columns named clearly (nic, salary, email…) → auto-flagged, stripped before AI.

---

## ⭐ BUILD LIST — only what's NEW or changed (do these)

> Everything else in the specs below **already exists** in the facts/dims — just
> assemble it. Legend: 🆕 new mart · ➕ add column (data exists in a fact, surface it)
> · 🔧 populate (column exists but empty) · ⚙️ derive (compute new in the mart) ·
> 🔴 capture (not in the datamart at all — needs HRM source).

**`mart_daily_attendance`** — 🆕 **NEW MART** (grain: employee × day). All columns are
assembled from existing facts (`fct_schedule_day`, `fct_daily_attendance`,
`fct_leave_daily`, `dim_shift`, `dim_leave_type`, `fct_leave_approval`, `dim_employee`).
New pieces to build inside it:
- ⚙️ `day_type` — derived (`Public Holiday → Weekend → On Leave → Absent → Present`)
- ⚙️ `punch_in_time` / `punch_out_time` — time part of `punch_*_datetime`
- ⚙️ `is_working_day` — rename of `fct_schedule_day.is_scheduled`
- ⚙️ `leave_approved_by` — `fct_leave_approval` (final) → `dim_employee.emp_fullname`
- 🔴 `punch_in_machine_no` — only if HRM captures a machine/device id (not in datamart)

**`mart_employee`** (existing `mart_employee_current`) — add / fix:
- ➕ `shift_name` — from `dim_shift` (join current `shift_id`)
- 🔧 `department` — column exists (`designation_department`) but is **empty (0/325)** → populate
- 🔴 `preferred_name` — verify in source; not currently in `dim_employee`

**`mart_leave_application`** — 🆕 **NEW MART** (grain: one leave application). Assembled from
`fct_leave_application` + `dim_leave_type` + `dim_leave_status` + `dim_employee`. No new
source data needed.

**`mart_leave_balance`** — 🆕 **NEW MART** (grain: employee × leave_type) — entitled / taken /
remaining / carried_forward. From `fct_leave_balance_snapshot` + `dim_leave_type`.

**`mart_payroll`** (existing `mart_processed_payroll_summary`) — add columns (all exist in
`fct_processed_salary`, just surface them):
- ➕ `bonus_amount` · ➕ `loan_deduction` · ➕ `installment_deduction`

**Nothing else is new.** Punch times, punch locations, shift, holiday, leave type,
approver — all already captured in the facts. Only `punch_in_machine_no` and
`preferred_name` may need source capture.

---

## 1. `mart_employee` — Employment  (enhance existing `mart_employee_current`)
**Grain:** one row per current employee (`employee_sk`).
**Source:** `dim_employee` (+ `dim_shift` for `shift_name`).

| group | columns |
|---|---|
| identity | employee_sk, emp_no, emp_attendance_no |
| profile (PII) | emp_fullname, emp_name, **preferred_name**, gender, date_of_birth, nic, epf_no, civil_status, nationality, religion, email, mobile |
| org | **department**, designation, grade, branch, location, legal_entity, employee_category, employment_type, cost_center, **shift_name** |
| employment | emp_status, lifecycle_status, is_active, join_date, tenure_years, probation_status, probation_due_date, resignation_effective_date, last_working_date |
| manager | superior_emp_no, superior_name |
| comp | basic_salary |

**Fixes needed:** populate `department` (currently 0/325 empty); add `shift_name`
(join `dim_shift`); add `preferred_name` if the source has a nick name.

---

## 2. `mart_daily_attendance` — Attendance  (NEW — highest priority)
**Grain:** one row per employee per calendar day.
**Base spine:** `fct_schedule_day` (one row per employee per day, with the day's
schedule/holiday/leave flags), LEFT JOIN the attendance and leave detail below.
**Source:**
`fct_schedule_day` (day spine + working-day/holiday/leave flags)
`+ fct_daily_attendance` (`employee_sk` + day → punch, worked, shift_sk)
`+ dim_shift` (`shift_sk` → shift_name)
`+ fct_leave_daily` (`employee_sk` + `leave_date` → leave that day)
`+ dim_leave_type` (`leave_type_sk` → leave_type_name)
`+ fct_leave_approval` (final approval → approver name)
`+ dim_employee` (`employee_sk` → identity, and the approver's name).
> One row = the full picture of a person's day: was it a working day, a holiday
> (which one), on leave (which type, approved by whom), or worked (punch + shift).

| group | columns |
|---|---|
| identity | employee_sk, emp_no, emp_fullname, department, designation, branch, legal_entity |
| date | calendar_day, year, month, day_of_week |
| **day status** | **is_working_day** (= is_scheduled), **is_public_holiday**, **holiday_name**, holiday_type, is_weekend, **is_on_leave**, **day_type** |
| shift | shift_name, planned_shift_name |
| punch (time) | punch_in_time, punch_out_time, punch_in_2_time, punch_out_2_time |
| punch (place) | punch_in_location, punch_out_location, punch_in_branch, punch_out_branch |
| worked | worked_hours, overtime_hours, late_minutes, early_leave_minutes |
| attendance status | is_present, is_absent, late_status, early_leave_status, is_manual_entry, is_approved |
| **leave detail** | **leave_type_name**, leave_status, is_half_day, half_day_type, leave_days, **leave_approved_by**, superior_approved, hr_approved |

**Column notes**
- **`is_working_day`** — from `fct_schedule_day.is_scheduled` (was this a rostered
  working day for this employee?).
- **`is_public_holiday` / `holiday_name` / `holiday_type`** — the holiday for that
  date (from `fct_schedule_day` / `fct_daily_attendance`); `holiday_name` is blank
  when it isn't a holiday.
- **`is_on_leave` + `leave_type_name`** — was the person on leave, and which leave
  (from `fct_leave_daily` → `dim_leave_type.leave_type_name`, e.g. "Annual Leave").
- **`leave_approved_by`** — the FINAL approver's name: `fct_leave_approval` where
  `is_final_approval = true` → `approver_employee_sk` → `dim_employee.emp_fullname`.
  Keep `superior_approved` / `hr_approved` (booleans from `fct_leave_daily`) too.
- **`day_type`** — one friendly categorisation of the day, so a report can show a
  single "status" column. Derive in priority order:
  `Public Holiday → Weekend → On Leave → Absent → Present`.
- `punch_in_time`/`punch_out_time` = time part of `punch_in_datetime` etc.
- Shift is time-varying → join on the fact's `shift_sk` (the shift **as-of that
  date**), NOT the employee's current `shift_id`.
- `Attendance Machine No` — not in the fact; add `punch_in_machine_no` if the
  source captures it.

---

## 3. `mart_leave_application` — Leave  (NEW — application grain)
**Grain:** one row per leave application.
**Source:** `fct_leave_application` + `dim_leave_type` + `dim_leave_status` + `dim_employee`.

| group | columns |
|---|---|
| identity | employee_sk, emp_no, emp_fullname, department, designation, branch |
| leave | leave_type_name, leave_category, is_paid_leave, leave_status, leave_source |
| dates | request_date, start_date, end_date, approval_date, year, month |
| measures | requested_days, approved_days, unpaid_days, rejected_days, cancelled_days |
| flags | is_hr_approval, is_planned_leave, emergency_leave_flag, payroll_impacted_flag |
| reason | leave_reason_text |

**Companion (balances) — keep/confirm `mart_leave_balance`:** grain employee × leave_type
→ employee identity + leave_type_name + entitled_days, taken_days, remaining_days,
carried_forward_days, year. (Partly covered by existing `mart_leave_employee_profile`.)

---

## 4. `mart_payroll` — Payroll  (mostly exists as `mart_processed_payroll_summary`)
**Grain:** one row per employee per payroll period.
**Source:** `fct_processed_salary` + `dim_payroll_period` + `dim_employee`.

| group | columns |
|---|---|
| identity | employee_sk, emp_no, emp_fullname, designation, branch, legal_entity, payroll_group_name |
| period | payroll_year, payroll_month, payroll_half, period_start_date, period_end_date, period_label |
| earnings | basic_salary, gross_salary, total_additions, ot_amount, bonus_amount, increment_amount |
| deductions | total_deductions, tax_amount, epf_employee_amount, epf_employer_amount, etf_amount, nopay_deduction, loan_deduction, installment_deduction, pay_cut_amount |
| net | net_salary |
| status | process_status, payroll_currency |

**Gaps to add to the existing mart:** `bonus_amount`, `loan_deduction`,
`installment_deduction` (present in `fct_processed_salary`, missing from the summary mart).
**Companion (dynamic pay items) — keep `mart_horizontal_paysheet_dynamic`:** one row per
employee × period, one column per pay item (already introspected automatically).

---

## Access (required after the schema-only switch)
The app now queries `hr` directly (search_path = `hr` only). Grant the read-only user:
```sql
GRANT USAGE ON SCHEMA hr TO <readonly_warehouse_user>;
GRANT SELECT ON ALL TABLES IN SCHEMA hr TO <readonly_warehouse_user>;
ALTER DEFAULT PRIVILEGES IN SCHEMA hr GRANT SELECT ON TABLES TO <readonly_warehouse_user>;
```

## Priority
1. **`mart_daily_attendance`** — biggest unlock (date + shift + punch time + location).
2. **`mart_employee`** — populate `department`, add `shift_name`, `preferred_name`.
3. **`mart_leave_application`** (+ balances).
4. **`mart_payroll`** — add bonus/loan/installment columns.
