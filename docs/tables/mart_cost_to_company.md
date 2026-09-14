# mart_cost_to_company

## Overview

**Business Purpose:**  
TBD

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Mart  
**Domain:** Payroll  
**Grain:** Cost to company (CTC)  
**Primary Key:** TBD  
**Business Key:** employee_sk, payroll_period_sk  
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
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `basic_salary` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `employer_epf` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `etf` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `bonuses` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `ot` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `non_cash_benefits` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_compensation` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_refreshed_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
