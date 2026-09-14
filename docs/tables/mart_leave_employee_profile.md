# mart_leave_employee_profile

## Overview

**Business Purpose:**  
Employee leave behavior profile.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Mart  
**Domain:** Leave Management  
**Grain:** Employee leave behavior profile  
**Primary Key:** TBD  
**Business Key:** emp_no  
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
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_no` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | employee number, employee code, staff id |
| `emp_fullname` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | employee name, full name, staff name |
| `department_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | department, dept, org unit |
| `designation` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `legal_entity` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_applications` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approved_applications` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `rejected_applications` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `cancelled_applications` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `pending_applications` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_requested_days` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_approved_days` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `ytd_approved_days` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `avg_approval_duration_hours` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `sick_leave_days` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `short_leave_count` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `short_leave_deducted_days` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `short_leave_hours_total` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `last_leave_start_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `first_leave_start_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `sick_leave_ratio_pct` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_refreshed_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
