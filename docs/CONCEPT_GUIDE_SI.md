# MintHRM Report Builder — Layer Concept Guide (සිංහල)

> මේ document එක junior dev කෙනෙකුට මුළු system එකේ **layer-by-layer concept එක** තේරුම් කරදෙන්න. Datamart එකේ ඉඳන් උඩට, හැම layer එකකටම: **මොකක්ද → ඇයි හැදුවේ (මොන issue එක) → Technology → Code උදාහරණය**.

---

## 🎯 ලොකු පින්තූරේ

HR users ලාට (SQL නොදන්න අයට) තමන්ගේ datamart එකෙන් **reports හදන්න** දෙන **multi-tenant SaaS** product එකක්. Datamart එක raw, cryptic, per-client, VPN එකෙන් එහා — ඒ නිසා අතරට layers ගොඩක් දාලා raw data එක **business-friendly + safe + governed + fast** කරනවා.

```
                        HR User ("in-hand salary by branch")
                                      ▲  (answer)
   ┌──────────────────────────────────┴───────────────────────────────┐
   │                         API + Security                            │  JWT · tenant · RBAC · audit
   ├───────────────────────────────────────────────────────────────────┤
   │  Glossary        business වචන → governed ref                      │  📖 NEW
   │  Metrics         number එකකට එක governed definition               │  📊 NEW
   │  Resolver        NL → spec (LLM නැතුව)                            │  🧠
   │  AI Adapter      unusual ඒවාට LLM (metadata-only)                 │  🤖
   │  Semantic Layer  business නම් ↔ physical columns  ← හදවත          │  🗺️
   │  Query Engine    spec → safe parameterised SQL                    │  ⚙️
   │  Result Cache    Redis · snapshot-keyed                            │  ⚡ NEW
   │  Read-only Guards SELECT only (3 layers)                          │  🔒
   └───────────────────────────────────────────────────────────────────┘
                                      ▲  (rows)
                          Datamart (read replica, VPN, per-tenant)        🧱
```

**ප්‍රධාන philosophy එක:** හැම layer එකක්ම raw data එක ටිකෙන් ටික **business-friendly + safe + governed + fast** කරනවා.

---

## 🧱 Layer 0 — Datamart (පදනම)

**මොකක්ද:** හැම client (tenant) කෙනෙකුටම වෙන-වෙන database එකක් — `hrm_wh_{tenant_id}` — read replica එකක්, VPN එකෙන් reach කරන්නේ. Employee, Payroll, Leave, Attendance, dynamic pay items වගේ marts.

**ඇයි මේක issue එකක්:**
- Physical column names cryptic (`addition_blend_allowance`, `net_amount`).
- හැම client කෙනෙක්ගේම pay items වෙනස් (allowances/deductions වෙනස්).
- VPN එක **flaky** — connection drop වෙනවා.
- මේක read replica — **write කරන්න බෑ**.

**Technology:** PostgreSQL (per-tenant DB), SQLAlchemy connection pool, WireGuard VPN.

```
hrm_wh_amazon                    hrm_wh_dialog
 ├─ hr_semantic.vw_payroll_*      ├─ hr_semantic.vw_payroll_*
 ├─ hr.mart_horizontal_paysheet…  ├─ hr.mart_horizontal_paysheet…   ← columns වෙනස්!
 └─ vw_data_dictionary            └─ vw_data_dictionary
```

---

## 🔒 Layer 1 — Read-only Access Guards (ආරක්ෂාව)

**මොකක්ද:** Datamart එකට යන හැම query එකක්ම **read-only** කියලා layer 3කින් enforce කරනවා.

**ඇයි හැදුවේ:** SaaS එකක නිසා — app bug එකක් හරි AI වැරැද්දක් හරි නිසා client data එකක් **delete/modify වෙන්න බෑ**. "Defense in depth" — එක layer fail වුණත් අනිත් ඒවා අල්ලනවා.

**3 layers:**
1. Read-only DB user (database permission).
2. Read-only transaction (`SET TRANSACTION READ ONLY`).
3. `assert_select_only()` — SQL එක `SELECT` විතරද කියලා check.

**Technology:** PostgreSQL roles, SQLAlchemy transactions, custom guard.

```python
def assert_select_only(sql: str) -> None:
    s = sql.strip().lower()
    if not (s.startswith("select") or s.startswith("with")):
        raise GuardError("Only SELECT is allowed")
    # INSERT / UPDATE / DELETE / DROP / ';' (multi-statement) → reject
```

---

## 🗺️ Layer 2 — Semantic Layer (system එකේ හදවත)

**මොකක්ද:** Business නම් (`"Net Salary"`) physical column (`vw_payroll_summary.net_amount`) එකට map කරන **translation map** එකක්. පිට පැත්තට පේන්නේ `ref` (business key) විතරයි — `payroll.net`.

**ඇයි හැදුවේ — මේක තමයි මූලික issue එක:**
- HR user "Net Salary" කියලා හිතනවා, datamart එකේ `net_amount`. **මේ දෙක bridge කරන්න ඕන.**
- හැම client කෙනෙක්ගේම pay items වෙනස් → එක hard-coded map එකක් බෑ → **auto-introspect** කරනවා (client එකේ datamart එකෙන්ම දැනගන්නවා).
- AI එකට physical names පෙන්නන්න බෑ (security) → AI එකට `ref`/`label`/`type` විතරයි.

**වැදගත් concept:** මේක **data ගබඩා කරන view එකක් නෙවෙයි** — **metadata** (JSON map). Rows නෑ. Per-tenant + **versioned** (report එකක් publish කරනකොට ඒ version එකට **pin** වෙනවා → පස්සේ map වෙනස් වුණත් පරණ report break වෙන්නේ නෑ).

**Technology:** Pydantic v2 (model + validation), JSONB in PostgreSQL (storage), SQLAlchemy (introspection).

```python
SemanticField(
    ref="payroll.net",                 # ← AI/spec එකට පේන්නේ මේ විතරයි
    label="Net Salary",
    type=FieldType.DECIMAL, role=FieldRole.MEASURE,
    physical=PhysicalColumn(table="vw_payroll_summary", column="net_amount"),  # hidden
    pii=True,
)
```

```
User sees        Ref (AI/spec sees)     Physical column (hidden)
─────────        ──────────────────     ────────────────────────
Net Salary   →   payroll.net        →   vw_payroll_summary.net_amount
Blend Allow. →   paysheet.blend     →   …paysheet_dynamic.addition_blend_allowance
```

---

## ⚙️ Layer 3 — Query Engine (spec → safe SQL)

**මොකක්ද:** User ගේ choices `DataSpec` (JSON) එකක් වෙනවා (fields, filters, joins, groupings). Query Engine එක ඒක **parameterised, read-only `SELECT`** එකක් කරනවා. **AI එක නෙවෙයි SQL ලියන්නේ — engine එක.**

**ඇයි හැදුවේ:**
- AI එකට කෙලින්ම SQL දුන්නොත් → injection risk + වැරදි SQL. ඒ නිසා AI **spec** (intent) විතරයි දෙන්නේ; engine එක deterministic + safe SQL හදනවා.
- Filter values **string concat නෑ** — parameters විදිහට bind → injection-proof.
- Period-grain bug එකක් තිබුණා (period marts cross-join → data duplicate) → period-aligned joins වලින් fix කළා.

**Technology:** SQLAlchemy Core (`select()`, `case()`), custom guards, AST evaluator (calculated fields — `eval()` නැතුව safe arithmetic).

```
② spec (AI emits this — refs only, NO SQL)
   { fields:  ["payroll.net"],
     filters: [{ ref:"payroll.period", op:"eq", param:"period" }] }

③ Query Engine builds (value = bound parameter, NOT concatenated)
   SELECT net_amount
   FROM   hr_semantic.vw_payroll_summary
   WHERE  period_label = :period
   -- params: { "period": "2025-07" }
```

---

## 📊 Layer 4 — Metrics Tier (governed numbers)

**මොකක්ද:** Business number එකකට **එක governed definition** — `metric.<key>` (උදා: `metric.headcount`). Kinds 3ක්: aggregate / count / formula.

**ඇයි හැදුවේ — මොන issue එක:**
- Report 10ක "Headcount" 10 විදිහකට calculate වුණා (`count(*)` vs `count(distinct)`). **Inconsistent.**
- Solution: "Headcount" කියන්නේ මේකයි කියලා **එක තැනක govern** කරනවා → හැම report එකකම එකම answer.
- **Validate-on-define** — define කරනකොටම compile කරලා බලනවා; වැරදි ref/formula එතනම reject.

**Technology:** Pydantic (`MetricDef`), JSONB storage, query-compiler integration.

```python
MetricDef(key="total_net", label="Total Net Pay",
          kind="aggregate", agg=AggFn.SUM, ref="payroll.net")
# report එකක refer කරන්නේ:  metric.total_net
# formula එකක්: kind="formula", expression="metric.total_gross - metric.total_deductions"
```

---

## 📖 Layer 5 — Glossary Tier (business words)

**මොකක්ද:** Business වචනයක් → plain-language අර්ථය → ඒක compute කරන governed ref. ("Take-home Pay" → "deductions අඩු කරපු net මුදල" → `metric.total_net`).

**ඇයි හැදුවේ:**
- User "in-hand salary" කියලා ඉල්ලුවොත් — ඒක field label එකක්වත් metric label එකක්වත් නෙවෙයි. System එක **guess** කරනවා.
- Glossary එකෙන් "in-hand salary" → `metric.total_net` කියලා **deterministically ground** කරනවා.
- Users ලාට consistent definitions (tooltip).

**Technology:** Pydantic (`GlossaryTerm`), JSONB storage, validate-on-define (ref එක resolve වෙන්න ඕන), resolver එකට synonym feed.

```python
GlossaryTerm(
    term="Take-home Pay", ref="metric.total_net",
    aliases=["in-hand salary", "net pay"],
    definition="සියලු deductions අඩු කිරීමෙන් පසු සේවකයාට අතට ලැබෙන මුදල.",
)
```

---

## 🧠 Layer 6 — Deterministic Resolver (NL → spec, LLM නැතුව)

**මොකක්ද:** "headcount by department" වගේ සාමාන්‍ය request — **LLM call එකක් නැතුව** spec එකක් කරනවා (field/metric labels + aliases + glossary synonyms containment-match). විසඳන්න බැරි ඒවා විතරක් LLM එකට (tiered).

**ඇයි හැදුවේ:**
- හැම NL request එකකටම LLM → **මිල අධිකයි, slow, non-deterministic**.
- සාමාන්‍ය requests වලට deterministic path → **ලාභයි, වේගවත්, reproducible, auditable**.

**Technology:** Plain Python (regex + normalize + containment match). No ML, no LLM.

```python
resolve_intent("in-hand salary by department", catalog)
# →  DataSpec(fields=[employee.department, metric.total_net])
#    source = "deterministic"   (LLM call = 0)

# tiered (ai_service.from_natural_language):
#   intent = resolve_intent(...)
#   if intent and intent.confidence >= 0.6:  serve deterministic
#   else:                                    fall back to LLM
```

---

## 🤖 Layer 7 — AI Adapter (LLM, fallback විදිහට)

**මොකක්ද:** Resolver එකට බැරි වුණොත් LLM එක. තව tasks 2ක්: Excel heading → field mapping, "describe a custom field" → banding rule.

**ඇයි හැදුවේ:** Flexible/unusual requests + Excel ingestion වලට AI ඕන. හැබැයි **AI එකට පේන්නේ metadata විතරයි** — PII නෑ, data rows නෑ, physical names නෑ, SQL ලියන්නේ නෑ. AI දෙන්නේ **proposal** එකක් → validate → user ට පෙන්නලා → edit කරන්න පුළුවන්.

**Technology:** Anthropic Claude **හෝ** self-hosted vLLM (per-tenant swappable), Pydantic structured-output validation, Fernet encryption (API keys at rest).

```python
# AI එකට යවන්නේ මේ විතරයි (metadata-only):
[{ "ref": "payroll.net", "label": "Net Salary", "type": "decimal", "role": "measure" }, …]
# PII නෑ · data rows නෑ · physical table/column නෑ
```

---

## ⚡ Layer 8 — Result Cache (වේගය)

**මොකක්ද:** Report result එක Redis එකේ cache කරනවා. Key = `tenant + compiled_sql_hash + params + datamart_snapshot_ref`.

**ඇයි හැදුවේ — මොන issue එක:**
- හැම report run එකක්ම **flaky VPN** එක පනිනවා live. දෙන්නෙක් එකම report එක ගැහුවොත් — දෙපාරක්ම datamart එකට.
- Cache hit වුණොත් **datamart එකට යන්නේම නෑ**.
- **Correctness:** `snapshot_ref` (data version) key එකේම තියෙන නිසා — datamart refresh වුණාම key වෙනස් → **stale data කවදාවත් serve වෙන්නේ නෑ** (explicit invalidation එකක්වත් නැතුව).
- **Single-flight** — popular report එකක් expire වුණ මොහොතේ 10ක් ආවොත් එක්කෙනෙක් compute, ඉතුරු අය wait (stampede නෑ).

**Technology:** Redis (shared, multi-pod), pickle+zlib (serialize), `SET NX` (single-flight lock). **Fail-safe** — Redis වැටුණොත් කෙලින්ම execute, run break වෙන්නේ නෑ.

```python
key = sha256(f"{tenant_id} | {compiled_sql_hash} | {params_hash} | {snapshot_ref}")
#  hit  → cache එකෙන් rows (datamart untouched)
#  miss → single-flight lock → execute → cache.set(key, result)
#  snapshot_ref වෙනස් → key වෙනස් → පරණ entry unreachable (stale serve වෙන්නේ නෑ)
```

---

## 🛡️ Layer 9 — Governance & Lineage (cross-cutting)

**මොකක්ද:** හැම real run එකකටම `compiled_sql_hash`, `result_checksum` (data fingerprint), `snapshot_ref` record කරනවා (`report_runs` table). Data-quality validation gates. Audit log.

**ඇයි හැදුවේ:** SaaS + HR data → "මේ report එක මොන data එකෙන්ද, කවදද, හරිද" කියලා prove කරන්න ඕන. Reproducibility + audit.

**Technology:** SHA-256 hashing, PostgreSQL (`report_runs` / validation tables), AST evaluator (no `eval`).

---

## 🔑 Layer 10 — Multi-tenancy + Security (සියල්ල වටා)

**මොකක්ද:** JWT එකෙන් tenant + role එනවා. හැම query/catalogue එකක්ම ඒ tenant ට scope. RBAC (admin actions gated). Audit log.

**ඇයි හැදුවේ:** SaaS — client A ට client B ගේ data පේන්න බෑ. `X-Act-As-Tenant` header එක SUPPORT_ADMIN ට විතරයි (spoof කරන්න බෑ).

**Technology:** FastAPI dependencies, Authlib (JWT), per-request tenant context.

---

## 🎬 සම්පූර්ණ flow එක — එක request එකක් (datamart → up)

```
1  Datamart            ← raw rows මෙතන (read replica, VPN)
2  Result cache        ← මුලින්ම මෙතන බලනවා; hit → datamart skip
3  Query Engine        ← spec → safe parameterised SELECT (rows produce කරපු එක)
4  Semantic layer      ← ref → schema.table.column + joins
5  Resolver            ← request → spec (LLM නැතුව); metrics+glossary match
6  Metrics tier        ← metric.<key> = එක governed definition
7  Glossary            ← "in-hand salary" → metric.total_net
   ▼
   Delivered: "in-hand salary by branch" — answered
```

---

## ✅ Junior ට මතක තියාගන්න key points

1. **Semantic layer = හදවත** — business නම් ↔ physical columns. Metadata, data නෙවෙයි. Per-tenant + versioned.
2. **AI SQL ලියන්නේ නෑ** — engine එක ලියනවා. AI දෙන්නේ validate කරන spec එකක්.
3. **Metrics + Glossary = governance** — number එකකට/වචනයකට එක meaning එකක්.
4. **Resolver = deterministic first** — සාමාන්‍ය ඒවාට LLM නෑ (ලාභ + reproducible).
5. **Cache = snapshot-keyed** — fast, ඒත් stale කවදාවත් serve වෙන්නේ නෑ.
6. **හැම layer එකේම පදනම** — read-only + per-tenant + auditable.
