# fct_short_leave_usage

## Overview

**Business Purpose:**  
One row per short leave request.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Leave Management  
**Grain:** One row per short leave request  
**Primary Key:** short_leave_usage_sk  
**Business Key:** source_short_leave_id  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- stg_short_leave

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
| `short_leave_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_short_leave_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_type_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_leave_type_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `request_date_sk` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `short_leave_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `start_time` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `end_time` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `short_leave_hours` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deducted_leave_days` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `duration_category` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `time_category` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `short_leave_status_code` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `purpose` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
