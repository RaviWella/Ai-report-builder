---
target: custom reports (CustomizedReports + CustomReportDefinitions)
total_score: 25
p0_count: 0
p1_count: 2
timestamp: 2026-06-05T05-54-07Z
slug: frontend-src-pages-hr-reports-customizedreports-tsx
---
# Custom Reports UI Critique

**Target:** `CustomizedReports.tsx`, `CustomReportDefinitions.tsx`, `Layout.tsx` (custom report nav)  
**Date:** 2026-06-05  
**Method:** Source review (Assessment A) + `detect.mjs` on three files (Assessment B). Browser overlay skipped (no Vite dev server confirmed for injection).

---

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Reports list uses skeleton; config page uses plain "Loading definitions…" text |
| 2 | Match System / Real World | 2 | Config surface speaks in warehouse/SQL terms (dbt, sync, view_query, mart_schema) |
| 3 | User Control and Freedom | 3 | Form cancel works; delete has no confirmation; inline edit cancel does not revert fields |
| 4 | Consistency and Standards | 4 | Reuses `hrm-report-action`, `ReportPageHeader`, `ReportEmptyState` patterns |
| 5 | Error Prevention | 2 | Default `SELECT 1 AS example` in create form; delete is one click |
| 6 | Recognition Rather Than Recall | 3 | Badges (dbt/sync/payslip) help; module labels duplicated under section headers |
| 7 | Flexibility and Efficiency | 2 | No bulk actions; sync reports cannot edit SQL after create in UI |
| 8 | Aesthetic and Minimalist Design | 2 | Uppercase section eyebrows; stacked cards with 3–4 pills each |
| 9 | Error Recovery | 3 | API errors + retry on config; export errors on reports list |
| 10 | Help and Documentation | 1 | One-line placeholder hint only; no task-focused SQL guidance |
| **Total** | | **25/40** | **Acceptable — functional but admin/config needs polish** |

**Cognitive load:** 4 checklist failures (badge overload per card, 3 row actions + labels, config jargon wall, section + module label redundancy). Moderate-to-high for first-time admins.

---

## Anti-Patterns Verdict

**LLM assessment:** Does not read like a marketing AI page. It reads like a **competent internal admin extension** bolted onto an existing HR report shell. The main AI tells present are **uppercase tracked section headers** on `CustomizedReports` (Employment / Operations) and **identical bordered card stacks** on the config page. Neither is catastrophic for a product register surface, but the section eyebrows match the saturated AI scaffold the skill flags.

**Deterministic scan:** Clean — `detect.mjs` returned `[]` for all three files.

**Browser overlays:** Not run (dev server not verified for injection).

---

## Overall Impression

The split between **Customized reports** (Operations) and **Custom report config** (Platform) is the right IA for your PRODUCT.md audience. Section grouping by Employment vs Operations matches the sidebar mental model. The config page does the job but still feels like a developer form, not an HR ops tool.

---

## What's Working

1. **IA separation.** Runtime reports under Operations; metadata under Platform matches how HR managers vs IT admins think about the task.
2. **Shared report vocabulary.** `hrm-report-action`, empty states, and export loading on the list page align with the rest of the HR report suite.
3. **Section-aware grouping.** `groupCustomReportsBySection` hides empty sections and maps modules to sidebar zones without extra navigation.

---

## Priority Issues

### [P1] Uppercase section eyebrows on Customized reports
- **What:** `CustomizedReports` renders `EMPLOYMENT` / `OPERATIONS` via `uppercase tracking-wide text-slate-500` headings.
- **Why it matters:** Matches the banned eyebrow scaffold; adds noise without information the sidebar does not already provide.
- **Fix:** Use sentence-case labels (`Employment`, `Operations`) with normal tracking, or drop headings and rely on subtle dividers / count labels.
- **Suggested command:** `/impeccable quieter`

### [P1] Config page assumes warehouse literacy
- **What:** Copy references "application database", `custom_reports` schema, `dbt`, `sync`, `{mart_schema}` without plain-language framing.
- **Why it matters:** Secondary persona (IT/ops admin) may manage sources but not write SQL; primary HR analysts will bounce off this screen.
- **Fix:** Lead with outcomes ("Reports appear under Customized reports after sync"), move schema names to collapsible "Advanced" help, rename badges to "ETL-built" / "App-managed".
- **Suggested command:** `/impeccable clarify`

### [P2] Inline edit cancel leaves stale local state
- **What:** `DefinitionCard` cancel sets `editing` false without resetting `reportName`, `module`, `sortOrder` from `row`.
- **Why it matters:** Re-opening edit shows abandoned values; erodes trust in a governance surface.
- **Fix:** Reset from `row` on cancel or key the card by `row.id` + `editing`.
- **Suggested command:** `/impeccable harden`

### [P2] Destructive delete without confirmation
- **What:** Delete on sync definitions fires immediately.
- **Why it matters:** Drops warehouse view + DB row; irreversible in one misclick during payroll close pressure.
- **Fix:** Confirm dialog naming report + view; disable while pending.
- **Suggested command:** `/impeccable harden`

### [P2] Config loading inconsistency
- **What:** Reports list uses `ReportListSkeleton`; config uses a single muted sentence.
- **Why it matters:** Breaks the "operational feedback" principle; page feels broken vs polished neighbors.
- **Fix:** Reuse `ReportListSkeleton` or a compact card skeleton on config.
- **Suggested command:** `/impeccable polish`

---

## Persona Red Flags

**Jordan (Confused First-Timer — IT admin on config):** "Sync warehouse" vs "Create & sync" distinction unclear. Badges `dbt` and `sync` unexplained. View query textarea with placeholder tokens looks like a developer console. Will not create reports without hand-holding.

**Alex (Power User — HR analyst on reports list):** Three equal-weight buttons per row (Preview, Excel, PDF) with no keyboard path. Cannot filter by module on the list page (only grouped sections). Export-all or period filter absent.

**Sam (Accessibility):** Section `aria-labelledby` is good. Export buttons use `aria-busy`. Uppercase section titles may be spelled letter-by-letter in some screen reader configs. Config form textarea lacks `aria-describedby` linking to placeholder help.

---

## Minor Observations

- Module label shown twice when grouped (section header + row subtitle).
- `CustomReportDefinitions` duplicates `inputClass` / `labelClass` instead of shared form primitives used elsewhere.
- Platform nav uses `FileSpreadsheet` for config while Operations uses the same icon for reports (two identical icons, different jobs).
- Empty config state mentions "Run migrations" (too implementation-specific for HR ops).

---

## Questions to Consider

- Should HR analysts ever land on config, or should it be Platform-only with role gating?
- If Employment has zero custom reports, should the section appear with an empty-state CTA instead of hiding entirely?
- Is editing SQL post-create a required v2 feature, or is recreate-and-delete enough?
