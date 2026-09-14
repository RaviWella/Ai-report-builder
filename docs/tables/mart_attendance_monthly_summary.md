# mart_attendance_monthly_summary

## Overview

**Business Purpose:**  
Monthly per-employee attendance and OT rollups for BI dashboards.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Mart  
**Domain:** Attendance  
**Grain:** Employee x month attendance  
**Primary Key:** TBD  
**Business Key:** employee_sk, year, month_number  
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
| Data Owner | Workforce Analytics |
| Technical Owner | Data Engineering |
| Classification | Internal |
| Contains PII | No |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `year` | smallint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `month_number` | smallint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `year_month` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_no` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | employee number, employee code, staff id |
| `emp_fullname` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | employee name, full name, staff name |
| `legal_entity` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `designation` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `grade` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `days_present` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `days_absent` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `days_on_holiday_worked` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `days_late` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `days_early_leave` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_worked_hours` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_overtime_hours` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_late_minutes` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_early_leave_minutes` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `attendance_rate_pct` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `punctuality_rate_pct` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `manual_punch_count` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `manual_punch_rate_pct` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_refreshed_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
