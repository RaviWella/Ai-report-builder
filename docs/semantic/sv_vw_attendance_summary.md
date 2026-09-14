# sv_vw_attendance_summary

> Warehouse object: `vw_attendance_summary` in schema `hr_semantic`

## Overview

**Purpose:** Semantic API view over mart_attendance_monthly_summary.

**Entity:** Attendance  
**Grain:** One row per business grain of underlying mart/fact — TBD per query  
**Recommended Usage:** Reporting and AI queries (query `hr_semantic` only)  

**Upstream reads:** mart_attendance_monthly_summary

## Recommended Filters

- `department_name` / `legal_entity` — org slice
- Period columns (`year_month`, `period_label`, `snapshot_month`) — time slice
- `is_current = true` on joined dimensions when applicable

## Join Dependencies

- mart_attendance_monthly_summary

## AI Agent Metadata

**Natural Language Aliases:**
- attendance
- absence
- punctuality
- overtime

**Typical Questions:**
- Absenteeism rate by department
- Overtime hours this month
- Late arrivals trend

**Recommended Dimensions:**
- year_month
- department_name

**Recommended Measures:**
- days_absent
- days_present
- total_overtime_hours

## Exposed Columns

- `employee_sk` (text)
- `department_id` (integer)
- `branch_id` (integer)
- `period_label` (text)
- `year` (integer)
- `month` (integer)
- `scheduled_days` (bigint)
- `present_days` (bigint)
- `late_count` (bigint)
- `overtime_days` (integer)
- `overtime_hours` (numeric)
- `avg_work_hours` (numeric)
- `total_late_minutes` (integer)
