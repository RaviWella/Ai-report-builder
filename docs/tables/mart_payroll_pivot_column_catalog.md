# mart_payroll_pivot_column_catalog

## Overview

**Business Purpose:**  
Discovered dynamic paysheet column catalog per tenant.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Mart  
**Domain:** Payroll  
**Grain:** Tenant x pivot_key dynamic paysheet column catalog  
**Primary Key:** TBD  
**Business Key:** Aggregate grain (see grain column)  
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
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `pivot_key` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `pivot_label` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `pivot_type` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `line_count` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_count` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_refreshed_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
