# fct_processed_attendance_payroll

## Overview

**Business Purpose:**  
TBD

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Payroll  
**Grain:** Attendance in payroll  
**Primary Key:** processed_attendance_payroll_sk  
**Business Key:** source_attendance_line_id  
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
| `attendance_payroll_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_attendance_line_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_group_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `attendance_item_type` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `attendance_days` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payable_days` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `absent_days` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `late_days` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `nopay_days` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `ot_hours` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `attendance_amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `attendance_deduction` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_timestamp` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
