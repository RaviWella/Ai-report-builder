# snap_leave_type

## Overview

**Business Purpose:**  
dbt snapshot history for dim_leave_type (feeds warehouse SCD2 dimensions).

**Schema:** `hr_snap`  
**Object Type:** Table  
**Layer:** Snapshot  
**Domain:** Leave Management  
**Grain:** SCD2 snapshot — SCD2 leave type (hr_leavetype)  
**Primary Key:** dbt_scd_id  
**Business Key:** leave_type_nk  
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
| `leave_type_nk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_leave_type_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_type_code` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_type_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_group_name` | varchar(128) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_paid_leave` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `affects_payroll` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `allow_half_day` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `allow_attachment` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `attachment_mandatory` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `entitlement_based` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `carry_forward_allowed` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `max_carry_forward_days` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `requires_approval` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `requires_coverup` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `leave_category` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_active` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `dbt_scd_id` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `dbt_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `dbt_valid_from` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `dbt_valid_to` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
