# mart_leave_monthly_summary

## Overview

**Business Purpose:**  
Month x department x leave type rollup.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Mart  
**Domain:** Leave Management  
**Grain:** Month x department x leave type  
**Primary Key:** TBD  
**Business Key:** year  
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
| `leave_monthly_summary_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `year` | smallint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `month_number` | smallint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `year_month` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `org_unit_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `department_name` | text | Yes | - | TBD | TBD | TBD | No | No | department, dept, org unit |
| `leave_type_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_type_name` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_type_code` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_leave_days` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_leave_hours` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approved_leave_days` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `pending_leave_days` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `unpaid_leave_hours` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employees_on_leave` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employees_with_approved_leave` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `half_day_leave_count` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_daily_row_count` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `avg_approved_days_per_employee` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_refreshed_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
