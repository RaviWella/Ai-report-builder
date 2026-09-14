---
target: Report Studio
total_score: 30
p0_count: 0
p1_count: 1
timestamp: 2026-06-09T06-00-28Z
slug: frontend-src-pages-hr-reports-customizedreports-tsx
---
# Report Studio UI Critique

**Target:** `CustomizedReports.tsx`, `CustomReportDefinitions.tsx`, `Layout.tsx` (nav)  
**Date:** 2026-06-09 (re-run after Report Studio rename, marketing copy, cross-nav link)  
**Method:** Source review (Assessment A) + `detect.mjs` on three files (Assessment B). Browser overlay skipped (no browser automation available for injection).

---

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 4 | Skeletons, per-row busy states, toasts; publish partial-failure still quiet |
| 2 | Match System / Real World | 2 | Page description promises field/filter builder UX the product does not ship |
| 3 | User Control and Freedom | 4 | Cancel/reset, delete confirm, cross-nav link to config; native confirm only |
| 4 | Consistency and Standards | 3 | "Report Studio" nav vs "Add custom report" CTAs; identical copy on two different jobs |
| 5 | Error Prevention | 3 | Delete guarded; SQL errors only after save/publish |
| 6 | Recognition Rather Than Recall | 3 | Config link helps admins; publish lifecycle still implicit |
| 7 | Flexibility and Efficiency | 2 | No list filter, bulk export, or keyboard accelerators |
| 8 | Aesthetic and Minimalist Design | 3 | Long marketing lead on an operational list; `shadow-sm` on HR list breaks flat rule |
| 9 | Error Recovery | 4 | Retry on load failures, dismiss export errors, mutation toasts |
| 10 | Help and Documentation | 2 | Lead copy mis-teaches the interface; SQL help good but buried on config |
| **Total** | | **30/40** | **Acceptable — solid shell, copy regression undermines trust** |

**Cognitive load:** 3 checklist failures (3 peer actions per report row, badge stack on config cards, save/publish mental model). Moderate load; acceptable for Platform admin, heavy for occasional IT users.

---

## Anti-Patterns Verdict

**LLM assessment:** Does not read as generic gradient-SaaS AI slop. It reads as a **native MintHRM report extension**: teal actions, dashed empty states, module-grouped lists, shared `ReportPageHeader`. The new tell is **marketing brochure copy on an audit-grade ops surface** ("Select fields, apply filters, organize data") where the actual UI is SQL definitions + preview/download rows. That violates PRODUCT.md voice ("Direct and operational") and the anti-reference against buzzword framing. Renaming to "Report Studio" is fine; the paragraph underneath is the regression.

**Deterministic scan:** Clean — `detect.mjs` returned `[]` for `CustomizedReports.tsx`, `CustomReportDefinitions.tsx`, and `Layout.tsx`.

**Browser overlays:** Not run (browser automation unavailable for script injection).

---

## Overall Impression

Report Studio / Report Studio Config is still the right IA split, and the cross-navigation link closes a real gap for warehouse admins. The rename lands in nav and headers. The single biggest problem now is **the shared description**: it describes a visual report builder MintHRM does not offer, which will erode trust with HR managers who expect spreadsheet-grade honesty during payroll close.

---

## What's Working

1. **Shared report vocabulary.** Both pages still use the same header, skeleton, error, empty, and `hrm-report-action` patterns as the rest of the HR suite.
2. **Bidirectional admin navigation.** "Open Report Studio Config" / "Open Report Studio" text links connect the two surfaces without forcing sidebar hunting.
3. **Operational feedback.** Per-row export busy states, card skeletons on config, and toast confirmations match PRODUCT.md principle #4.

---

## Priority Issues

### [P1] Page description promises capabilities the UI does not provide
- **What:** Both pages share: "Create, customize, and manage reports… Select fields, apply filters, organize data…" Report Studio is a grouped list with Preview / Excel / PDF. Config is SQL + publish, not a field picker.
- **Why it matters:** HR managers and IT admins read the lead, look for filters or a builder, and conclude the product is incomplete or broken. Directly conflicts with PRODUCT.md ("traceability over spectacle", anti-buzzword copy).
- **Fix:** Split copy by surface. Report Studio: what is in the list, how to run/export, where config lives. Config: SQL-based definitions, publish step, ETL-built vs app-managed. Drop "select fields / apply filters" unless that UX ships.
- **Suggested command:** `/impeccable clarify`

### [P2] Publish vs save lifecycle still implicit
- **What:** "Save report" (create) and header "Publish reports" (sync) are separate with no inline explanation that app-managed SQL must be published before views appear in Report Studio.
- **Why it matters:** Jordan saves a report, opens Report Studio, sees nothing, and assumes ETL or the rename broke the product.
- **Fix:** One sentence under header actions; post-create toast with "Publish now" action; or auto-sync on first save.
- **Suggested command:** `/impeccable onboard`

### [P2] Equal-weight export cluster on each report row
- **What:** Preview, Download Excel, and Download PDF are three sibling actions with similar visual weight (Excel primary only by color).
- **Why it matters:** Alex scanning six payroll reports mis-clicks format; Casey on mobile gets a wall of same-sized targets.
- **Fix:** Preview + one Download control with format choice (menu or split button). Excel stays default.
- **Suggested command:** `/impeccable distill`

### [P2] Terminology drift after rename
- **What:** Nav says "Report Studio" but CTAs still say "Add custom report", empty hint says "add a custom report", component/file names unchanged.
- **Why it matters:** Users wonder whether "custom report" and "Report Studio report" are different objects.
- **Fix:** Align user-facing strings: "Add report", "Report Studio report", or "tenant report" consistently.
- **Suggested command:** `/impeccable clarify`

### [P3] Cross-nav link placement is easy to miss
- **What:** "Open Report Studio Config" sits as a lone text link between header and content; config page puts its counterpart in the filter toolbar row.
- **Why it matters:** Admins who do not use Platform nav may never discover config from the list page despite the new link.
- **Fix:** Move link into `ReportPageHeader` children as a secondary action button, matching "Publish reports" / "Add custom report" on config.
- **Suggested command:** `/impeccable layout`

---

## Persona Red Flags

**Jordan (Confused First-Timer — IT admin):** Reads "Select fields, apply filters" on Report Studio Config, opens the form, finds only a SQL textarea. Saves, skips Publish, sees empty Report Studio. Assumes the rebrand broke reporting.

**Alex (Power User — HR analyst):** Still exports one report at a time with three clicks; no module filter on the list; no keyboard path to download. New marketing lead adds scroll before reaching reports.

**Dana (HR manager — PRODUCT.md primary):** Marketing language on a payroll-close surface undermines audit credibility. Wants "which reports, which period, export path" not product vision copy.

---

## Minor Observations

- Report list uses `shadow-sm` while DESIGN.md Flat HR Rule says HR cards/lists should be border-led only.
- Platform and Operations nav both use `FileSpreadsheet` for different jobs (config vs runtime list).
- `window.confirm` for delete is accessible but visually inconsistent with the shell.
- Filtered empty state ("No reports in Payroll") still lacks a "Show all areas" button.
- Source badge explanation remains tooltip-only (`title`), not exposed to screen readers.

---

## Questions to Consider

- Should Report Studio lead copy describe the actual workflow (list, preview, export) instead of aspirational builder language?
- Should first custom report creation auto-publish so Report Studio is never empty after save?
- Would a header action "Configure reports" beat a floating text link for admin discoverability?
