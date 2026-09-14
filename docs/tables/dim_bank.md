# dim_bank

## Overview

**Business Purpose:**  
Payroll bank dimension.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Dimension  
**Domain:** Payroll  
**Grain:** Bank master  
**Primary Key:** bank_sk  
**Business Key:** source_bank_id  
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
| `bank_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_bank_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `bank_code` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `bank_name` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
