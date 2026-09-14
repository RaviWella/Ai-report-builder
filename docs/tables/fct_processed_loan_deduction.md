# fct_processed_loan_deduction

## Overview

**Business Purpose:**  
Loan and installment deductions from processed_loan_data / installments.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Payroll  
**Grain:** Loan deduction  
**Primary Key:** processed_loan_deduction_sk  
**Business Key:** source_loan_deduction_id  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- processed_loan_data → stg_payroll_loan_deductions

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
| `processed_loan_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_type` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_group_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `loan_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `installment_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `installment_no` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `installment_amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `remaining_balance` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_final_installment` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_timestamp` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_loan_deduction_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
