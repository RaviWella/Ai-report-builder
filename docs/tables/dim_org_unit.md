# dim_org_unit

## Overview

**Business Purpose:**  
Org hierarchy dimension from company_hierarchy / stg_departments.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Dimension  
**Domain:** Workforce  
**Grain:** Organization hierarchy  
**Primary Key:** org_unit_sk  
**Business Key:** source_org_unit_id / org_unit_code  
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
| `org_unit_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_hierarchy_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `org_unit_code` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `org_unit_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `unit_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `parent_hierarchy_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `level_2_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `level_3_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `level_4_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
