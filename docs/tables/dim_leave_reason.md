# dim_leave_reason

## Overview

**Business Purpose:**  
Predefined leave purpose lookup.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Dimension  
**Domain:** Leave Management  
**Grain:** Predefined leave purpose lookup  
**Primary Key:** leave_reason_sk  
**Business Key:** source_reason_id / reason_code  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- stg_leave_reason

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
| `leave_reason_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_reason_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `reason_name` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_legal_entity_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
