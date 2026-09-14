# sv_vw_employment_monthly

> Warehouse object: `vw_employment_monthly` in schema `hr_semantic`

## Overview

**Purpose:** Semantic API view over fct_employment_snapshot.

**Entity:** Workforce  
**Grain:** One row per business grain of underlying mart/fact — TBD per query  
**Recommended Usage:** Reporting and AI queries (query `hr_semantic` only)  

**Upstream reads:** fct_employment_snapshot

## Recommended Filters

- `department_name` / `legal_entity` — org slice
- Period columns (`year_month`, `period_label`, `snapshot_month`) — time slice
- `is_current = true` on joined dimensions when applicable

## Join Dependencies

- fct_employment_snapshot

## AI Agent Metadata

**Natural Language Aliases:**
- employment snapshot
- monthly employment

**Typical Questions:**
- Employment state at month end

**Recommended Dimensions:**
- snapshot_month
- designation

**Recommended Measures:**
- headcount

## Exposed Columns

- `tenant_id` (varchar(64))
- `source_system` (varchar(32))
- `period_label` (text)
- `snapshot_month` (date)
- `active_headcount` (bigint)
- `resigned_headcount_eom` (bigint)
- `terminated_headcount_eom` (bigint)
- `other_non_active_headcount_eom` (bigint)
- `prior_month_active_headcount` (bigint)
- `net_active_headcount_change_mom` (bigint)
- `monthly_salary_cost_active` (numeric)
- `avg_years_of_service_active` (numeric)
- `fte_equivalent` (numeric)
