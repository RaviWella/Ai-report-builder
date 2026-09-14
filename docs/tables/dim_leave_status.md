# dim_leave_status

## Overview

**Business Purpose:**  
Normalized leave workflow status lookup.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Dimension  
**Domain:** Leave Management  
**Grain:** Normalized workflow status lookup  
**Primary Key:** leave_status_sk  
**Business Key:** status_code  
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
| `leave_status_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `status_code` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `status_name` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_status_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
