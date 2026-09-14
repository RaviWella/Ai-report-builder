# fct_compliance_payroll

## Overview

**Business Purpose:**  
EPF/ETF compliance amounts from processed salary statutory columns.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Payroll  
**Grain:** Statutory slice  
**Primary Key:** compliance_payroll_sk  
**Business Key:** source_compliance_id  
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
| `compliance_payroll_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_compliance_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `compliance_salary` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `compliance_ot` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `compliance_nopay` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `compliance_attendance_days` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `compliance_work_hours` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `compliance_status` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_timestamp` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
