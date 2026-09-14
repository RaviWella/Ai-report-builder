# sv_vw_turnover

> Warehouse object: `vw_turnover` in schema `hr_semantic`

## Overview

**Purpose:** Semantic API view over lifecycle / employment facts.

**Entity:** Workforce  
**Grain:** One row per business grain of underlying mart/fact — TBD per query  
**Recommended Usage:** Reporting and AI queries (query `hr_semantic` only)  

**Upstream reads:** lifecycle / employment facts

## Recommended Filters

- `department_name` / `legal_entity` — org slice
- Period columns (`year_month`, `period_label`, `snapshot_month`) — time slice
- `is_current = true` on joined dimensions when applicable

## Join Dependencies

- lifecycle / employment facts

## AI Agent Metadata

**Natural Language Aliases:**
- turnover
- attrition
- leavers

**Typical Questions:**
- Turnover rate
- Who left this quarter?

**Recommended Dimensions:**
- department_name
- period

**Recommended Measures:**
- TBD

## Exposed Columns

- `employee_id` (integer)
- `department_id` (integer)
- `branch_id` (integer)
- `status` (text)
- `separation_type` (text)
- `period_label` (text)
- `year` (integer)
