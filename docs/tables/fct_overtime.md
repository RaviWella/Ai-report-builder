# fct_overtime

## Overview

**Business Purpose:**  
Overtime fact per employee × day (derived from attendance until prl_overtime is staged).

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Attendance  
**Grain:** TBD  
**Primary Key:** overtime_sk  
**Business Key:** source_emp_id, source_ot_id  
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
| Data Owner | Workforce Analytics |
| Technical Owner | Data Engineering |
| Classification | Internal |
| Contains PII | No |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_ot_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `ot_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_ot_hours` | numeric(10,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
