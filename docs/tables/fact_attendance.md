# fact_attendance

## Overview

**Business Purpose:**  
Daily attendance fact — one row per employee per day.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Attendance  
**Grain:** TBD  
**Primary Key:** id  
**Business Key:** id  
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
| `id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `attendance_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `year` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `month` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `period_label` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `check_in` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `check_out` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `status` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `late_minutes` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `early_leave_minutes` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `overtime_minutes` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `work_hours` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `shift_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_present` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_late` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `has_overtime` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `overtime_hours` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
