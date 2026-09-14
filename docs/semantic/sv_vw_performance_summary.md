# sv_vw_performance_summary

> Warehouse object: `vw_performance_summary` in schema `hr_semantic`

## Overview

**Purpose:** Semantic API view over performance staging.

**Entity:** Enterprise HR  
**Grain:** One row per business grain of underlying mart/fact — TBD per query  
**Recommended Usage:** Reporting and AI queries (query `hr_semantic` only)  

**Upstream reads:** performance staging

## Recommended Filters

- `department_name` / `legal_entity` — org slice
- Period columns (`year_month`, `period_label`, `snapshot_month`) — time slice
- `is_current = true` on joined dimensions when applicable

## Join Dependencies

- performance staging

## AI Agent Metadata

**Natural Language Aliases:**
- performance
- appraisal
- review scores

**Typical Questions:**
- Performance ratings summary

**Recommended Dimensions:**
- TBD

**Recommended Measures:**
- TBD

## Exposed Columns

- `employee_id` (integer)
- `department_id` (integer)
- `branch_id` (integer)
- `period_label` (varchar(32))
- `review_year` (integer)
- `overall_score` (numeric(6,2))
- `rating` (varchar(64))
- `status` (text)
