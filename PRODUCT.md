# Product

## Register

product

## Users

**Primary:** HR managers and payroll analysts at mid-size organizations running month-end workforce reporting. They work inside MinHRM or a connected HR system, open MintHRM from the warehouse analytics widget, and need posted-transaction metrics they can defend in audits.

**Secondary:** HR operations staff and IT admins who configure ETL source databases, monitor extraction runs, and troubleshoot data freshness.

**Context:** Desktop-first, office lighting, often under time pressure during payroll close. Users expect spreadsheet-grade numbers, not narrative summaries. They switch between prebuilt reports (headcount, payroll, attendance), custom dbt views, and the Datamart Assistant for ad-hoc questions.

## Product Purpose

MintHRM is a governance-grade HR intelligence platform. It extracts data from customer source databases (MySQL/PostgreSQL), builds dimensional marts and semantic views, and surfaces deterministic analytics through a React workbench.

Success looks like:

- Every dashboard metric traces to a semantic view and posted HR transaction
- HR teams complete recurring reports without exporting to Excel first
- ETL status and data freshness are visible before numbers are trusted
- Ad-hoc analysis via Datamart Assistant stays read-only and grounded in cataloged schema

The product is not a general BI tool or an AI chatbot bolted onto charts. It is an auditable HR operations surface where design disappears into the task.

## Brand Personality

**Three words:** Authoritative, precise, calm.

**Voice:** Direct and operational. Name the report, the period, and the action. No marketing filler, no hype about AI transformation. Errors explain what failed and what to do next.

**Emotional goal:** Users should feel in command of workforce data, not impressed by interface chrome. Confidence comes from traceability and consistent patterns, not animation or novelty.

**Creative north star (visual):** The Workforce Command — committed teal signals where the system is active and where to act; neutrals carry the data.

## Anti-references

- **Generic AI SaaS dashboards:** identical metric-card grids, uppercase section kickers on every block, gradient accents, chat-first layouts that hide the underlying data model
- **Decorative status UI:** thick colored side stripes on cards and toasts, gradient avatars, blue-as-second-brand split across Datamart and HR shell
- **Marketing HR apps:** illustration-heavy empty states, oversimplified KPIs, playful tone that undermines audit credibility
- **Buzzword copy:** streamline, empower, seamless, world-class, next-generation framing

## Design Principles

1. **Traceability over spectacle.** If a number cannot be explained, it should not be prominent. UI prioritizes period context, source freshness, and drill-down paths.
2. **One command surface.** HR reports, ETL control, and Datamart Assistant share navigation, tokens, and interaction patterns. Assistant mode may add motion; it does not become a separate product skin.
3. **Density with hierarchy.** Tables and KPI rows are allowed to be dense; visual weight must show what matters this period, not give every metric equal billboard space.
4. **Operational feedback.** Loading, running ETL, failed extracts, and saved sources always show system status. Silent failure is unacceptable.
5. **Expert respect.** No forced tutorials, no patronizing empty states. First-time guidance is inline and dismissible; power users get batch paths and keyboard-friendly controls over time.

## Accessibility & Inclusion

**Target:** WCAG 2.1 AA for the React frontend.

**Requirements:**

- Keyboard navigation for sidebar, forms, tables, and modals
- Visible focus indicators on all interactive elements
- Body text contrast ≥ 4.5:1; large text ≥ 3:1
- Color never the sole indicator of status (pair with icon or label)
- `prefers-reduced-motion: reduce` honored on all transitions and entrance animations
- Form fields labeled; icon-only controls include accessible names

**Known considerations:** Data-heavy tables need sticky headers and horizontal scroll without trapping focus. Datamart chat composer and sidebar grouping are high-complexity surfaces and require dedicated screen-reader testing in a future pass.
