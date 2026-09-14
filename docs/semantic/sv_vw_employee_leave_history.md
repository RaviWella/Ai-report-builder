# sv_vw_employee_leave_history

> Warehouse object: `vw_employee_leave_history` in schema `hr_semantic`

## Overview

**Purpose:** Semantic API view over fct_leave_application, dim_employee, dim_leave_type.

**Entity:** Leave Management  
**Grain:** One row per business grain of underlying mart/fact — TBD per query  
**Recommended Usage:** Reporting and AI queries (query `hr_semantic` only)  

**Upstream reads:** fct_leave_application, dim_employee, dim_leave_type

## Recommended Filters

- `department_name` / `legal_entity` — org slice
- Period columns (`year_month`, `period_label`, `snapshot_month`) — time slice
- `is_current = true` on joined dimensions when applicable

## Join Dependencies

- fct_leave_application, dim_employee, dim_leave_type

## AI Agent Metadata

**Natural Language Aliases:**
- leave history
- leave applications
- time off requests

**Typical Questions:**
- Show leave history for an employee
- Pending leave applications

**Recommended Dimensions:**
- department_name
- leave_type
- leave_status

**Recommended Measures:**
- approved_days
- requested_days

## Exposed Columns

- `employee_number` (varchar(64))
- `employee_name` (varchar(255))
- `department_name` (varchar(255))
- `leave_type` (varchar(255))
- `leave_type_code` (varchar(64))
- `leave_status` (text)
- `leave_source` (text)
- `leave_start_date` (date)
- `leave_end_date` (date)
- `leave_apply_date` (timestamp)
- `approval_date` (timestamp)
- `requested_days` (numeric(8,2))
- `approved_days` (numeric(8,2))
- `unpaid_days` (numeric(8,2))
- `leave_reason` (text)
- `is_hr_approval` (boolean)
- `payroll_impacted_flag` (boolean)
- `cancelled_flag` (boolean)
- `approval_duration_hours` (numeric(10,2))
