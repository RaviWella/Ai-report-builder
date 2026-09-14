# Report Builder — Concept 1 vs Concept 2

> Data mart එකෙන් data view කරන්න approach දෙකක්. දෙකේම **semantic layer** එකක් තියෙනවා, නමුත් data එකට ළඟා වෙන (data access) ක්‍රමය වෙනස්. මේ doc එක තීරණයක් ගන්න — SaaS product එකකට (≈200 clients) මොකද ගැළපෙන්නේ කියලා.

| | **Concept 1** | **Concept 2** |
|---|---|---|
| Branch / Folder | `feat/ai-report-builder` (Mint-Report-Bulder) | `Mint-Report-Bulder- Sawinu` |
| One line | **Mart + Job execute** — spec එක compile කරලා mart එකට live read-only query එකක් run කරනවා | **Manual Views** — හදපු dbt/SQL views මතින් query කරනවා |
| Semantic layer | Dynamic, per-tenant, JSONB, auto-introspected + AI-enriched | Curated, version-controlled YAML + DB catalog |
| Data access surface | Compiler එක physical columns වලට resolve කරනවා → parameterized SQL | Hand-written `vw_*` views (dbt + custom SQL templates) |
| Materialization | නෑ — on-demand execute + Redis result cache (snapshot-keyed) | Views (zero storage, query-time compute) + per-tenant sync |
| Multi-tenancy | per-tenant DB `hrm_wh_{tenant_id}` + search_path scoping | per-tenant DB + schema + explicit `WHERE tenant_id` filters |

---

## Concept 1 — "Mart + Job Execute" (current branch)

### එක මොකක්ද?
User report එකක් හදනකොට AI ට පේන්නේ `metadata_for_ai()` විතරයි (physical names, data නෑ). AI එකෙන් එන්නේ structured **DataSpec** එකක් — SQL නෙවෙයි. Run කරනකොට:

```
DataSpec → compiler.py (semantic refs → physical columns)
         → parameterized SQLAlchemy Select
         → guards (SELECT-only, join reachable, row limit)
         → result cache lookup (tenant | sql_hash | params | snapshot_ref)
         → [miss] read-only replica එකට execute
         → run log (sql_hash + result_checksum + snapshot_ref + semantic_version)
         → Excel/PDF render
```

Semantic catalog එක නිතරම (nightly job) datamart එක introspect කරලා auto-update වෙනවා; පරණ published reports පරණ version එකට pinned නිසා කැඩෙන්නේ නෑ.

### ✅ Plus
- **Self-service / dynamic** — අලුත් report එකකට DB එකේ අලුත් view එකක් හදන්න ඕනේ නෑ. Field catalogue එකේ තියෙන ඕන combination එකක් AI/builder එකෙන් compile වෙනවා.
- **Zero schema drift maintenance** — datamart එක වෙනස් වුණොත් nightly introspect එකෙන් catalog එක auto-sync වෙනවා. Manual SQL edit නෑ.
- **Audit-grade lineage** — හැම run එකකම `compiled_sql_hash + result_checksum + snapshot_ref`. Reproducible, compliance වලට ලොකු plus එකක්.
- **Strong safety model** — AI SQL ලියන්නේ නෑ; parameterized SQL විතරයි, 3-layer read-only enforcement, `assert_select_only()`. SQL injection surface එකක් නෑ.
- **Result caching built-in** — snapshot-keyed Redis cache + single-flight. Warehouse refresh වෙනකොට cache auto-invalidate (key එක වෙනස් වෙනවා).
- **Version pinning** — පරණ report exact ව reproduce කරන්න පුළුවන් (semantic version + snapshot).

### ❌ Minus
- **Performance unpredictable** — query එක compiler එකෙන් generate වෙන නිසා, මට්ටම් optimize කරපු hand-tuned joins නෑ. Complex/heavy reports වලදී mart එකට බර වැඩි වෙන්න පුළුවන් (view tuning නෑ).
- **Compiler complexity** — period-grain joins වගේ edge cases compiler එකේ handle කරන්න ඕනේ (memory එකේ "period-grain-join-fix" issue එක මේකේ symptom එකක්). Logic එක backend code එකේ.
- **Black-box-ish SQL** — DBA කෙනෙකුට "මේ report එක මොන SQL එකද run කරන්නේ" කියලා කලින් predict කරන්න අමාරුයි (generated, per-spec).
- **AI dependency** — NL→spec path එකේ quality එක AI/glossary/metrics config එක මත. Determinism වැඩිකරන්න extra layers (glossary, canonical metrics) දාලා තියෙනවා.

---

## Concept 2 — "Manual Views" (Sawinu folder)

### එක මොකක්ද?
Data access surface එක = **hand-written views**. දෙ වර්ගයක්:
1. **dbt semantic views** — `models/semantic/vw_*.sql` (26ක්, `materialized='view'`). dbt `{{ ref() }}` මගින් per-tenant resolve.
2. **Custom report views** — SQL templates (`alembic/data/custom_report_sql/vw_*.sql`) → `tenant_custom_reports` table එකේ store → `custom_reports_sync.py` මගින් per-tenant warehouse එකට `CREATE OR REPLACE VIEW` කරනවා (`{tenant_id}_custom_reports` schema).

Semantic layer එක curated YAML (`semantic_catalog.yaml`) + DB catalog (`metric_catalog`, `semantic_dictionary`, `ai_query_contracts`). Question එකක් resolve වෙනකොට topics/dimensions/metrics match කරලා grounded views වලට යොමු කරනවා.

```
Question → resolve_semantics() → schema_broker (allowlist + grounding)
        → LLM SQL gen (datamart) OR YAML metric resolver (HR metrics)
        → execute against vw_* (semantic / custom_reports schema)
        → JSON
```

### ✅ Plus
- **Predictable performance** — views hand-tuned. Common reports වලට optimized joins; DBA ට tune කරන්න පුළුවන්.
- **Governance / certified metrics** — `metric_catalog` එකේ `certified` flag, aggregation rules, anomaly rules. Finance/payroll-grade governance.
- **Traceable & reviewable** — හැම view එකක්ම version-controlled SQL (git/migration). Code review, approval workflow පුළුවන්.
- **dbt ecosystem** — lineage, tests, docs, materialization control නොමිලේම එනවා. Standard, hire කරන්න පහසු skillset.
- **Explicit tenant isolation** — `WHERE tenant_id = '{tenant_id}'` + per-tenant schema. "RLS magic" නෑ, predictable.
- **Stable contract** — view = stable interface. Underlying mart වෙනස් වුණත් view එක නොවෙනස්ව තියාගන්න පුළුවන් (abstraction).

### ❌ Minus
- **Not self-service** — අලුත් report එකකට අලුත් SQL view එකක් ලියන්න + migration + sync ඕනේ. Code change + deploy cycle එකක්. (200 clients කෙනෙක්ට custom report එකක් කිව්වොත් engineering bottleneck).
- **Schema drift maintenance** — datamart schema එක වෙනස් වුණොත් views manually update කරන්න ඕනේ; catalog↔warehouse sync එක tooling එකෙන් උදව් වුණත් manual oversight ඕනේ.
- **View sprawl at scale** — tenant 200 × custom reports → දහස් ගණන් views warehouse එකේ. Sync, versioning, drift across tenants manage කරන්න operational බරක්.
- **LLM still writes SQL (datamart chat path)** — allowlist/contracts වලින් guard කරලා තිබුණත්, Concept 1 එකේ "AI SQL ලියන්නේම නෑ" model එකට වඩා surface එක ලොකුයි.
- **Per-tenant divergence risk** — tenant overrides + custom views එක්ක, tenants අතර behaviour drift වෙන්න පුළුවන් (consistency එක maintain කරන්න discipline ඕනේ).

---

## SaaS, 200 clients — මොකද ගැළපෙන්නේ?

දෙකේම තනි තනිව ශක්තීන් තියෙනවා, නමුත් **scale + multi-tenant SaaS** එකකට මේ trade-off එක මූලිකයි:

> **Self-service flexibility (Concept 1) vs Governed predictability (Concept 2)**

### 200 clients කියන්නේ:
- හැම client කෙනෙක්ටම custom reports ඕනේ වෙයි → Concept 2 එකේ "අලුත් view = code+deploy" model එක **engineering bottleneck** එකක් වෙනවා.
- නමුත් payroll/statutory reports වලට **certified, predictable, auditable** numbers ඕනේ → Concept 2 එකේ governance එක ලොකු වටිනාකමක්.

### නිර්දේශය: **Hybrid — Concept 1 base + Concept 2 governance**

| Need | Use |
|---|---|
| Ad-hoc / self-service reports (long tail, 200 clients) | **Concept 1** — dynamic compile, no per-report engineering |
| Certified payroll/statutory/compliance reports | **Concept 2** style — curated/certified views + governed metrics |
| Performance-critical heavy reports | Hand-tuned views (Concept 2) registered *as entities* in Concept 1's catalog |

**ප්‍රායෝගිකව:**
1. **Concept 1 එක base එක** කරගන්න — dynamic semantic layer + Mart+Job execute. මේක 200 clients ට self-service scale කරනවා, per-report engineering නැතුව.
2. Concept 2 එකේ හොඳම දේ **borrow කරන්න**: certified metrics tier (memory එකේ `canonical-metrics-tier` දැනටමත් මේ දිශාවට), governance flags, සහ performance-critical reports වලට hand-tuned views (ඒවා Concept 1 catalog එකේ "entity" එකක් විදිහට register කරන්න).
3. **Caching + lineage** (Concept 1 දැනටමත් ශක්තිමත්) තියාගන්න — 200 clients × repeated runs වලට snapshot-keyed cache එක critical.

### සරලව
- **Pure Concept 2** තනියම → scale එකේදී engineering bottleneck + view sprawl.
- **Pure Concept 1** තනියම → governance/performance gaps (certified numbers, heavy-report tuning).
- **Concept 1 (base) + Concept 2 (governance & tuned views)** = SaaS 200 clients ට හොඳම fit. Flexibility + governance දෙකම.

---

### TL;DR
- **Concept 1** = dynamic, self-service, audit-grade, scales without engineering per report. Performance/predictability තමයි watch කරන්න ඕනේ.
- **Concept 2** = governed, predictable, certified, dbt-standard. Self-service නෑ; scale එකේදී view sprawl + maintenance.
- **200-client SaaS → Concept 1 base, Concept 2 governance layer එකක් විදිහට.** මේක තමයි recommendation එක.
