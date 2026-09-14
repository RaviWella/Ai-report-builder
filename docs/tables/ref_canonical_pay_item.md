# dim_canonical_pay_item

## Overview

**Business Purpose:**  
Canonical mapping for dynamic payroll line labels (seed-driven; API extensible).

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Dimension  
**Domain:** Payroll  
**Grain:** Normalized pay components  
**Primary Key:** canonical_pay_item_sk  
**Business Key:** canonical_pay_item_code  
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
| Contains PII | Yes |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `canonical_pay_item_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_item_name` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `canonical_item_name` | text | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `canonical_category` | text | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `payroll_behavior` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_taxable` | boolean | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `is_epf_applicable` | boolean | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `item_type` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
