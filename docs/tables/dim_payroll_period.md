# dim_payroll_period

## Overview

**Business Purpose:**  
Payroll calendar dimension (year × month × half).

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Dimension  
**Domain:** Payroll  
**Grain:** Year x month x half  
**Primary Key:** payroll_period_sk  
**Business Key:** year, month, half  
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
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_year` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_month` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_half` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `period_start_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `period_end_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_frequency` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_closed` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
