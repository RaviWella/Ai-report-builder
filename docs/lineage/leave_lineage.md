# Leave Lineage

Leave intelligence mart source-to-target paths.

## Leave modules

```text
hr_leaveapplication
  ↓
stg_leave_requests
  ↓
int_leave_application
  ↓
fct_leave_application
  ↓
vw_employee_leave_history
```

```text
hr_leaveapplication_dates
  ↓
stg_leave_application_dates
  ↓
fct_leave_daily
  ↓
mart_leave_monthly_summary
```

```text
hr_leave_balance
  ↓
stg_leave_balance
  ↓
fct_leave_balance_snapshot
  ↓
vw_current_leave_balance / vw_leave_liability
```

```text
hr_leaveapplication_superiors
  ↓
stg_leave_approvals
  ↓
fct_leave_approval
  ↓
vw_pending_leave_approvals
```
