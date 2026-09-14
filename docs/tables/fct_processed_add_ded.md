# fct_processed_add_ded

## Overview

**Business Purpose:**  
Vertical additions/deductions fact from processed_sal_add_ded.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Enterprise HR  
**Grain:** Add/ded line  
**Primary Key:** processed_add_ded_sk  
**Business Key:** source_add_ded_id  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- processed_sal_add_ded → stg_payroll_add_ded

**Consumers:**
- Semantic Views
- Reports
- AI Agent

## Governance

| Property | Value |
|----------|-------|
| Data Owner | HR Analytics |
| Technical Owner | Data Engineering |
| Classification | Internal |
| Contains PII | No |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `processed_add_ded_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_add_ded_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_payroll_group_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `canonical_pay_item_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_item_name` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_item_code` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `add_ded_type` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `quantity` | numeric(14,4) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `rate` | numeric(14,4) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_epf_applicable` | boolean | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `process_timestamp` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_group_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
