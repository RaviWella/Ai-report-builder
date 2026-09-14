# fct_salary_change

## Overview

**Business Purpose:**  
Salary revision fact from hr_lifecycle pay-change rows. PIT join to dim_employee.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Payroll  
**Grain:** TBD  
**Primary Key:** salary_change_sk  
**Business Key:** source_increment_id  
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
| `source_system` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_increment_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `effective_date_sk` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `effective_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `change_type` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `previous_salary` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `new_salary` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `change_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `change_pct` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `designation_at_change` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `grade_at_change` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `legal_entity_at_change` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approved_by_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approved_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `reason` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `event_name` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
