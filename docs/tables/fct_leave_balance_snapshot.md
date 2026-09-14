# fct_leave_balance_snapshot

## Overview

**Business Purpose:**  
Employee x leave type x snapshot date balance.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Leave Management  
**Grain:** Employee x leave type x snapshot date  
**Primary Key:** leave_balance_snapshot_sk  
**Business Key:** balance_source, source_balance_id, snapshot_date  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- hr_leave_balance → stg_leave_balance

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
| `balance_snapshot_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `balance_source` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_balance_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `snapshot_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `snapshot_date_sk` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_type_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_leave_type_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_type_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `entitled_days` | numeric(10,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `earned_days` | numeric(10,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `used_days` | numeric(10,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `remaining_days` | numeric(10,2) | Yes | - | TBD | TBD | TBD | No | No | leave balance, balance days |
| `carry_forward_days` | numeric(10,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `encashed_days` | numeric(10,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `expired_days` | numeric(10,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `pending_approval_days` | numeric(10,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `entitlement_year` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `balance_status` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `period_start_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `period_end_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `expiry_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
