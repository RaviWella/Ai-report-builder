# fct_leave_application

## Overview

**Business Purpose:**  
One row per leave application (Phase 1 standard leave).

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Leave Management  
**Grain:** One row per leave application (all implemented modules)  
**Primary Key:** leave_application_sk  
**Business Key:** source_application_id, leave_source_code  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- hr_leaveapplication → stg_leave_requests

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
| `leave_application_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_application_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_source_code` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_type_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_status_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_source_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_reason_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `request_date_sk` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `start_date_sk` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `end_date_sk` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approval_date_sk` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_leave_type_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_status_code` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_status_code` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_final_status_code` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_purpose_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_approved_by` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `start_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `end_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `request_date` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approval_date` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `requested_days` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approved_days` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | leave taken, days on leave |
| `unpaid_days` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `rejected_days` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `cancelled_days` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_reason_text` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_hr_approval` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `cancelled_flag` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emergency_leave_flag` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `attachment_submitted_flag` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_impacted_flag` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_planned_leave` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approval_duration_hours` | numeric(10,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `created_timestamp` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `updated_timestamp` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
