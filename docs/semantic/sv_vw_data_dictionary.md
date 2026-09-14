# sv_vw_data_dictionary

> Warehouse object: `vw_data_dictionary` in schema `hr_semantic`

## Overview

**Purpose:** TBD

**Entity:** Enterprise HR  
**Grain:** One row per business grain of underlying mart/fact — TBD per query  
**Recommended Usage:** Reporting and AI queries (query `hr_semantic` only)  

**Upstream reads:** TBD

## Recommended Filters

- `department_name` / `legal_entity` — org slice
- Period columns (`year_month`, `period_label`, `snapshot_month`) — time slice
- `is_current = true` on joined dimensions when applicable

## Join Dependencies

- TBD

## AI Agent Metadata

**Natural Language Aliases:**
- TBD

**Typical Questions:**
- TBD

**Recommended Dimensions:**
- TBD

**Recommended Measures:**
- TBD

## Exposed Columns

- `tenant_id` (varchar(64))
- `schema_name` (varchar(64))
- `object_name` (varchar(128))
- `object_type` (varchar(32))
- `layer` (varchar(32))
- `domain` (varchar(64))
- `object_grain` (text)
- `object_description` (text)
- `ordinal_position` (integer)
- `field_name` (varchar(128))
- `data_type` (varchar(128))
- `nullable` (text)
- `pk` (text)
- `fk` (varchar(255))
- `description` (text)
- `source` (text)
- `pii` (boolean)
- `sensitive` (boolean)
- `dictionary_generated_at` (timestamp)
