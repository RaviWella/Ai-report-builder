# fct_processed_tax

## Overview

**Business Purpose:**  
Processed tax breakdown per employee × period × tax component.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Payroll  
**Grain:** Tax component  
**Primary Key:** processed_tax_sk  
**Business Key:** source_tax_id  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- processed_tax_data_for_employee → stg_payroll_tax

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
| `processed_tax_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_tax_id` | bigint | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tax_amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tax_type` | varchar(255) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `taxable_income` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `tax_relief_amount` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `tax_percentage` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `annualized_taxable_income` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `process_timestamp` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
