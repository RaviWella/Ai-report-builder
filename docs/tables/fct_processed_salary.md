# fct_processed_salary

## Overview

**Business Purpose:**  
Processed payroll snapshot fact. Grain: employee_sk × payroll_period_sk × payroll_group_sk.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Payroll  
**Grain:** Emp x period x group  
**Primary Key:** processed_salary_sk  
**Business Key:** source_processed_salary_id  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- processed_sal_basic_data → stg_payroll_details

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
| `processed_salary_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | ETL tenant_id var | ETL extract + dbt conformed join | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_processed_salary_id` | integer | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `payroll_run_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | dim_employee via source_emp_id | ETL extract + dbt conformed join | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | dim_payroll_period via year/month/half | ETL extract + dbt conformed join | No | No | TBD |
| `payroll_group_sk` | text | Yes | - | TBD | dim_payroll_group via source_payroll_group_id | ETL extract + dbt conformed join | No | No | TBD |
| `source_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_payroll_group_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `period_label` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `basic_salary` | numeric(14,2) | Yes | - | TBD | processed_sal_basic_data.psb_basic_or_day_salary | ETL extract + dbt conformed join | No | Yes | TBD |
| `total_additions` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `gross_salary` | numeric(14,2) | Yes | - | TBD | processed_sal_basic_data.gross_salary_vw / psb_sub_total | ETL extract + dbt conformed join | No | Yes | gross pay, gross earnings |
| `total_deductions` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `net_salary` | numeric(14,2) | Yes | - | TBD | processed_sal_basic_data.psb_net_total | ETL extract + dbt conformed join | No | Yes | net pay, take home pay |
| `tax_amount` | numeric(14,2) | Yes | - | TBD | processed_sal_basic_data.psb_tax | ETL extract + dbt conformed join | No | Yes | TBD |
| `epf_employee_amount` | numeric(14,2) | Yes | - | TBD | processed_sal_basic_data.psb_epf8 | ETL extract + dbt conformed join | No | Yes | TBD |
| `epf_employer_amount` | numeric(14,2) | Yes | - | TBD | processed_sal_basic_data.psb_epf12 | ETL extract + dbt conformed join | No | Yes | TBD |
| `etf_amount` | numeric(14,2) | Yes | - | TBD | processed_sal_basic_data.psb_epf3 | ETL extract + dbt conformed join | No | Yes | TBD |
| `pay_cut_amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `increment_amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_timestamp` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | ETL load timestamp | ETL extract + dbt conformed join | No | No | TBD |
| `process_year` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_month` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_half` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `processed_month` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `ot_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `bonus_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `attendance_deduction` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `nopay_deduction` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `loan_deduction` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `installment_deduction` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `service_charge` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `currency_code` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `exchange_rate` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_multi_currency` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_compliance_processed` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `original_process_reference` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `reversal_timestamp` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `reversed_by` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `reversal_reason` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_status` | varchar(255) | Yes | - | TBD | processed_sal_basic_data.process_status | ETL extract + dbt conformed join | No | No | TBD |
