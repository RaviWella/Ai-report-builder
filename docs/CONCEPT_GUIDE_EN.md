# MintHRM Report Builder — Layer Concept Guide (English)

> A walk-through of the whole system for a junior dev. From the datamart upward, for
> every layer: **what it is → why we built it (the problem) → the technology → a code example.**

---

## 🎯 The big picture

A **multi-tenant SaaS** that lets non-technical HR users build **reports** from their HR
datamart — with **no SQL**. The datamart is raw, cryptic, per-client and behind a VPN, so we
put several layers in between that make the raw data **business-friendly + safe + governed + fast**.

```
                        HR User ("in-hand salary by branch")
                                      ▲  (answer)
   ┌──────────────────────────────────┴───────────────────────────────┐
   │                         API + Security                            │  JWT · tenant · RBAC · audit
   ├───────────────────────────────────────────────────────────────────┤
   │  Glossary        business words → governed ref                    │  📖 NEW
   │  Metrics         one governed definition per number               │  📊 NEW
   │  Resolver        NL → spec (no LLM)                               │  🧠
   │  AI Adapter      LLM for the unusual (metadata-only)              │  🤖
   │  Semantic Layer  business names ↔ physical columns  ← the heart   │  🗺️
   │  Query Engine    spec → safe parameterised SQL                    │  ⚙️
   │  Result Cache    Redis · snapshot-keyed                            │  ⚡ NEW
   │  Read-only Guards SELECT only (3 layers)                          │  🔒
   └───────────────────────────────────────────────────────────────────┘
                                      ▲  (rows)
                          Datamart (read replica, VPN, per-tenant)        🧱
```

**The core idea:** every layer makes the raw data a little more **business-friendly, safe,
governed and fast**.

---

## 🧱 Layer 0 — Datamart (the foundation)

**What:** Each client (tenant) has its own database — `hrm_wh_{tenant_id}` — a read replica
reached over a VPN, with marts for Employee, Payroll, Leave, Attendance and dynamic pay items.

**Why it's a problem:**
- Physical column names are cryptic (`addition_blend_allowance`, `net_amount`).
- Pay items differ per client (different allowances/deductions).
- The VPN is **flaky** — connections drop.
- It's a read replica — **you can't write to it**.

**Technology:** PostgreSQL (per-tenant DB), SQLAlchemy connection pool, WireGuard VPN.

```
hrm_wh_amazon                    hrm_wh_dialog
 ├─ hr_semantic.vw_payroll_*      ├─ hr_semantic.vw_payroll_*
 ├─ hr.mart_horizontal_paysheet…  ├─ hr.mart_horizontal_paysheet…   ← columns differ!
 └─ vw_data_dictionary            └─ vw_data_dictionary
```

---

## 🔒 Layer 1 — Read-only access guards (safety)

**What:** Three independent layers force every datamart query to be **read-only**.

**Why:** It's a SaaS holding client HR data — an app bug or an AI slip must never be able to
**write or delete**. Defense in depth: if one layer fails, the others still catch it.

**3 layers:**
1. Read-only DB user (database-level permission).
2. Read-only transaction (`SET TRANSACTION READ ONLY`).
3. `assert_select_only()` — checks the SQL is a `SELECT` only.

**Technology:** PostgreSQL roles, SQLAlchemy transactions, a custom guard.

```python
def assert_select_only(sql: str) -> None:
    s = sql.strip().lower()
    if not (s.startswith("select") or s.startswith("with")):
        raise GuardError("Only SELECT is allowed")
    # INSERT / UPDATE / DELETE / DROP / ';' (multi-statement) → rejected
```

---

## 🗺️ Layer 2 — Semantic layer (the heart of the system)

**What:** A per-tenant map from a business name (`"Net Salary"`) to a physical column
(`vw_payroll_summary.net_amount`). The outside world only ever sees the `ref` (a business key)
— `payroll.net`.

**Why we built it — this is the core problem:**
- The HR user thinks "Net Salary"; the warehouse stores `net_amount`. **These two must be bridged.**
- Pay items differ per client, so it can't be hand-coded — it's **auto-introspected** from each
  client's own datamart.
- The AI must never see physical names (security) → the AI only sees `ref`/`label`/`type`.

**Key concept:** this is **not a view that holds data** — it's **metadata** (a JSON map). No rows.
Per-tenant and **versioned** (when a report is published it is **pinned** to that version, so a
later change to the map never breaks the old report).

**Technology:** Pydantic v2 (model + validation), JSONB in PostgreSQL (storage), SQLAlchemy
(introspection).

```python
SemanticField(
    ref="payroll.net",                 # ← this is ALL the AI/spec sees
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

**What:** User choices become a `DataSpec` (JSON) — fields, filters, joins, groupings. The Query
Engine compiles it into one **parameterised, read-only `SELECT`**. **The engine writes the SQL,
not the AI.**

**Why:**
- If the AI wrote SQL directly → injection risk + wrong SQL. So the AI only emits a **spec**
  (intent); the engine deterministically builds safe SQL.
- Filter values are **bound as parameters**, never string-concatenated → injection-proof.
- A period-grain bug once duplicated rows (period marts cross-joined) → fixed here with
  period-aligned joins.

**Technology:** SQLAlchemy Core (`select()`, `case()`), custom guards, an AST evaluator
(calculated fields — safe arithmetic without `eval()`).

```
② spec (the AI emits this — refs only, NO SQL)
   { fields:  ["payroll.net"],
     filters: [{ ref:"payroll.period", op:"eq", param:"period" }] }

③ Query Engine builds (value = bound parameter, NOT concatenated)
   SELECT net_amount
   FROM   hr_semantic.vw_payroll_summary
   WHERE  period_label = :period
   -- params: { "period": "2025-07" }
```

---

## 📊 Layer 4 — Metrics tier (governed numbers)

**What:** A named `metric.<key>` layer over the fields — the **single definition** of a business
number (kinds: aggregate / count / formula).

**Why — the problem:**
- "Headcount" was being re-derived 10 different ways across reports (`count(*)` vs
  `count(distinct)`). **Inconsistent.**
- Defining it **once** means it's identical everywhere.
- **Validated on define** — it's compiled when defined; a bad ref/formula is rejected up front.

**Technology:** Pydantic (`MetricDef`), JSONB storage, query-compiler integration.

```python
MetricDef(key="total_net", label="Total Net Pay",
          kind="aggregate", agg=AggFn.SUM, ref="payroll.net")
# referenced in a report as:  metric.total_net
# a formula kind:  kind="formula", expression="metric.total_gross - metric.total_deductions"
```

---

## 📖 Layer 5 — Glossary tier (business words)

**What:** A business word → its plain-language meaning → the governed ref that computes it.
("Take-home Pay" → "the net amount after deductions" → `metric.total_net`).

**Why:**
- A user asking for "in-hand salary" names neither a field nor a metric, so the system used to
  **guess**.
- The glossary maps "in-hand salary" → `metric.total_net` — **grounded, not guessed**.
- Users get consistent definitions (tooltips).

**Technology:** Pydantic (`GlossaryTerm`), JSONB storage, validate-on-define (the ref must
resolve), and it feeds the resolver as synonyms.

```python
GlossaryTerm(
    term="Take-home Pay", ref="metric.total_net",
    aliases=["in-hand salary", "net pay"],
    definition="The net amount an employee receives after all deductions.",
)
```

---

## 🧠 Layer 6 — Deterministic resolver (NL → spec, without the LLM)

**What:** A common request like "headcount by department" becomes a spec **with no LLM call**
(by matching field/metric labels + aliases + glossary synonyms). Only what it can't resolve goes
to the LLM (tiered).

**Why:**
- Sending every request to an LLM is **expensive, slow and non-deterministic**.
- A deterministic path for the common shapes is **cheaper, faster, reproducible and auditable**.

**Technology:** Plain Python (regex + normalize + containment match). No ML, no LLM.

```python
resolve_intent("in-hand salary by department", catalog)
# →  DataSpec(fields=[employee.department, metric.total_net])
#    source = "deterministic"   (LLM calls = 0)

# tiered (ai_service.from_natural_language):
#   intent = resolve_intent(...)
#   if intent and intent.confidence >= 0.6:  serve deterministic
#   else:                                    fall back to the LLM
```

---

## 🤖 Layer 7 — AI adapter (the LLM, as a fallback)

**What:** Used when the resolver can't handle a request, plus two more tasks: Excel-heading →
field mapping, and "describe a custom field" → a banding rule.

**Why:** Flexibility for open-ended requests and Excel ingestion. But the AI sees **metadata
only** — no PII, no data rows, no physical names, and it never writes SQL. It returns a
**proposal** that is validated, shown to the user, and editable before anything runs.

**Technology:** Anthropic Claude **or** a self-hosted vLLM (swappable per tenant), Pydantic
structured-output validation, Fernet encryption (API keys at rest).

```python
# All the AI ever receives (metadata-only):
[{ "ref": "payroll.net", "label": "Net Salary", "type": "decimal", "role": "measure" }, …]
# no PII · no data rows · no physical table/column
```

---

## ⚡ Layer 8 — Result cache (speed)

**What:** Caches the report result in Redis. Key =
`tenant + compiled_sql_hash + params + datamart_snapshot_ref`.

**Why — the problem:**
- Every run otherwise hits the **flaky VPN** live. Two users running the same report = two
  warehouse round-trips.
- On a cache hit, **the datamart is never touched**.
- **Correctness:** the `snapshot_ref` (data version) is part of the key — when the datamart
  refreshes, the key changes → **stale data is never served** (with no explicit invalidation).
- **Single-flight** — when a popular report expires and 10 users arrive, one computes while the
  others wait (no stampede).

**Technology:** Redis (shared, multi-pod), pickle+zlib (serialization), `SET NX` (single-flight
lock). **Fail-safe** — if Redis is down it executes directly; a run never breaks.

```python
key = sha256(f"{tenant_id} | {compiled_sql_hash} | {params_hash} | {snapshot_ref}")
#  hit  → rows from Redis (datamart untouched)
#  miss → single-flight lock → execute → cache.set(key, result)
#  snapshot_ref changes → key changes → old (stale) entry is unreachable
```

---

## 🛡️ Layer 9 — Governance & lineage (cross-cutting)

**What:** Every real run records `compiled_sql_hash`, a `result_checksum` (a data fingerprint)
and the `snapshot_ref` (in `report_runs`). Plus data-quality validation gates and an audit log.

**Why:** For a SaaS holding HR data you must prove "which data, when, and was it valid".
Reproducibility + audit.

**Technology:** SHA-256 hashing, PostgreSQL (`report_runs` / validation tables), an AST evaluator
(no `eval`).

---

## 🔑 Layer 10 — Multi-tenancy + security (around everything)

**What:** A JWT carries the tenant + role. Every query and catalogue is scoped to that tenant.
RBAC gates admin actions. Everything is audited.

**Why:** SaaS — client A must never see client B's data. The `X-Act-As-Tenant` header is honoured
only for a SUPPORT_ADMIN (it can't be spoofed).

**Technology:** FastAPI dependencies, Authlib (JWT), a per-request tenant context.

---

## 🎬 The full flow — one request (datamart → up)

```
1  Datamart            ← raw rows live here (read replica, VPN)
2  Result cache        ← checked first; hit → datamart skipped
3  Query Engine        ← spec → safe parameterised SELECT (produced the rows)
4  Semantic layer      ← ref → schema.table.column + joins
5  Resolver            ← request → spec (no LLM); matches metrics + glossary
6  Metrics tier        ← metric.<key> = the one governed definition
7  Glossary            ← "in-hand salary" → metric.total_net
   ▼
   Delivered: "in-hand salary by branch" — answered
```

---

## ✅ Key points for a junior to remember

1. **The semantic layer is the heart** — business names ↔ physical columns. It's metadata, not
   data. Per-tenant + versioned.
2. **The AI never writes SQL** — the engine does. The AI only produces a validated spec.
3. **Metrics + glossary = governance** — one meaning per number / per word.
4. **The resolver is deterministic-first** — common requests skip the LLM (cheaper + reproducible).
5. **The cache is snapshot-keyed** — fast, but stale data is never served.
6. **Every layer's baseline** — read-only + per-tenant + auditable.
