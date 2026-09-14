# fct_payroll_process_execution

## Overview

**Business Purpose:**  
Payroll run execution metadata (from stg_payroll_runs / processed snapshots).

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Payroll  
**Grain:** Run metadata  
**Primary Key:** payroll_process_execution_sk  
**Business Key:** TBD  
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
| `payroll_process_execution_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_group_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_start_time` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_end_time` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_duration_seconds` | bigint | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `processed_employee_count` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `failed_employee_count` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `reversed_employee_count` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_type` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_status` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `triggered_by` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
