# sv_vw_leave_liability

> Warehouse object: `vw_leave_liability` in schema `hr_semantic`

## Overview

**Purpose:** Semantic API view over fct_leave_balance_snapshot, dim_employee, dim_leave_type.

**Entity:** Leave Management  
**Grain:** One row per business grain of underlying mart/fact — TBD per query  
**Recommended Usage:** Reporting and AI queries (query `hr_semantic` only)  

**Upstream reads:** fct_leave_balance_snapshot, dim_employee, dim_leave_type

## Recommended Filters

- `department_name` / `legal_entity` — org slice
- Period columns (`year_month`, `period_label`, `snapshot_month`) — time slice
- `is_current = true` on joined dimensions when applicable

## Join Dependencies

- fct_leave_balance_snapshot, dim_employee, dim_leave_type

## AI Agent Metadata

**Natural Language Aliases:**
- leave liability
- expiring leave
- paid leave balance

**Typical Questions:**
- Leave liability by department
- Leave expiring in 90 days

**Recommended Dimensions:**
- department_name
- leave_type

**Recommended Measures:**
- liability_days

## Exposed Columns

- `employee_number` (varchar(64))
- `employee_name` (varchar(255))
- `department_name` (varchar(255))
- `legal_entity` (varchar(255))
- `leave_type` (varchar(255))
- `leave_type_code` (varchar(64))
- `is_paid_leave` (boolean)
- `entitlement_year` (integer)
- `entitled_days` (numeric(10,2))
- `used_days` (numeric(10,2))
- `liability_days` (numeric(10,2))
- `carry_forward_days` (numeric(10,2))
- `expired_days` (numeric(10,2))
- `pending_approval_days` (numeric(10,2))
- `period_start_date` (date)
- `expiry_date` (date)
- `days_until_expiry` (integer)
- `is_expiring_within_90_days` (boolean)
- `snapshot_date` (date)
