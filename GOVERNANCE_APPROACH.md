# Governance Workstream — Approach (Concept 1)

> Next gap after performance: **governed, trustworthy numbers** for a fully-dynamic product. C2 එකේ certified metrics + forbidden-agg rules + query contracts තියෙනවා; C1 එකේ නෑ (හෝ enforce වෙන්නේ නෑ). Goal: dynamic ස්වභාවය නැති නොකර, numbers trustworthy කරන එක.

Two code-grounded findings shape this:
- 🔴 **`allowed_aggregations` exists but is NOT enforced.** Set in seed/introspection ([semantic_seed.py](backend/app/services/semantic_seed.py), [semantic_service.py](backend/app/services/semantic_service.py)) but the compiler never checks it — a spec can `AVG` an ID or `SUM` a rate. (grep: only assignments, no read in `query_engine/`.)
- 🟢 **Metrics/glossary stored as full JSON** (`semantic_metrics.definition` JSONB) — adding `MetricDef` fields is **zero-migration**.

---

## G1 — Enforce `allowed_aggregations` (close the open gap) 🟢🟢 *highest value / lowest effort*

**මොකද:** spec එකක field එකක් මත value-aggregation (`sum/avg/min/max`) apply කරනකොට, ඒ field එකේ `allowed_aggregations` එකේ ඒක තියෙනවද check කරනවා. නැත්නම් → `GuardError`. (`count`/`count_distinct` ඕන field එකකට OK — headcount වගේ; restrict වෙන්නේ value-aggs විතරයි.)

**Where:** [compiler.py](backend/app/query_engine/compiler.py) — `apply_aggregate` call වෙන තැන් 2 (`spec.fields[].agg`, `spec.aggregations[].fn`). Lookup `catalog.field_index()[ref].allowed_aggregations`.

**Why it matters:** fully-dynamic product එකක AI/user ඕන agg එකක් ඉල්ලන්න පුළුවන් → nonsensical numbers (avg of NIC, sum of attendance_rate) block වෙනවා. C2 `metric_aggregation_rules` එකේ equivalent — **data දැනටමත් තියෙනවා, enforce කරනවා විතරයි.**

**Safety:** config-gated (`query_enforce_allowed_aggregations`, default ON-able after audit) — හෝ lenient mode (empty allowed list = unrestricted). Tests: allowed agg → OK; disallowed → GuardError; count on dimension → OK.

---

## G2 — Certify + govern metrics 🟢 *zero-migration*

**Model** ([domain/semantic.py](backend/app/domain/semantic.py) `MetricDef`) — add (defaults → backward-compatible JSON):
```python
certified: bool = False
certified_by: str | None = None
certified_at: str | None = None
owner: str | None = None
```

**Service** ([metrics_service.py](backend/app/services/metrics_service.py) `define`):
- Certified metric එකක් **re-define කරන්න AdminRoles + explicit re-certify** ඕනේ (silent drift block). Certify = separate action/flag.
- `certified_at` stamp on certify (timestamp via API layer — compiler/service `Date.now` restriction නෑ, normal runtime).

**AI projection** (`metadata_for_ai`) — `certified` + `owner` surface කරනවා → AI/field-picker certified metrics prefer කරනවා, uncertified ඒවා "draft" විදිහට mark.

**Why:** "Headcount" / "Total Net Pay" වගේ numbers **certified, single-definition** — dynamic වුණත් report දෙකක එකම answer. Finance/payroll trust.

**Tests:** certify → flag set + surfaced; re-define certified without re-cert → rejected; metadata_for_ai shows certified.

---

## G3 — Metric/glossary version-pinning (reproducibility) 🟢 *fixes deep-dive §4*

**Problem:** `_attach_governed()` ([semantic_service.py](backend/app/services/semantic_service.py)) loads **ACTIVE** metrics/glossary even for `get_pinned_catalog()` → metric definition වෙනස් කළොත් පරණ published reports වලටත් බලපානවා (reproducibility break).

**Fix (two options):**
- **A (simple, recommended):** publish වෙනකොට, active metrics/glossary **resolved set එක version snapshot එකට bake** කරනවා (catalog JSONB එකේ `metrics`/`glossary` fields දැනටමත් තියෙනවා — ඒවට write කරනවා). `get_pinned_catalog` → pinned governed set; `get_active_catalog` → `_attach_governed` (live). Migration නෑ.
- **B (richer):** metric rows version කරලා, report version එකට `metrics_version_ref` pin කරනවා (column + migration).

**Recommendation:** A — zero migration, reproducibility close කරනවා, governance work එකේ natural part.

**Tests:** publish → pinned catalog freezes metric defs; active metric change → old version unchanged, new version sees change.

---

## G4 — Query contract / blocked refs (sensitive policy) 🟡 *later*

Tenant-level `blocked_refs` (e.g. raw PII never selectable) → `guards.validate_refs` එකේ enforce. Catalog/policy එකේ store. C2 `ai_query_contracts` equivalent. (PII දැනටමත් AI ට යන්නේ නෑ; මේක *selection* policy.)

---

## Build order + effort

| # | Item | Impact | Effort | |
|---|---|---|---|---|
| G1 | Enforce allowed_aggregations | nonsensical numbers block — dynamic trust | **Low** | 🟢 මුලින්ම |
| G2 | Certified metrics (+ AI surfacing) | governed single-definition numbers | Low-Med | 🟢 |
| G3 | Metric/glossary version-pinning | reproducibility (§4 gap) | Med | 🟢 |
| G4 | Blocked-refs contract | sensitive-column policy | Med | 🟡 later |

**Recommended first slice:** **G1 + G2** — දෙකම low effort, zero/near-zero migration, dynamic-trust එකට decisive. G3 ඊට පස්සේ (reproducibility), G4 optional.

## Touch points
| Item | File(s) |
|---|---|
| G1 enforce | [compiler.py](backend/app/query_engine/compiler.py) (+ [config.py](backend/app/core/config.py) flag) |
| G2 model | [domain/semantic.py](backend/app/domain/semantic.py) `MetricDef`, `metadata_for_ai` |
| G2 service/API | [metrics_service.py](backend/app/services/metrics_service.py), [api/v1/semantic.py](backend/app/api/v1/semantic.py) |
| G3 pinning | [semantic_service.py](backend/app/services/semantic_service.py) `_attach_governed`, [template_service.py](backend/app/services/template_service.py) publish |
| G4 contract | [guards.py](backend/app/query_engine/guards.py), catalog/policy store |
