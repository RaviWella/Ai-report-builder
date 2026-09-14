# fct_variable_pay_item

## Overview

**Business Purpose:**  
Dynamic variable additions/deductions fact.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Enterprise HR  
**Grain:** Variable pay line  
**Primary Key:** variable_pay_item_sk  
**Business Key:** source_variable_id, variable_item_type  
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
| Data Owner | HR Analytics |
| Technical Owner | Data Engineering |
| Classification | Internal |
| Contains PII | No |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `variable_pay_item_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_variable_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `variable_item_type` | varchar(16) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_payroll_group_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `canonical_pay_item_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `variable_item_name` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_considered_for_payroll` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_timestamp` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
