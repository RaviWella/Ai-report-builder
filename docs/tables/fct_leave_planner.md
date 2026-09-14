# fct_leave_planner

## Overview

**Business Purpose:**  
One row per planned leave.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Leave Management  
**Grain:** One row per planned leave  
**Primary Key:** leave_planner_sk  
**Business Key:** source_planner_id  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- stg_leave_planner

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
| `leave_planner_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_planner_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_type_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `actual_leave_application_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `planned_start_date_sk` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `planned_end_date_sk` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `planned_start_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `planned_end_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `planned_days` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `utilized_days` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `variance_days` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `planner_status` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `planner_purpose` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
