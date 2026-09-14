# fct_processed_multi_currency_salary

## Overview

**Business Purpose:**  
TBD

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Payroll  
**Grain:** FX salary  
**Primary Key:** processed_multi_currency_salary_sk  
**Business Key:** source_multi_currency_id  
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
| `processed_multi_currency_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_multi_currency_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_currency` | varchar(16) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `target_currency` | varchar(16) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `exchange_rate` | numeric(14,6) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `salary_amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `converted_amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_timestamp` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
