# fct_lieu_leave_entitlement

## Overview

**Business Purpose:**  
Earned lieu leave entitlement event.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Leave Management  
**Grain:** Earned lieu entitlement event  
**Primary Key:** lieu_leave_entitlement_sk  
**Business Key:** source_entitlement_id  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- stg_lieu_leave_entitlement

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
| `lieu_entitlement_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_entitlement_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `calendar_date_sk` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `calendar_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `earned_lieu_days` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `adjusted_lieu_days` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `paid_lieu_days` | numeric(8,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `earning_source` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `earning_reason` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `final_status_code` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
