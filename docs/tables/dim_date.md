# dim_date

## Overview

**Business Purpose:**  
Calendar dimension — day grain; month-start dates link to snapshot_month.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Dimension  
**Domain:** Workforce  
**Grain:** Calendar  
**Primary Key:** date_sk  
**Business Key:** date_sk (calendar surrogate) / calendar_date if present  
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
| `date_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `calendar_date` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `year` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `month_number` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `day_of_month` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `day_of_week` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `year_month` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `month_start_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `month_end_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `quarter` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_weekend` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
