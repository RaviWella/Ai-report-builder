# sv_vw_leave_utilization

> Warehouse object: `vw_leave_utilization` in schema `hr_semantic`

## Overview

**Purpose:** Semantic API view over mart_leave_monthly_summary, fct_leave_balance_snapshot.

**Entity:** Leave Management  
**Grain:** One row per business grain of underlying mart/fact — TBD per query  
**Recommended Usage:** Reporting and AI queries (query `hr_semantic` only)  

**Upstream reads:** mart_leave_monthly_summary, fct_leave_balance_snapshot

## Recommended Filters

- `department_name` / `legal_entity` — org slice
- Period columns (`year_month`, `period_label`, `snapshot_month`) — time slice
- `is_current = true` on joined dimensions when applicable

## Join Dependencies

- mart_leave_monthly_summary, fct_leave_balance_snapshot

## AI Agent Metadata

**Natural Language Aliases:**
- leave utilization
- leave usage rate

**Typical Questions:**
- Leave utilization by department
- Used vs entitled leave

**Recommended Dimensions:**
- year_month
- department_name
- leave_type

**Recommended Measures:**
- utilization_rate_pct
- approved_leave_days

## Exposed Columns

- `year_month` (text)
- `year` (smallint)
- `month_number` (smallint)
- `department_name` (text)
- `leave_type` (text)
- `leave_type_code` (text)
- `approved_leave_days` (numeric)
- `total_leave_days` (numeric)
- `pending_leave_days` (numeric)
- `employees_on_approved_leave` (bigint)
- `avg_approved_days_per_employee` (numeric)
- `total_entitled_days` (numeric)
- `total_used_days` (numeric)
- `total_remaining_days` (numeric)
- `utilization_rate_pct` (numeric)
- `period_usage_share_pct` (numeric)
- `_refreshed_at` (timestamp)
