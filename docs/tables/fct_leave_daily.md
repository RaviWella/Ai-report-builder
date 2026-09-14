# fct_leave_daily

## Overview

**Business Purpose:**  
One row per employee per leave date.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Leave Management  
**Grain:** Employee x leave date  
**Primary Key:** leave_daily_sk  
**Business Key:** source_leave_date_id  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- hr_leaveapplication_dates → stg_leave_application_dates

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
| `leave_daily_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_leave_date_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_application_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_type_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_status_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `date_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `date_key` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_application_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_source_code` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_leave_type_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `header_leave_status_code` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_day_count` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_hours` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `unpaid_leave_hours` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_half_day` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `half_day_type` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `coverup_approved` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `superior_approved` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `hr_approved` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_weekend_overlap` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_holiday_overlap` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `attendance_adjustment_flag` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
