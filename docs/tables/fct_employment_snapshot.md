# fct_employment_snapshot

## Overview

**Business Purpose:**  
Monthly employment state at month-end with FKs to dim_employee, dim_designation (PIT), and dim_org_unit.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Fact  
**Domain:** Workforce  
**Grain:** TBD  
**Primary Key:** employment_snapshot_sk  
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
| Data Owner | HR Analytics |
| Technical Owner | Data Engineering |
| Classification | Internal |
| Contains PII | No |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `employment_snapshot_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `org_unit_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `designation_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `snapshot_month` | date | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_status` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employment_type` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employment_category` | varchar(128) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `carder` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `legal_entity_id` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_active` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_on_probation` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `is_resigned` | boolean | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `basic_salary` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `years_of_service` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenure_band` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_source_updated_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `source_system` | varchar(32) | Yes | - | TBD | TBD | TBD | No | No | TBD |
