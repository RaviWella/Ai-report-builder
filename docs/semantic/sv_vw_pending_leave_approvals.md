# sv_vw_pending_leave_approvals

> Warehouse object: `vw_pending_leave_approvals` in schema `hr_semantic`

## Overview

**Purpose:** Semantic API view over fct_leave_approval, fct_leave_application, dim_employee.

**Entity:** Leave Management  
**Grain:** One row per business grain of underlying mart/fact — TBD per query  
**Recommended Usage:** Reporting and AI queries (query `hr_semantic` only)  

**Upstream reads:** fct_leave_approval, fct_leave_application, dim_employee

## Recommended Filters

- `department_name` / `legal_entity` — org slice
- Period columns (`year_month`, `period_label`, `snapshot_month`) — time slice
- `is_current = true` on joined dimensions when applicable

## Join Dependencies

- fct_leave_approval, fct_leave_application, dim_employee

## AI Agent Metadata

**Natural Language Aliases:**
- pending approvals
- leave approval queue

**Typical Questions:**
- Leaves waiting for approval

**Recommended Dimensions:**
- department_name
- leave_type

**Recommended Measures:**
- pending_count

## Exposed Columns

- `employee_number` (varchar(64))
- `employee_name` (varchar(255))
- `approver_employee_number` (varchar(64))
- `approver_name` (varchar(255))
- `leave_type` (varchar(255))
- `leave_start_date` (date)
- `leave_end_date` (date)
- `requested_days` (numeric(8,2))
- `leave_apply_date` (timestamp)
- `approval_level_name` (text)
- `approval_status` (text)
- `approval_sequence` (bigint)
- `action_date` (date)
- `leave_reason` (text)
