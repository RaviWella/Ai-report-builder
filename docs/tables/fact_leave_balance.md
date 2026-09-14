# fact_leave_balance

## Overview

**Business Purpose:**  
Legacy leave balance view — approved applications from fct_leave_application.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Leave Management  
**Grain:** Legacy approved-leave summary over fct_leave_application  
**Primary Key:** id  
**Business Key:** id (legacy bridge)  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- fct_leave_application

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
| `id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_type_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_type_code` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_type_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_paid` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `period_label` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `year` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `days_requested` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `days_approved` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `days_entitled` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `balance_days` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `sick_days` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
