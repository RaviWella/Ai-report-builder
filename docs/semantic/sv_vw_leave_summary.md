# sv_vw_leave_summary

> Warehouse object: `vw_leave_summary` in schema `hr_semantic`

## Overview

**Purpose:** Semantic API view over fact_leave_balance, fct_leave_application, dim_employee.

**Entity:** Leave Management  
**Grain:** One row per business grain of underlying mart/fact — TBD per query  
**Recommended Usage:** Reporting and AI queries (query `hr_semantic` only)  

**Upstream reads:** fact_leave_balance, fct_leave_application, dim_employee

## Recommended Filters

- `department_name` / `legal_entity` — org slice
- Period columns (`year_month`, `period_label`, `snapshot_month`) — time slice
- `is_current = true` on joined dimensions when applicable

## Join Dependencies

- fact_leave_balance, fct_leave_application, dim_employee

## AI Agent Metadata

**Natural Language Aliases:**
- leave
- time off
- vacation
- sick leave

**Typical Questions:**
- Leave days taken by type
- Leave balance summary

**Recommended Dimensions:**
- leave_type_name
- period_label

**Recommended Measures:**
- days_taken
- balance_days

## Exposed Columns

- `employee_sk` (text)
- `department_id` (integer)
- `branch_id` (integer)
- `period_label` (text)
- `year` (integer)
- `leave_type_code` (varchar(64))
- `leave_type_name` (varchar(255))
- `is_paid` (boolean)
- `days_taken` (numeric(8,2))
- `days_entitled` (numeric(8,2))
- `balance_days` (numeric)
- `sick_days` (numeric(8,2))
