# Concept 1 vs Concept 2 — SaaS Fitness (200 clients)

> දෙකම code එකට එරෙහිව නැවත audit කරපු එක. SaaS-critical dimensions 9ක් — එක එක concept එකට **FITS / PARTIAL / DOESN'T FIT** verdict + හේතුව. Lens එක: multi-tenant SaaS, ~200 clients.

## Side-by-side verdict

| # | Dimension | **Concept 1** (dynamic compile) | **Concept 2** (manual views) |
|---|---|---|---|
| 1 | **Tenant onboarding** | ✅ **FITS** — zero-touch; JWT ආපු ගමන් tenant row + semantic catalog auto-introspect + seed. Nightly refresh. | ❌ **DOESN'T FIT** — manual: tenant registry + per-tenant warehouse provision + dbt run + view sync per tenant. |
| 2 | **Multi-tenancy isolation** | ✅ **FITS** — 3 layers: per-tenant DB + search_path, read-only txn, query guards. Single bypass එකක් leak කරන්නේ නෑ. | 🟡 **PARTIAL** — explicit `WHERE tenant_id='{...}'` හැම view එකේම; වැඩ කරනවා, හැබැයි manual/error-prone (placeholder අමතක වුණොත් leak). RLS නෑ. |
| 3 | **Self-service (no code per report)** | ✅ **FITS** — NL chat / Excel / drag-drop builder → spec → preview → publish. Code/deploy නෑ. | ❌ **DOESN'T FIT** — අලුත් report = SQL ලියනවා + migration + deploy + 200 tenant sync. Builder UI නෑ. |
| 4 | **Performance & scalability** | 🟡 **PARTIAL** — Redis result cache (snapshot-keyed) + row limit + statement timeout + per-tenant pool. **Cost governor / tuned joins / pre-aggregation නෑ** (noisy-neighbour risk). | ✅ **FITS** — hand-tuned views, dbt materialization control (view→table→incremental). DBA cost forecast කරන්න පුළුවන්. (Runtime noisy-neighbour guard එළියෙන් එන්න ඕනේ.) |
| 5 | **Security** | ✅ **FITS** — triple read-only, parameterized SQL (no concat), PII rows stripped, AI physical names/data දකින්නේ නෑ. | 🟡 **PARTIAL** — views read-only; **template string-substitution = injection surface** (`render_view_query`), validation regex-based; LLM-SQL chat path. |
| 6 | **Governance & correctness** | 🟡 **FITS (partial)** — metrics/glossary tier + audit lineage (version pin + sql_hash + checksum) + validation gates. **Certified-flag / forbidden-agg / query-contracts තවම නෑ.** | ✅ **FITS** — `metric_catalog.certified`, forbidden aggregations, query contracts, dbt tests/docs. Payroll/statutory-grade. |
| 7 | **Ops maintenance at scale** | 🟡 **PARTIAL** — metadata migrations + nightly drift auto-detect; custom tenant schema එකකට manual enrich ඕනේ. Version bump append-only (පරණ reports break නෑ). | ❌ **DOESN'T FIT** — schema change → 200× `CREATE OR REPLACE VIEW` sync; per-tenant divergence risk; explicit view versioning නෑ. |
| 8 | **AI dependency / determinism** | 🟡 **PARTIAL** — deterministic-first resolver + every AI spec guard-validated. **Eval harness / model-pin නෑ.** | 🟡 **PARTIAL** — glossary/metrics deterministic; ad-hoc datamart chat තවම LLM-SQL (non-deterministic). |
| 9 | **Observability** | ✅ **FITS** — run lineage (run_id, sql_hash, checksum, snapshot), audit log, structured logs. (Prometheus/OTel wiring තවම නෑ.) | 🟡 **PARTIAL** — logging + dbt run logs; **per-run lineage / point-in-time snapshot නෑ** (6 මාස පරණ report reproduce කරන්න අමාරු). |

**Score:** Concept 1 → FITS ×5, PARTIAL ×4, DOESN'T FIT ×0. Concept 2 → FITS ×2, PARTIAL ×4, DOESN'T FIT ×3.

---

## Concept 1 — SaaS එකකට ගැළපෙන / නොගැළපෙන

**ගැළපෙනවා (keep as base):**
- Zero-touch onboarding — 200 clients instantly scale, DBA/code නැතුව.
- Unbreakable 3-layer isolation.
- Self-service report design — engineering bottleneck නෑ. **මේක SaaS එකට decisive.**
- Strong security (read-only, PII, AI-safe).
- Audit lineage + reproducibility.

**නොගැළපෙන / improve කරන්න ඕනේ:**
1. **Query cost governor නෑ** → එක heavy report එකක් 199 ට බලපායි. *(GA කලින් must — Foundation Item 3)*
2. **Golden SQL tests නෑ** → compiler regressions (period-grain) silent. *(must — Item 2)*
3. **Performance tuning / pre-aggregation නෑ** → heavy reports slow. *(Item 5, big)*
4. **Governance tier light** → certified-flag / forbidden-agg එකතු කරන්න (Concept 2 borrow).
5. AI eval harness + model pin නෑ.

## Concept 2 — SaaS එකකට ගැළපෙන / නොගැළපෙන

**ගැළපෙනවා (borrow these):**
- Certified/governed metrics — compliance-grade. Payroll/statutory bulletproof.
- Predictable performance — hand-tuned, materialized views.
- dbt ecosystem — lineage/tests/docs, standard skillset.
- Explicit, auditable isolation (RLS magic නෑ).

**නොගැළපෙන (SaaS scale blockers):**
1. **Not self-service** → report එකකට developer sprint. 200 clients × custom reports = engineering bottleneck. ⛔
2. **Manual tenant onboarding** → zero-touch නෑ.
3. **200× view sync burden** + per-tenant divergence.
4. **Template SQL injection surface** + minimal validation.
5. **Per-run lineage / snapshot නෑ** → reproducibility weak.

---

## තීරණය (consistent with first comparison)

> **Dimensions දෙකක්: Self-service + scale → Concept 1 clearly ඉදිරියෙන්. Governance + predictable perf → Concept 2 ඉදිරියෙන්.**

200-client SaaS එකකට **pure Concept 2 = scale loser** (self-service ×, onboarding ×, ops ×). **Pure Concept 1 = governance/perf gaps.**

**හරි move එක = Hybrid:**
- **Base = Concept 1** (onboarding, isolation, self-service, security, observability — 5/5 FITS).
- **Borrow from Concept 2** = (a) certified-metrics governance, (b) heavy/hot reports වලට hand-tuned/materialized views — Concept 1 catalog එකේ entity එකක් විදිහට register කරලා.
- **GA කලින් Concept 1 වල 3 gaps වහන්න:** cost governor + golden tests + (පසුව) aggregate awareness.

**එක වචනෙන්:** Concept 1 තමයි SaaS foundation එක (gaps කිහිපයක් වහන්න තියෙනවා); Concept 2 එකේ governance + tuned-view layer එක උඩින් borrow කරන්න. ඒක තමයි 200 clients ට හොඳම fit.
