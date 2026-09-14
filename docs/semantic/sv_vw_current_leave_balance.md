# sv_vw_current_leave_balance

> Warehouse object: `vw_current_leave_balance` in schema `hr_semantic`

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
- leave balance
- remaining leave
- entitlement

**Typical Questions:**
- Current leave balance by employee
- Remaining annual leave

**Recommended Dimensions:**
- department_name
- leave_type

**Recommended Measures:**
- remaining_days
- entitled_days
- used_days

## Exposed Columns

- `employee_number` (varchar(64))
- `employee_name` (varchar(255))
- `department_name` (varchar(255))
- `leave_type` (varchar(255))
- `leave_type_code` (varchar(64))
- `entitlement_year` (integer)
- `entitled_days` (numeric(10,2))
- `used_days` (numeric(10,2))
- `remaining_days` (numeric(10,2))
- `pending_approval_days` (numeric(10,2))
- `period_start_date` (date)
- `period_end_date` (date)
- `snapshot_date` (date)
