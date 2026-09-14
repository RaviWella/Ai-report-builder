---
target: custom reports
total_score: 33
p0_count: 0
p1_count: 0
timestamp: 2026-06-05T06-02-08Z
slug: frontend-src-pages-hr-reports-customizedreports-tsx
---
# Custom Reports UI Critique

**Target:** `CustomizedReports.tsx`, `CustomReportDefinitions.tsx`, `customReportModules.ts`, `Layout.tsx` (nav)  
**Date:** 2026-06-05 (re-run after clarify, harden, polish)  
**Method:** Source review (Assessment A) + `detect.mjs` on three files (Assessment B). Browser overlay skipped (no verified Vite dev server for injection).

---

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 4 | Skeletons, pending labels, and toasts on both surfaces; minor gap on partial publish failures |
| 2 | Match System / Real World | 3 | Plain-language labels improved; SQL editor and "Publish reports" still assume technical comfort |
| 3 | User Control and Freedom | 4 | Cancel resets, delete confirm, dismiss export errors, form close resets draft |
| 4 | Consistency and Standards | 4 | Shared `ReportPageHeader`, `ReportQueryError`, `ReportEmptyState`, `hrm-report-action` |
| 5 | Error Prevention | 3 | Delete guarded; Report ID pattern validated; SQL errors surface only after save/publish |
| 6 | Recognition Rather Than Recall | 3 | ETL-built/App-managed badges help; publish-vs-save timing still implicit |
| 7 | Flexibility and Efficiency | 2 | No list filter, bulk export, or post-create SQL edit |
| 8 | Aesthetic and Minimalist Design | 3 | Section eyebrows fixed; definition cards still carry 3–4 pills per row |
| 9 | Error Recovery | 4 | Retry on load failures, toasts on mutations, export error dismiss |
| 10 | Help and Documentation | 3 | SQL help + collapsible tokens; no task walkthrough for first custom report |
| **Total** | | **33/40** | **Good — solid operational surface, admin flow still dense** |

**Cognitive load:** 3 checklist failures (3 peer actions per report row, badge stack on config cards, publish/save mental model). Moderate load; acceptable for Platform admin, heavy for occasional IT users.

---

## Anti-Patterns Verdict

**LLM assessment:** Does not read as generic marketing AI. It reads as a **native extension of the MintHRM report shell**: teal actions, dashed empty states, section-grouped lists. Prior uppercase eyebrow scaffold is gone. Remaining tell is **identical bordered card/list stacks** on the config page and **equal-weight action clusters** (Preview / Excel / PDF) on each row. Appropriate for product register, not slop.

**Deterministic scan:** Clean — `detect.mjs` returned `[]` for all three files.

**Browser overlays:** Not run (dev server not verified for injection).

---

## Overall Impression

The custom reports split (Operations list vs Platform config) is the right IA and now **feels like the rest of the HR report suite**. Clarify/harden/polish closed the obvious gaps: loading parity, delete safety, copy that respects HR ops language. The biggest remaining opportunity is **reducing decision weight per row** on the reports list and **clarifying the publish lifecycle** on config without adding more badges.

---

## What's Working

1. **Shared report vocabulary.** Both pages use the same header, skeleton, error, empty, and action patterns as Employees, Payroll, and other HR reports.
2. **Operational feedback.** Per-row busy states on save/delete/export, card skeleton on config, and toast confirmations match PRODUCT.md principle #4.
3. **Governance safety.** Delete confirmation, edit cancel reset, and trimmed validation on create reduce payroll-close misclick risk.

---

## Priority Issues

### [P2] Equal-weight export cluster on each report row
- **What:** `CustomizedReports` renders Preview, Download Excel, and Download PDF as three sibling `hrm-report-action` buttons with no primary/secondary hierarchy beyond Excel as primary.
- **Why it matters:** Alex scans 6+ payroll reports and clicks the wrong format; Casey on mobile sees a wall of same-sized targets.
- **Fix:** Keep Preview + one "Download" control with format choice (split button, menu, or dialog). Excel stays default for HR analysts.
- **Suggested command:** `/impeccable distill`

### [P2] Publish vs save lifecycle still implicit
- **What:** Config has "Save report" (create) and a separate header "Publish reports" (sync). Nothing explains that app-managed SQL must be published before analytics views exist.
- **Why it matters:** Jordan saves a report, opens Customized reports, sees nothing, and assumes the product is broken.
- **Fix:** After create success, prompt to publish or auto-sync once; add one sentence under the header actions describing when publish is needed.
- **Suggested command:** `/impeccable onboard`

### [P2] Badge stack on definition cards
- **What:** Each card shows area pill + source pill + optional payslip pill beside the title.
- **Why it matters:** Extraneous load on a governance screen where title and source type matter most; duplicates area already available via filter.
- **Fix:** Drop area pill when not editing (filter covers it) or merge source + layout into one muted meta line under the title.
- **Suggested command:** `/impeccable quieter`

### [P2] Filtered empty state without a clear action
- **What:** "No reports in Payroll" tells users to clear the filter but offers no control besides the select above.
- **Why it matters:** Small friction that reads like an dead end on an otherwise polished empty-state pattern.
- **Fix:** Add "Show all areas" button in the empty state, mirroring the unfiltered CTA pattern.
- **Suggested command:** `/impeccable polish`

### [P3] Source type tooltip-only for assistive tech
- **What:** `reportSourceDescription` is on `title` of the badge span, not exposed as visible or sr-only text.
- **Why it matters:** Sam hears "ETL-built" without the explanation that only name/area/order are editable.
- **Fix:** Add sr-only description or visible one-line meta under badges.
- **Suggested command:** `/impeccable audit`

---

## Persona Red Flags

**Jordan (Confused First-Timer — IT admin on config):** Saves custom report, skips "Publish reports", sees empty Customized reports list. SQL textarea and `{mart_schema}` tokens in advanced details still feel like a DBA console despite improved labels.

**Alex (Power User — HR analyst on reports list):** Must open each row and choose Excel or PDF individually; no module filter on the list page; three clicks minimum per report export with no keyboard path.

**Sam (Accessibility):** Export busy state uses `aria-busy` well. Source badge meaning relies on hover `title`. Delete uses native `window.confirm`, which is accessible but inconsistent with in-app dialog patterns elsewhere.

---

## Minor Observations

- Platform and Operations nav both use `FileSpreadsheet` for different jobs (config vs runtime list).
- `inputClass` / `labelClass` duplicated in config page; same pattern as `EtlSources.tsx` (acceptable one-off until extracted).
- `window.confirm` for delete works but breaks visual consistency with the rest of the shell.
- Empty section groups are hidden entirely; Employment with zero reports never explains why the section is absent.

---

## Questions to Consider

- Should first custom report creation auto-publish, with manual publish only for bulk refresh?
- Would a single "Download" menu on the list page cover 90% of exports without hiding PDF?
- Is Platform-only role gating needed so HR analysts never land on the SQL form?
