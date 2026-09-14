# mart_dynamic_pay_items

## Overview

**Business Purpose:**  
TBD

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Mart  
**Domain:** Enterprise HR  
**Grain:** Dynamic pay items  
**Primary Key:** TBD  
**Business Key:** payroll_period_sk, canonical_pay_item_sk, variable_item_name  
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
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `canonical_pay_item_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `variable_item_name` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_count` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `avg_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `max_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `min_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_refreshed_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
