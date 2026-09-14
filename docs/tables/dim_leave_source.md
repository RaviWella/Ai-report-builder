# dim_leave_source

## Overview

**Business Purpose:**  
Leave module origin lookup.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Dimension  
**Domain:** Leave Management  
**Grain:** Leave module origin lookup  
**Primary Key:** leave_source_sk  
**Business Key:** leave_source_code  
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
| `leave_source_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_code` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_name` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `display_order` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_implemented` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
