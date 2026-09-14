# fct_maternity_leave

## Overview

**Business Purpose:**  
One row per maternity leave request.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Leave Management  
**Grain:** One row per maternity leave request  
**Primary Key:** maternity_leave_sk  
**Business Key:** source_maternity_leave_id  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- stg_maternity_leave

**Consumers:**
- Semantic Views
- Reports
- AI Agent

## Governance

| Property | Value |
|----------|-------|
| Data Owner | HR Operations |
| Technical Owner | Data Engineering |
| Classification | Internal |
| Contains PII | No |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `maternity_leave_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_maternity_leave_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_type_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `maternity_start_date_sk` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `maternity_end_date_sk` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `maternity_start_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `maternity_end_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `expected_delivery_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `maternity_days` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `feeding_hours_allocated` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `feeding_hours_used` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `feeding_hours_eligible_flag` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `maternity_status_code` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `maternity_purpose` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
