# dim_canonical_pay_item_seed

## Overview

**Business Purpose:**  
TBD

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Dimension  
**Domain:** Payroll  
**Grain:** TBD  
**Primary Key:** canonical_pay_item_seed_sk  
**Business Key:** source_item_name  
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
| `tenant_id` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_item_name` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `canonical_item_name` | text | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `canonical_category` | text | Yes | - | TBD | TBD | TBD | Yes | No | TBD |
| `payroll_behavior` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_taxable` | boolean | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `is_epf_applicable` | boolean | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `item_type` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
