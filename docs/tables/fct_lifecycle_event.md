# fct_lifecycle_event

## Overview

**Business Purpose:**  
Career lifecycle fact (one row per event). PIT join to dim_employee on effective_date.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Workforce  
**Grain:** TBD  
**Primary Key:** lifecycle_event_sk  
**Business Key:** source_lifecycle_id  
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
| Data Owner | HR Analytics |
| Technical Owner | Data Engineering |
| Classification | Internal |
| Contains PII | No |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_lifecycle_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `effective_date_sk` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `effective_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `event_category` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `event_name` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_position_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `previous_designation` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `new_designation` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `previous_grade` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `new_grade` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `previous_location` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `new_location` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `new_legal_entity` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `new_company_section` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `new_section` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `new_salary` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `previous_salary` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `reason` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `triggered_by_emp_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `approved_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `last_working_date` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `parent_source_lifecycle_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_loaded_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
