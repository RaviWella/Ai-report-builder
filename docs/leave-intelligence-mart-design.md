# Leave Intelligence Mart — MintHRM Warehouse Design

**Version:** 1.0 (aligned with MintHRM datamart conventions)  
**Domain:** Leave Management  
**Platform:** PostgreSQL / dbt / multi-tenant warehouse (`hrm_wh_{tenant_id}`)  
**Status:** Planned (Phase 0 interim objects exist today)

---

## 1. Purpose

Enterprise leave reporting, analytics, operational dashboards, and AI-assisted report generation across the MintHRM Yii leave module (~74 source tables).

The leave mart extends the existing dimensional model used for Enterprise HR, Attendance, and Payroll Phase 6. It reuses conformed dimensions and follows the same naming and semantic-layer strategy.

---

## 2. Warehouse alignment

### Schemas

| Schema | Role |
|--------|------|
| `hr_raw` | Staging landing (`stg_*`) |
| `hr` | Physical dimensions, facts, marts |
| `hr_semantic` | Stable `vw_*` views for BI and AI agents |
| `hr_control` | ETL / dbt metadata |

### Naming conventions (MintHRM standard)

| Pattern | Use |
|---------|-----|
| `dim_*` | Conformed or domain dimensions |
| `fct_*` | Atomic transactional facts |
| `mart_*` | BI-ready aggregates (not `agg_*`) |
| `vw_*` | Semantic reporting views |
| `*_sk` | Surrogate keys (`employee_sk`, `leave_type_sk`, `date_sk`) |

**Do not create** duplicate enterprise dimensions. **Do not use** `dim_calendar` — reuse **`dim_date`**.

### Reused conformed dimensions

| Dimension | Leave usage |
|-----------|-------------|
| `dim_employee` | Employee analytics (SCD2) |
| `dim_date` | Calendar / fiscal analytics |
| `dim_designation` | Workforce analytics |
| `dim_org_unit` | Department hierarchy |
| `dim_shift` | Attendance-linked leave |

---

## 3. Current state (Phase 0 — implemented)

| Object | Schema | Notes |
|--------|--------|-------|
| `stg_leave_types` | `hr_raw` | From `hr_leavetype` |
| `stg_leave_requests` | `hr_raw` | From `hr_leaveapplication` (+ date subquery) |
| `fact_leave_balance` | `hr` | **Legacy name** — approved standard leave only; interim bridge |
| `vw_leave_summary` | `hr_semantic` | Reads `fact_leave_balance` + `dim_employee` |

Phase 0 covers **standard leave applications only**. It does not unify short/lieu/maternity/educational/day-off/planner modules.

---

## 4. Target architecture

```text
MintHRM MySQL (~74 leave tables)
    ↓  CDC / ETL
hr_raw.stg_*  (module-specific staging)
    ↓  dbt integration
hr.dim_leave_*  (new leave dimensions)
    ↓
hr.fct_leave_*  (atomic facts)
    ↓
hr.mart_leave_*  (aggregates)
    ↓
hr_semantic.vw_*  (AI-safe reporting)
```

---

## 5. Source module map

MintHRM leave is not a single table — it is parallel workflows unified in the warehouse.

| Module | Primary source tables | `dim_leave_source` value |
|--------|----------------------|---------------------------|
| Standard leave | `hr_leaveapplication`, `hr_leaveapplication_dates`, `hr_leaveapplication_superiors` | `STANDARD` |
| Short leave | `hr_short_leave`, `config_short_leave_*` | `SHORT` |
| Lieu leave | `hr_lieu_leave`, `lieu_leave_entitlement_data`, `lieu_leave_*` | `LIEU` |
| Maternity | `hr_leave_maternity`, `prl_maternity_leaveentitle`, `feeding_hours_*` | `MATERNITY` |
| Educational | `hr_edulv_application`, `hr_edulv_*` | `EDUCATIONAL` |
| Day off | `hr_day_off`, `day_off_settings` | `DAY_OFF` |
| Planner | `hr_leave_planner`, `hr_leave_planner_dates` | `PLANNER` |

### Entitlement / balance sources

| Source table | Warehouse target |
|--------------|------------------|
| `prl_leaveentitle` | `fct_leave_balance_snapshot` |
| `hr_leave_balance` | `fct_leave_balance_snapshot` |
| `prl_maternity_leaveentitle` | `fct_leave_balance_snapshot` (maternity slice) |
| `prl_leaveentitlehistory` | Balance adjustment audit (staging → snapshot deltas) |

### Leave type configuration

| Source | Target |
|--------|--------|
| `hr_leavetype` | `dim_leave_type` |
| `hr_leavetype_group`, `hr_leavetype_group_assign` | `dim_leave_type.leave_group_name` |
| `hr_leavetype_property` | Extended type attributes |
| `hr_predefine_leave_purpose` | `dim_leave_reason` |

---

## 6. New dimensions

### 6.1 `dim_leave_type` (SCD2)

**Grain:** One row per leave type version.

| Column | Description |
|--------|-------------|
| `leave_type_sk` | Surrogate key |
| `source_leave_type_id` | Source PK (internal `hr` only) |
| `leave_type_code` | Short code |
| `leave_type_name` | Display name |
| `leave_group_name` | Group from `hr_leavetype_group` |
| `is_paid_leave` | Paid / unpaid |
| `affects_payroll` | Payroll impact |
| `allow_half_day` | Half-day allowed |
| `entitlement_based` | Uses entitlement |
| `carry_forward_allowed` | Carry-forward flag |
| `requires_approval` | Workflow required |
| `leave_category` | STANDARD / SHORT / LIEU / etc. |
| `is_current`, `effective_from`, `effective_to` | SCD2 |

### 6.2 `dim_leave_status`

Normalized workflow status (Pending, Approved, Rejected, Cancelled, HR Approved, Cover-Up Pending, Superior Pending, Auto Approved).

### 6.3 `dim_leave_reason`

From `hr_predefine_leave_purpose`.

### 6.4 `dim_leave_source`

Distinguishes origin module (see Section 5).

### 6.5 `dim_leave_approval_level`

Cover Up → Supervisor → HR → Final Approval.

---

## 7. Core facts

### 7.1 `fct_leave_application` ★ central fact

**Grain:** One row per leave application (all modules unified via `leave_source_sk`).

**Primary sources:** `hr_leaveapplication`, `hr_short_leave`, `hr_lieu_leave`, `hr_leave_maternity`, `hr_edulv_application`, `hr_day_off`.

| Key column | Role |
|------------|------|
| `leave_application_sk` | Surrogate key |
| `source_application_id` | Source transaction ID + source module discriminator |
| `employee_sk` | FK → `dim_employee` |
| `leave_type_sk` | FK → `dim_leave_type` |
| `leave_status_sk` | FK → `dim_leave_status` |
| `leave_source_sk` | FK → `dim_leave_source` |
| `leave_reason_sk` | FK → `dim_leave_reason` |
| `request_date_sk`, `start_date_sk`, `end_date_sk`, `approval_date_sk` | FK → `dim_date` |

**Measures:** `requested_days`, `approved_days`, `unpaid_days`, `leave_hours`, `rejected_days`, `cancelled_days`.

**Partition:** Monthly on `start_date_sk` (recommended).

**Replaces:** `fact_leave_balance` (deprecate after migration).

### 7.2 `fct_leave_daily`

**Grain:** Employee × leave date.

**Source:** `hr_leaveapplication_dates` + expanded ranges from other modules.

Critical for attendance integration, daily occupancy, overlapping leave detection.

| Key column | Role |
|------------|------|
| `leave_daily_sk` | Surrogate key |
| `leave_application_sk` | FK → `fct_leave_application` |
| `employee_sk` | FK → `dim_employee` |
| `date_sk` | FK → `dim_date` |
| `leave_type_sk`, `leave_status_sk` | FKs |
| `is_half_day`, `half_day_type` | Half-day flags |
| `is_holiday_overlap`, `is_weekend_overlap` | Calendar overlap |

### 7.3 `fct_leave_balance_snapshot`

**Grain:** Employee × leave type × snapshot date (daily recommended).

**Sources:** `prl_leaveentitle`, `hr_leave_balance`, `prl_maternity_leaveentitle`.

**Measures:** `entitled_days`, `earned_days`, `used_days`, `remaining_days`, `carry_forward_days`, `encashed_days`, `expired_days`, `pending_approval_days`.

### 7.4 `fct_leave_approval`

**Grain:** One row per approval action.

**Sources:** `hr_leaveapplication_superiors`, `hr_lieu_leaveapplication_superiors`, `hr_leave_maternity_superiors`, `hr_edulv_superior_approval`.

### 7.5 Module-specific facts (Phase 3)

| Fact | Grain | Source |
|------|-------|--------|
| `fct_lieu_leave_entitlement` | Earned lieu event | `lieu_leave_entitlement_data`, Concept Two adjustments |
| `fct_short_leave_usage` | Short leave request | `hr_short_leave` |
| `fct_maternity_leave` | Maternity request | `hr_leave_maternity` |
| `fct_leave_planner` | Planned leave | `hr_leave_planner` |

---

## 8. Marts (Phase 4)

| Mart | Grain | Purpose |
|------|-------|---------|
| `mart_leave_monthly_summary` | Month × department × leave type | Executive dashboards |
| `mart_leave_employee_profile` | Employee | Behavior analytics (sick frequency, approval delay) |
| `mart_department_leave_heatmap` | Department × date | Calendar / occupancy heatmap |

---

## 9. Semantic views (`hr_semantic`)

| View | Upstream | Purpose |
|------|----------|---------|
| `vw_current_leave_balance` | `fct_leave_balance_snapshot` | Current balances (LLM-friendly) |
| `vw_employee_leave_history` | `fct_leave_application`, `fct_leave_daily` | Unified history |
| `vw_pending_leave_approvals` | `fct_leave_approval` | Operational approval queue |
| `vw_leave_liability` | `fct_leave_balance_snapshot` | Payroll liability / expiring leave |
| `vw_leave_utilization` | `mart_leave_monthly_summary` | Utilization KPIs |

**Interim:** `vw_leave_summary` remains until `vw_employee_leave_history` ships.

### AI / DataHub guidance

- Report agents and DataHub consumers should query **`hr_semantic` only**.
- Expose business keys (`emp_no`, leave type name) — hide `source_*_id` in semantic views.
- Every SCD dimension exposes `is_current = true` for deterministic LLM SQL.

---

## 10. ER relationships

| From | To | Join |
|------|-----|------|
| `fct_leave_application` | `dim_employee` | `employee_sk` |
| `fct_leave_application` | `dim_leave_type` | `leave_type_sk` |
| `fct_leave_application` | `dim_date` | `start_date_sk` |
| `fct_leave_daily` | `fct_leave_application` | `leave_application_sk` |
| `fct_leave_daily` | `dim_employee` | `employee_sk` |
| `fct_leave_daily` | `dim_date` | `date_sk` |
| `fct_leave_balance_snapshot` | `dim_employee` | `employee_sk` |
| `fct_leave_balance_snapshot` | `dim_leave_type` | `leave_type_sk` |
| `fct_leave_approval` | `fct_leave_application` | `leave_application_sk` |
| `mart_leave_monthly_summary` | `fct_leave_daily` | aggregates |

Full planned ER: [`datamart-er.yml`](datamart-er.yml) → `planned_domain_models.leave`.

---

## 11. ETL strategy

### Phase 1 CDC priority

```text
hr_leaveapplication
hr_leaveapplication_dates
hr_leavetype
prl_leaveentitle
hr_leave_balance
```

### Incremental columns (recommended)

| Source | Column |
|--------|--------|
| `hr_leaveapplication` | `updated_at` |
| `prl_leaveentitle` | `modified_date` |
| `hr_short_leave` | `updated_date` |

### Snapshot jobs

| Snapshot | Frequency |
|----------|-----------|
| Leave balance | Daily |
| Leave liability | Month-end |
| Entitlement status | Daily |

---

## 12. Data quality rules

**Applications**

- End date ≥ start date
- Leave days ≥ 0
- Employee and leave type must exist in conformed dims
- Approval date ≥ request date

**Balances**

- `remaining_days` ≥ 0 (or flagged exception)
- `used_days` ≤ `entitled_days` + carry-forward within policy
- No duplicate employee + leave type + overlapping date range (dedup test)

---

## 13. Implementation phases

| Phase | Status | Deliverables |
|-------|--------|--------------|
| **0** | ✅ Implemented | `stg_leave_*`, `fact_leave_balance`, `vw_leave_summary` |
| **1** | ✅ Implemented | `dim_leave_type`, `dim_leave_status`, `dim_leave_source`, `fct_leave_application`, `fct_leave_daily`, `stg_leave_application_dates` |
| **2** | ✅ Implemented | `dim_leave_approval_level`, `fct_leave_balance_snapshot`, `fct_leave_approval`, semantic views (balance, history, pending) |
| **3** | ✅ Implemented | Short/lieu/maternity/planner staging + module facts; unified `fct_leave_application` |
| **4** | ✅ Implemented | Marts + `vw_leave_liability`, `vw_leave_utilization`; `dim_leave_reason` |

---

## 14. Business KPIs

| KPI | Definition |
|-----|------------|
| Leave utilization rate | Used / entitled |
| Sick leave ratio | Sick days / total leave days |
| Unplanned leave rate | Emergency leave % |
| Leave approval SLA | Avg approval duration (hours) |
| Leave liability | Remaining paid leave × cost basis |
| Department absence rate | Leave days / workforce days |
| Short leave frequency | Short leaves per employee per period |
| Lieu earn rate | Earned lieu days / eligible attendance events |

---

## 15. Related documentation

| Document | Purpose |
|----------|---------|
| [`datamart-er.yml`](datamart-er.yml) | ER source of truth (includes `planned_domain_models.leave`) |
| [`HR_DATAMART_ER.pdf`](HR_DATAMART_ER.pdf) | Section 4 — Leave Intelligence (planned) |
| [`README.md`](README.md) | How to update ER when implementing phases |

---

## 16. Migration note: `fact_leave_balance` → `fct_leave_application`

1. Build `fct_leave_application` from existing `stg_leave_requests` + new date staging.
2. Point `vw_leave_summary` at semantic successor (`vw_employee_leave_history` or thin wrapper).
3. Keep `fact_leave_balance` as deprecated view alias for one release cycle if external reports depend on it.
4. Update `datamart-er.yml` `domain_models` when physical models land on disk.
