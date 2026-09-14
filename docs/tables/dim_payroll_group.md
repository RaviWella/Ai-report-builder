# dim_payroll_group

## Overview

**Business Purpose:**  
Payroll processing group dimension (from hr_payroll_groups).

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Dimension  
**Domain:** Payroll  
**Grain:** Payroll run group  
**Primary Key:** payroll_group_sk  
**Business Key:** source_payroll_group_id  
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
| Data Owner | Payroll |
| Technical Owner | Data Engineering |
| Classification | Internal |
| Contains PII | No |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `payroll_group_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_payroll_group_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_group_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `legal_entity_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `currency_code` | varchar(16) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_frequency` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_active` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
