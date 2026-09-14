# fact_payroll

## Overview

**Business Purpose:**  
Legacy payroll view — refs fct_processed_salary (Phase 6).

**Schema:** `hr`  
**Object Type:** View  
**Layer:** Fact  
**Domain:** Payroll  
**Grain:** Legacy view of fct_processed_salary  
**Primary Key:** id  
**Business Key:** same as fct_processed_salary (compatibility view)  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- TBD

**Consumers:**
- Semantic Views
- Reports
- AI Agent

## Governance

| Property | Value |
|----------|-------|
| Data Owner | Payroll |
| Technical Owner | Data Engineering |
| Classification | Internal |
| Contains PII | No |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_run_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `department_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `branch_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_year` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_month` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `period_label` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `run_status` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `basic_salary` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `allowances` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `overtime_pay` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `bonuses` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `gross_salary` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | gross pay, gross earnings |
| `tax_deduction` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `other_deductions` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_deductions` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `net_salary` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | net pay, take home pay |
