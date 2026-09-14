# fct_leave_approval

## Overview

**Business Purpose:**  
One row per leave approval action.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Leave Management  
**Grain:** One row per approval action  
**Primary Key:** leave_approval_sk  
**Business Key:** source_approval_id  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- stg_leave_approvals
- stg_leave_requests

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
| `leave_approval_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_approval_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_application_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `applicant_employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approver_employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_approval_level_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approval_status_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `action_date_sk` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `action_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_application_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_source_code` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_approver_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approval_level_code` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approval_level_name` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approval_status_code` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `application_status_code` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approval_sequence` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approval_comment` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_final_approval` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `created_timestamp` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `updated_timestamp` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
