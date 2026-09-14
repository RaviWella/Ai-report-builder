# dim_leave_type

## Overview

**Business Purpose:**  
SCD2 leave type dimension (hr_leavetype).

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Dimension  
**Domain:** Leave Management  
**Grain:** SCD2 leave type (hr_leavetype)  
**Primary Key:** leave_type_sk  
**Business Key:** source_leave_type_id, valid_from  
**SCD Type:** Type 2  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- stg_leave_types

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

## SCD Type 2

**Dimension Type:** Type 2  
**Current Row Logic:** `is_current = true`  
**History Logic:** `valid_from` / `valid_to` (or `effective_from` / `effective_to`)  

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `leave_type_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
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
| `valid_from` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `valid_to` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_current` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `version_number` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
