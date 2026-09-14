# Semantic Layer — Deep Dive (Concept 1) + Enhancement Map

> Concept 1 එකේ semantic layer එක enhance කරන්න කලින් — current structure එක හරියටම, code-verified. Model → lifecycle → resolution → storage, ඊට පස්සේ enhancement targets (Concept 2 එක්ක compare කරලා). සියල්ල actual code references.

---

## 1. Domain model — [domain/semantic.py](backend/app/domain/semantic.py)

Catalog එක Pydantic models 9කින්. **මූලික rule:** physical names (table/column) `PhysicalColumn` එකේ විතරයි; AI දකින්නේ `ref`/`label`/`type` විතරයි.

```
SemanticCatalog (tenant_id, version)
├── entities: [Entity]
│     ├── name, key, base_schema, base_table, primary_key
│     ├── period_grain: PeriodGrain?  (year_column, month_column)
│     └── fields: [SemanticField]
│           ├── ref ("<entity>.<field>"), label, description, type, role
│           ├── physical: PhysicalColumn (table, column, schema_name)   ← AI never sees
│           ├── allowed_aggregations: [AggFn]   (measures only)
│           ├── sample_values: [str]?  (enum dimensions)
│           └── pii: bool
├── joins: [JoinDef]  (left/right entity, left/right key, join_type)  ← only DECLARED joins ever used
├── metrics: [MetricDef]   ← governed (separate table, see §4)
│     ├── key ("metric.<key>"), label, unit, kind
│     ├── kind = "aggregate" | "count" | "formula"
│     ├── agg, ref, distinct, expression, filters: [MetricFilter], aliases
└── glossary: [GlossaryTerm]   ← governed (separate table, see §4)
      ├── term, aliases, definition, category
      └── ref → metric.<key> or <entity>.<field>  (optional; can be documentary)
```

**Key types:**
- `FieldType` = STRING / INTEGER / DECIMAL / DATE / DATETIME / BOOLEAN
- `FieldRole` = DIMENSION / MEASURE
- `AggFn` = sum / avg / min / max / count / count_distinct
- `MetricDef.kind`: `aggregate` (agg over a measure), `count` (count/count-distinct), `formula` (arithmetic over OTHER metrics — ratios/nets)

**Resolution helpers (SemanticCatalog methods):**
| Method | Job |
|---|---|
| `field_index()` | `ref → SemanticField` |
| `metric_index()` | `key → MetricDef` |
| `glossary_index()` | `slug → GlossaryTerm` |
| `synonyms_for_ref()` | `ref → [NL phrases]` (glossary terms+aliases that point at a ref) — grounds deterministic NL resolver |
| `expand_field_refs()` | `metric.<k>` → underlying field refs (recursive through formula metrics); drops `calc.*` |
| `root_for()` | pick a root entity all referenced entities are join-reachable from |
| `metadata_for_ai()` | **the ONLY projection AI sees** — fields + metrics as `{ref,label,type,role,entity,...}`, no physical names |
| `glossary_for_ai()` | term→definition→ref list, grounds AI in tenant vocabulary |

---

## 2. Lifecycle — [services/semantic_service.py](backend/app/services/semantic_service.py)

### Bootstrap (zero-touch, SaaS onboarding)
`get_active_catalog(tenant_id)`:
1. `latest_version` නැත්නම් → `_ensure_tenant` (auto-provision tenants row) → `_assemble_catalog(version=1)` → save → commit (race-safe).
2. තිබුණොත් → load latest → `_attach_governed`.

### `_assemble_catalog` = curated seed + live introspection (fault-tolerant)
```
build_seed_catalog(tenant_id)              ← curated ER mapping (semantic_seed.py)
  + _introspect_paysheet()                 ← wide per-tenant pay items (mart_horizontal_paysheet_dynamic)
  + _transaction_entities()                ← Pay Item Summary + Payroll Period (Grand Summary)
  + _introspect_summary_marts()            ← mart_statutory_summary, …
```
හැම introspection එකක්ම `try/except` — datamart unreachable (VPN down) උනොත් **seed-only catalog** එක return වෙනවා, builder එක තවම වැඩ කරනවා.

### Introspection internals
- `introspect_datamart()` — `information_schema.columns` query, `vw_`/`mart_`/`dim_` objects විතරක් entities බවට. Types `_PG_TYPE_MAP` එකෙන් map; numeric → MEASURE, else DIMENSION. Joins **manual enrich** වෙනවා (auto-infer නෑ).
- `_column_meta()` — **`vw_data_dictionary` view එකට preference** (business descriptions + authoritative PII flags); නැත්නම් `information_schema` fallback.
- PII inference: `_looks_pii()` + dictionary flag (err on privacy side).
- Label humanization: `_humanize_label()` / `_humanize_payitem()` + acronym map (EPF/ETF/NIC/OT…).

### Versioning
- `rebuild_catalog()` — force fresh introspection → **new version** (admin).
- `refresh_if_changed()` — nightly job; `_field_refs()` (ref+type set) compare කරලා, **වෙනස් උනොත් විතරයි** version bump (duplicate versions වළක්වයි).
- `get_pinned_catalog(version)` — report එක save කරපු **exact version** එක → reproducibility.
- Versions **immutable & append-only** — පරණ reports කැඩෙන්නේ නෑ.

---

## 3. Resolution flow (how the layer is USED)

**Build-time (AI/builder):** `metadata_for_ai()` + `glossary_for_ai()` → AI/picker. AI returns `DataSpec` (refs only).
**NL→spec:** `intent_resolver` — glossary `synonyms_for_ref()` + fuzzy match (deterministic-first), AI leftovers වලට.
**Compile-time:** [compiler.py](backend/app/query_engine/compiler.py) — `resolve(ref)` → PhysicalColumn; `expand_field_refs` → metrics; `_apply_joins` → declared joins + period-grain alignment. Guards: `validate_refs`, `validate_joins`.

---

## 4. Storage & governance nuance ⚠️ (enhancement-critical)

- **Catalog (entities + joins)** → JSONB in `semantic_models`, versioned ([semantic_repo.py](backend/app/repositories/semantic_repo.py)).
- **Metrics + Glossary** → **SEPARATE tables**, loaded at resolve time by `_attach_governed()` (via `load_active_metrics` / `load_active_glossary`).

> 🔴 **Important:** `_attach_governed()` loads the **ACTIVE** metrics/glossary even for `get_pinned_catalog()`. ඒ කියන්නේ — entities/joins version-pinned වුණත්, **metric/glossary definitions pinned නෑ**. Metric එකක definition එක වෙනස් කළොත්, ඒක පරණ published reports වලටත් බලපානවා. Reproducibility එකට මේක gap එකක් — enhance කරනකොට මතක තියාගන්න.

---

## 5. Concept 1 vs Concept 2 — semantic layer richness

| Capability | **Concept 1** | **Concept 2** |
|---|---|---|
| Per-tenant catalog | ✅ inherent (JSONB versioned) | 🟡 base YAML + per-tenant overrides (`tenant_semantic_overrides`) |
| Entities/fields | ✅ dynamic, introspected + dictionary-enriched | 🟡 curated YAML topics→tables |
| Joins | ✅ declared `JoinDef` + period-grain alignment | join hint lines |
| Metrics | ✅ `MetricDef` (aggregate/count/formula) | ✅ `metric_catalog` |
| **Certified flag** | ❌ නෑ | ✅ `metric_catalog.certified` |
| **Forbidden/allowed agg rules** | 🟡 `allowed_aggregations` per field | ✅ `metric_aggregation_rules` (governed per metric) |
| **Query contracts (blocked cols)** | ❌ (guards validate refs, but no explicit blocklist contract) | ✅ `ai_query_contracts` |
| **Anomaly rules** | ❌ නෑ | ✅ `metric_anomaly_rules` |
| **Topics/keywords (NL routing)** | 🟡 glossary aliases/synonyms | ✅ `topics` keyword taxonomy |
| Glossary/synonyms | ✅ `GlossaryTerm` + `synonyms_for_ref` | ✅ `semantic_dictionary` |
| **Narrative templates** | ❌ නෑ | ✅ `narrative_templates` |
| Metric version-pinning | 🔴 not pinned (§4) | n/a (views stable) |
| AI-safe projection (no physical) | ✅ strict (`metadata_for_ai`) | 🟡 allowlist-based |

---

## 6. Enhancement targets (priority order)

### 🟢 High value, low effort
1. **Certify + govern metrics** — `MetricDef` එකට `certified: bool` + `owner` + `forbidden_aggregations` fields එකතු කරන්න. `metadata_for_ai` එකේ certified flag surface කරන්න. *(borrow Concept 2 `metric_catalog.certified` + `metric_aggregation_rules`)*
2. **Pin metrics/glossary to version** (§4 gap fix) — published report එකේ metric/glossary definitions snapshot කරන්න (JSONB එකට bake කරන්න, හෝ version-stamped metric table). Reproducibility close කරයි.
3. **Query contract / blocked-columns** — catalog එකට tenant-level `blocked_refs` + sensitive-column policy. Guards වල enforce. *(borrow `ai_query_contracts`)*

### 🟡 Medium
4. **Topic/keyword routing tier** — entities/metrics වලට `topics`/`keywords` metadata → NL resolver routing වැඩි දියුණු කරන්න (large catalog වලට scale). *(borrow Concept 2 `topics`)*
5. **Richer field metadata** — `format` (currency/percent/date-format), `synonyms` per field (දැන් glossary එකේ විතරයි), `default_aggregation`, `is_sensitive`.
6. **Join cardinality metadata** — `JoinDef` එකට `cardinality` (one-to-one/one-to-many) → symmetric-aggregate / fan-out detection (compiler correctness — period-grain root fix).

### 🟠 Larger
7. **Anomaly/validation rules per metric** — `metric_anomaly_rules` equivalent → data-quality surfacing.
8. **Aggregate/rollup sources on entities** — `Entity.aggregates[]` (pre-aggregated materialized sources) → aggregate-awareness (perf). *(ties to the Gap-1 perf work)*
9. **Narrative templates** — metric → insight text generation.

---

## 7. Where to touch (cheat-sheet)

| Change | File(s) |
|---|---|
| Add fields to model | [domain/semantic.py](backend/app/domain/semantic.py) |
| Bootstrap / introspection / versioning | [services/semantic_service.py](backend/app/services/semantic_service.py) |
| Curated seed entities/joins | [services/semantic_seed.py](backend/app/services/semantic_seed.py) |
| Metrics governance | [services/metrics_service.py](backend/app/services/metrics_service.py) |
| Glossary | [services/glossary_service.py](backend/app/services/glossary_service.py) |
| Storage / version | [repositories/semantic_repo.py](backend/app/repositories/semantic_repo.py) |
| Resolution / validation | [query_engine/compiler.py](backend/app/query_engine/compiler.py), [query_engine/guards.py](backend/app/query_engine/guards.py) |
| NL resolution | [services/intent_resolver.py](backend/app/services/intent_resolver.py) |
| API | [api/v1/semantic.py](backend/app/api/v1/semantic.py) |
| AI projection (what AI sees) | `metadata_for_ai()` / `glossary_for_ai()` in semantic.py |

> ⚠️ Model එකට field එකක් එකතු කරනකොට: (a) JSONB serialization backward-compatible (Pydantic default දාන්න — පරණ versions load වෙන්න ඕනේ), (b) `_field_refs()` change-detection එකට බලපාන්නේද බලන්න, (c) `metadata_for_ai` එකෙන් physical/sensitive කිසිවක් leak වෙන්නේ නැද්ද confirm කරන්න.
