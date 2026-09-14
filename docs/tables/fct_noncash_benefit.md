# fct_noncash_benefit

## Overview

**Business Purpose:**  
TBD

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Enterprise HR  
**Grain:** Non-cash benefit  
**Primary Key:** noncash_benefit_sk  
**Business Key:** source_noncash_benefit_id  
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
| `noncash_benefit_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_noncash_benefit_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `benefit_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `benefit_type` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `benefit_value` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `taxable_value` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `process_timestamp` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
