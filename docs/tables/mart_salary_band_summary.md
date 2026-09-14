# mart_salary_band_summary

## Overview

**Business Purpose:**  
Current compensation bands by legal entity, designation, and grade (active employees).

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Mart  
**Domain:** Payroll  
**Grain:** Band x period summary  
**Primary Key:** TBD  
**Business Key:** salary_band_sk, legal_entity_name, designation_name, grade_name  
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
| `salary_band_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `legal_entity_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `designation_name` | text | Yes | - | TBD | TBD | TBD | No | No | designation, job title, role |
| `grade_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `headcount` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `min_salary` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `max_salary` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `avg_salary` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `median_salary` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `payroll_cost` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_refreshed_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
