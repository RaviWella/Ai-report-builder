# mart_payroll_reconciliation

## Overview

**Business Purpose:**  
TBD

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Mart  
**Domain:** Payroll  
**Grain:** Group x period reconcile  
**Primary Key:** TBD  
**Business Key:** payroll_group_sk, payroll_period_sk, payroll_group_name  
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
| `payroll_group_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_group_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_year` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_month` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_half` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `gross_salary_total` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `net_salary_total` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `total_additions` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_deductions` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `epf_employee_total` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `epf_employer_total` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `etf_total` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `tax_total` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `loan_deduction_totals` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `attendance_deduction_total` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_count` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_variance` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `reconciliation_status` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_refreshed_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
