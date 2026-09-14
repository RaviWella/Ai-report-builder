# sv_vw_salary_bands

> Warehouse object: `vw_salary_bands` in schema `hr_semantic`

## Overview

**Purpose:** Semantic API view over mart_salary_band_summary.

**Entity:** Payroll  
**Grain:** One row per business grain of underlying mart/fact — TBD per query  
**Recommended Usage:** Reporting and AI queries (query `hr_semantic` only)  

**Upstream reads:** mart_salary_band_summary

## Recommended Filters

- `department_name` / `legal_entity` — org slice
- Period columns (`year_month`, `period_label`, `snapshot_month`) — time slice
- `is_current = true` on joined dimensions when applicable

## Join Dependencies

- mart_salary_band_summary

## AI Agent Metadata

**Natural Language Aliases:**
- salary bands
- compensation bands
- pay ranges

**Typical Questions:**
- Average salary by grade
- Headcount by salary band

**Recommended Dimensions:**
- grade_name
- designation_name
- legal_entity

**Recommended Measures:**
- avg_salary
- headcount

## Exposed Columns

- `salary_band_sk` (text)
- `tenant_id` (varchar(64))
- `source_system` (varchar(32))
- `legal_entity_name` (varchar(255))
- `designation_name` (text)
- `grade_name` (varchar(255))
- `headcount` (bigint)
- `min_salary` (numeric)
- `max_salary` (numeric)
- `avg_salary` (numeric)
- `median_salary` (numeric)
- `payroll_cost` (numeric)
- `_refreshed_at` (timestamp)
