# sv_vw_payroll_summary

> Warehouse object: `vw_payroll_summary` in schema `hr_semantic`

## Overview

**Purpose:** Semantic API view over mart_processed_payroll_summary, payroll facts.

**Entity:** Payroll  
**Grain:** One row per business grain of underlying mart/fact — TBD per query  
**Recommended Usage:** Reporting and AI queries (query `hr_semantic` only)  

**Upstream reads:** mart_processed_payroll_summary, payroll facts

## Recommended Filters

- `department_name` / `legal_entity` — org slice
- Period columns (`year_month`, `period_label`, `snapshot_month`) — time slice
- `is_current = true` on joined dimensions when applicable

## Join Dependencies

- mart_processed_payroll_summary, payroll facts

## AI Agent Metadata

**Natural Language Aliases:**
- payroll
- salary
- compensation
- payslip

**Typical Questions:**
- Total gross payroll this month
- Net pay by department
- Payroll summary by period

**Recommended Dimensions:**
- period_label
- department_name
- legal_entity

**Recommended Measures:**
- gross_salary
- net_salary
- total_deductions

## Exposed Columns

- `tenant_id` (varchar(64))
- `employee_sk` (text)
- `employee_id` (integer)
- `department_id` (integer)
- `branch_id` (integer)
- `period_label` (text)
- `payroll_year` (integer)
- `payroll_month` (integer)
- `payroll_half` (integer)
- `emp_no` (varchar(64))
- `emp_fullname` (varchar(255))
- `designation` (text)
- `legal_entity` (varchar(255))
- `branch` (varchar(255))
- `payroll_group_name` (varchar(255))
- `basic_salary` (numeric)
- `gross_salary` (numeric)
- `total_additions` (numeric)
- `total_deductions` (numeric)
- `net_salary` (numeric)
- `tax_amount` (numeric)
- `epf_employee_amount` (numeric)
- `epf_employer_amount` (numeric)
- `etf_amount` (numeric)
- `pay_cut_amount` (numeric)
- `increment_amount` (numeric)
- `run_status` (text)
