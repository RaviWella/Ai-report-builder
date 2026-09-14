# fct_salary_bank_instruction

## Overview

**Business Purpose:**  
Bank payment instructions by employee × payroll period.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Payroll  
**Grain:** Salary bank payment instruction by employee x period x account  
**Primary Key:** salary_bank_instruction_sk  
**Business Key:** source_salary_bank_data_id  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- prl_salary_retrieve → stg_payroll_salary_retrieve
- prl_salary_bank_data → stg_payroll_salary_bank_data

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
| Contains PII | Yes |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `salary_bank_instruction_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_salary_bank_data_id` | integer | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `source_salary_retrieve_id` | integer | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_group_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `bank_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `bank_branch_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_bank_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_bank_branch_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `bank_acc_no` | text | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `bank_amount` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `bank_passbook_name` | text | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `is_primary_account` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_bank` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
