# sv_vw_headcount

> Warehouse object: `vw_headcount` in schema `hr_semantic`

## Overview

**Purpose:** Semantic API view over mart_headcount_monthly, dim_employee.

**Entity:** Workforce  
**Grain:** One row per business grain of underlying mart/fact — TBD per query  
**Recommended Usage:** Reporting and AI queries (query `hr_semantic` only)  

**Upstream reads:** mart_headcount_monthly, dim_employee

## Recommended Filters

- `department_name` / `legal_entity` — org slice
- Period columns (`year_month`, `period_label`, `snapshot_month`) — time slice
- `is_current = true` on joined dimensions when applicable

## Join Dependencies

- mart_headcount_monthly, dim_employee

## AI Agent Metadata

**Natural Language Aliases:**
- headcount
- workforce size
- staff count
- employee count

**Typical Questions:**
- How many active employees do we have?
- Headcount by month
- Workforce trend

**Recommended Dimensions:**
- snapshot_month
- legal_entity

**Recommended Measures:**
- active_headcount

## Exposed Columns

- `employee_id` (integer)
- `department_id` (integer)
- `branch_id` (integer)
- `employment_status` (text)
- `employment_type` (varchar(64))
- `gender` (varchar(32))
- `join_period_label` (text)
- `resign_period_label` (varchar(7))
- `terminate_period_label` (varchar(7))
- `separation_period_label` (varchar(7))
- `metric_status` (text)
- `is_active` (boolean)
- `is_current` (boolean)
