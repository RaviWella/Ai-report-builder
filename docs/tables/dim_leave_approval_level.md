# dim_leave_approval_level

## Overview

**Business Purpose:**  
Approval hierarchy lookup.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Dimension  
**Domain:** Leave Management  
**Grain:** Approval hierarchy lookup  
**Primary Key:** leave_approval_level_sk  
**Business Key:** approval_level_code  
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
| `leave_approval_level_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `level_code` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `level_key` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `level_name` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `display_order` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
