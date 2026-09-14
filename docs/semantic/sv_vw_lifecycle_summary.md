# sv_vw_lifecycle_summary

> Warehouse object: `vw_lifecycle_summary` in schema `hr_semantic`

## Overview

**Purpose:** Semantic API view over fct_lifecycle_event.

**Entity:** Workforce  
**Grain:** One row per business grain of underlying mart/fact — TBD per query  
**Recommended Usage:** Reporting and AI queries (query `hr_semantic` only)  

**Upstream reads:** fct_lifecycle_event

## Recommended Filters

- `department_name` / `legal_entity` — org slice
- Period columns (`year_month`, `period_label`, `snapshot_month`) — time slice
- `is_current = true` on joined dimensions when applicable

## Join Dependencies

- fct_lifecycle_event

## AI Agent Metadata

**Natural Language Aliases:**
- lifecycle
- joiners
- promotions
- transfers

**Typical Questions:**
- Joiners this month
- Promotions by department

**Recommended Dimensions:**
- event_category
- department_name

**Recommended Measures:**
- event_count

## Exposed Columns

- `tenant_id` (varchar(64))
- `source_system` (text)
- `period_label` (text)
- `event_category` (text)
- `event_name` (text)
- `employee_id` (integer)
- `department_id` (integer)
- `branch_id` (integer)
- `effective_date` (date)
- `new_salary` (numeric(14,2))
- `previous_salary` (numeric(14,2))
