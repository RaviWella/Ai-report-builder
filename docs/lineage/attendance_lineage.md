# Attendance Lineage

Attendance and overtime analytics path.

## Daily attendance

```text
HR_ATTEDANCE / hr_attedance
  ↓
stg_attendance
  ↓
fct_daily_attendance
  ↓
mart_attendance_monthly_summary
  ↓
vw_attendance_summary
```

```text
fct_daily_attendance (OT derivation)
  ↓
fct_overtime
  ↓
mart_attendance_monthly_summary.total_overtime_hours
```
