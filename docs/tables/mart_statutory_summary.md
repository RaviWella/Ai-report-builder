# mart_statutory_summary

## Overview

**Business Purpose:**  
TBD

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Mart  
**Domain:** Payroll  
**Grain:** Statutory rollup  
**Primary Key:** TBD  
**Business Key:** payroll_period_sk, legal_entity_name  
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
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `legal_entity_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_epf` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `employer_epf` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `etf` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `apit` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `taxable_payroll` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `employee_count` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_year` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_month` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_half` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_refreshed_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
