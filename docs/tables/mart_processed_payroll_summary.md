# mart_processed_payroll_summary

## Overview

**Business Purpose:**  
Primary payroll BI mart per employee × period (§8.1).

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Mart  
**Domain:** Payroll  
**Grain:** Emp x period BI summary  
**Primary Key:** TBD  
**Business Key:** emp_no  
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
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_group_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_year` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_month` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_half` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `period_start_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `period_end_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_no` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | employee number, employee code, staff id |
| `emp_fullname` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | employee name, full name, staff name |
| `designation` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_category` | varchar(128) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `legal_entity` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `branch` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_group_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `basic_salary` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `gross_salary` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | gross pay, gross earnings |
| `total_additions` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_deductions` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `net_salary` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | net pay, take home pay |
| `tax_amount` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `epf_employee_amount` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `epf_employer_amount` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `etf_amount` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `pay_cut_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `increment_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `ot_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `nopay_deduction` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_currency` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_status` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_timestamp` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_refreshed_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
