# mart_horizontal_paysheet_core

## Overview

**Business Purpose:**  
Paysheet core columns per employee × period.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Mart  
**Domain:** Payroll  
**Grain:** Wide paysheet core  
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
| `emp_no` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | employee number, employee code, staff id |
| `emp_fullname` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | employee name, full name, staff name |
| `designation` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `branch` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_group_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_year` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_month` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_half` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `basic_salary` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `gross_salary` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | gross pay, gross earnings |
| `net_salary` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | net pay, take home pay |
| `total_allowance` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_deduction` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `ot_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `bonus_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tax_amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `epf_employee` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `epf_employer` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `etf_amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `nopay_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `loan_deduction` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `pay_cut_amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `increment_amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_currency` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_status` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_refreshed_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
