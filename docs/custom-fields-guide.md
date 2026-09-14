# Custom Field Logic — Builder Guideline

A practical guide for writing **custom columns** in the Report Builder. Two kinds:
**Formula** (arithmetic) and **Banding** (condition → label). You never write SQL —
you describe the logic and the Query Engine compiles it to safe, parameterized SQL.

> **Golden rule:** a custom field is a calculation **over fields that already exist
> in the semantic layer**. It cannot invent data the datamart doesn’t have. If the
> logic needs new source data or heavy business rules, it belongs in the datamart /
> `mint-rule-engine` (computed once, then it becomes a normal field here).

---

## 1. Formula fields (arithmetic)

Combine existing **measure** fields with `+  -  *  /` and parentheses.

**Syntax**
```
<field.ref> <op> <field.ref | number> …
```

**Examples**
| Column | Formula |
|---|---|
| Take Home | `payroll.net - payroll.deductions` |
| Total EPF | `payroll.epf_employee + payroll.epf_employer` |
| Tax % of Gross | `payroll.tax / payroll.gross * 100` |
| Net after a 5% levy | `payroll.net - (payroll.net * 0.05)` |
| Cost to Company | `payroll.gross + payroll.epf_employer` |

**Rules**
- Use **field refs** (e.g. `payroll.gross`) — pick them from the field list; don’t type physical column names.
- Allowed tokens only: refs, numbers, `+ - * / ( )`. Anything else is rejected.
- Works on **numbers** (measures). Dividing/adding text fields won’t make sense.
- You may reference an **earlier custom field** by `calc.<name>` (define it first).
- No functions, no dates, no conditions here — use Banding (below) for conditions.

---

## 2. Banding fields (condition → label)

Turn a number/text field into a **labelled band**. Rules are checked **top-to-bottom;
the first match wins**; anything unmatched gets the **Otherwise** label.

**Structure**
```
Based on:  <field>           e.g. Age
Rules (in order):
   <op> <value>  →  <label>
   <op> <value>  →  <label>
Otherwise     →  <label>
```

**Examples**

*Age groups* (based on `employee.age`)
```
lt  20  → "Under 20"
lt  30  → "20–29"
lt  50  → "30–49"
Otherwise → "50+"
```

*Salary bands* (based on `payroll.gross`)
```
lt   50000  → "Band C"
lt  150000  → "Band B"
Otherwise   → "Band A"
```

*Tenure flag* (based on `employee.tenure_years`)
```
gte 5 → "Loyal (5y+)"
Otherwise → "—"
```

*Status label* (based on `employee.status`)
```
eq "active" → "Working"
Otherwise   → "Not active"
```

---

## 3. Operators

| Op | Meaning | Use with |
|---|---|---|
| `lt` `lte` | < , ≤ | numbers, dates |
| `gt` `gte` | > , ≥ | numbers, dates |
| `eq` `neq` | = , ≠ | numbers, text |
| `between` | within `[low, high]` | numbers, dates |
| `contains` | text contains | text |

Numbers are detected automatically (type `20`, not `"20"`). Text values keep quotes
in examples but you just type the word in the value box.

---

## 4. What you CANNOT do at report time (use the datamart instead)

These are intentionally **not** in the report builder — they live in the dbt marts /
rule engine so they’re computed once and governed:

- **Date math** (e.g. Age = today − DOB, days since join). ✅ Already precomputed:
  `employee.age`, `employee.tenure_years`, `employee.tenure_bucket`.
- **Cross-row logic** — running totals, rank, “% of department total”, prior-month
  comparison. (These are aggregations/marts, not per-row formulas.)
- **Brand-new business rules** (e.g. a client-specific bonus or EPF formula that
  depends on data not in the datamart). → add to `mint-rule-engine` + the mart.
- **Lookups to external systems.**

Rule of thumb: if you can compute it from numbers/labels already in the field list →
do it here. If you need new data or it spans many rows → it’s a mart/ETL job.

---

## 5. Tips

- **Name it clearly** — the column name becomes the heading and the field key.
- **Order banding rules from most specific / smallest first** (first match wins).
- **Preview before publishing** — “Run preview” shows the computed values on real data.
- **Reuse** — a formula can build on an earlier custom field (`calc.<name>`).
- Custom fields are saved inside the report version (immutable on publish) and
  recompiled deterministically every run — no drift.

---

## 6. Under the hood (for the curious)

- Formula → a SQLAlchemy arithmetic expression over the resolved physical columns.
- Banding → a parameterized `CASE WHEN … THEN … END`; thresholds and labels are
  **bound parameters**, never string-concatenated.
- The AI, if you describe a formula in words, only proposes the **structured spec** —
  it never writes SQL and never sees employee data.
