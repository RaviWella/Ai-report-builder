# mart_department_leave_heatmap

## Overview

**Business Purpose:**  
Department x calendar date absence heatmap.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Mart  
**Domain:** Leave Management  
**Grain:** Department x calendar date occupancy  
**Primary Key:** TBD  
**Business Key:** calendar_date  
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
| Data Owner | HR Operations |
| Technical Owner | Data Engineering |
| Classification | Internal |
| Contains PII | No |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `department_leave_heatmap_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `calendar_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `calendar_date_sk` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `org_unit_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `department_name` | text | Yes | - | TBD | TBD | TBD | No | No | department, dept, org unit |
| `employees_on_leave` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approved_leave_days` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `pending_leave_days` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employees_with_any_leave_status` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `department_headcount` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `absence_rate_pct` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_refreshed_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
