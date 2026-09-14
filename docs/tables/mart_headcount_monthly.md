# mart_headcount_monthly

## Overview

**Business Purpose:**  
Monthly tenant-level workforce snapshot from fct_employment_snapshot. Headcount and status splits are month-end (EOM) point-in-time.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Mart  
**Domain:** Workforce  
**Grain:** Org x month headcount  
**Primary Key:** TBD  
**Business Key:** headcount_monthly_sk, snapshot_month_sk  
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
| `headcount_monthly_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `snapshot_month` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `snapshot_month_sk` | text | Yes | - | dim_date.date_sk for the first calendar day of snapshot_month. | TBD | TBD | No | No | TBD |
| `active_headcount` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `resigned_headcount_eom` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `terminated_headcount_eom` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `other_non_active_headcount_eom` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `prior_month_active_headcount` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `net_active_headcount_change_mom` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `monthly_salary_cost_active` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `avg_years_of_service_active` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `fte_equivalent` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_refreshed_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
