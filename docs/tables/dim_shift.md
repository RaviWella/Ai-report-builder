# dim_shift

## Overview

**Business Purpose:**  
SCD Type 2 shift dimension from snap_shift.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Dimension  
**Domain:** Attendance  
**Grain:** Work shift  
**Primary Key:** shift_sk  
**Business Key:** source_shift_id / shift_code  
**SCD Type:** Type 2  
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

## SCD Type 2

**Dimension Type:** Type 2  
**Current Row Logic:** `is_current = true`  
**History Logic:** `valid_from` / `valid_to` (or `effective_from` / `effective_to`)  

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `shift_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_shift_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `shift_name` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `valid_from` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `valid_to` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_current` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `version_number` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
