# snap_designation

## Overview

**Business Purpose:**  
dbt snapshot history for dim_designation (feeds warehouse SCD2 dimensions).

**Schema:** `hr_snap`  
**Object Type:** Table  
**Layer:** Snapshot  
**Domain:** Enterprise HR  
**Grain:** SCD2 snapshot — Job title / grade  
**Primary Key:** dbt_scd_id  
**Business Key:** designation_nk  
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
| Data Owner | HR Analytics |
| Technical Owner | Data Engineering |
| Classification | Internal |
| Contains PII | No |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `designation_nk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_desig_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `designation_code` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `designation_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | designation, job title, role |
| `grade_name` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `department_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `dbt_scd_id` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `dbt_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `dbt_valid_from` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `dbt_valid_to` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
