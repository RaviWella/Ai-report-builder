# Employee Lineage

Source-to-target mapping for workforce domain.

## Core employee master

```text
hr_empbasic.emp_id
  ↓
stg_employees.id
  ↓
snap_employee (dbt snapshot)
  ↓
dim_employee.employee_sk
  ↓
mart_employee_current
  ↓
vw_headcount (semantic)
```

```text
hr_employment.ref_emp_id
  ↓
stg_employees (enriched attributes)
  ↓
fct_employment_snapshot
  ↓
mart_headcount_monthly
```

```text
hr_lifecycle
  ↓
stg_lifecycle
  ↓
fct_lifecycle_event
  ↓
vw_lifecycle_summary / vw_turnover
```
