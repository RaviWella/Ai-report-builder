---
name: MintHRM Intelligence Platform
description: Committed-teal HR operations workbench for workforce analytics, ETL control, and datamart reporting.
colors:
  primary: "#0f766e"
  primary-light: "#ccfbf1"
  primary-surface: "#f0fdfa"
  accent-sky: "#0284c7"
  accent-datamart: "#2b5eec"
  success: "#16a34a"
  warning: "#d97706"
  danger: "#dc2626"
  surface-page: "#f8fafc"
  surface-card: "#ffffff"
  sidebar: "#1e293b"
  sidebar-text: "#cbd5e1"
  text-primary: "#0f172a"
  text-secondary: "#64748b"
  border-default: "#e2e8f0"
typography:
  headline:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "normal"
  title:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "normal"
  body:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.025em"
  metric:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1.875rem"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "normal"
  mono:
    fontFamily: "ui-monospace, Menlo, Monaco, Cascadia Code, monospace"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "14px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  page: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "#0d9488"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-secondary:
    backgroundColor: "{colors.primary-light}"
    textColor: "#0f766e"
    rounded: "{rounded.md}"
    padding: "6px 12px"
  input-field:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: "10px 12px"
  card-metric:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.lg}"
    padding: "20px"
  nav-item-active:
    backgroundColor: "rgba(15, 118, 110, 0.3)"
    textColor: "#5eead4"
    rounded: "0px"
    padding: "10px 20px"
---

# Design System: MintHRM Intelligence Platform

## 1. Overview

**Creative North Star: "The Workforce Command"**

MintHRM is an HR operations command center: dense enough for payroll analysts and HR managers working through month-end, clear enough that a first-time user can find a report without training. Teal is the authority color. It marks where the system is active, where data is trustworthy, and where the user should act next. The interface should feel like a serious internal tool, not a marketing landing page or a generic AI dashboard.

The app splits into two surfaces today: a Tailwind-based HR shell (reports, ETL, settings) and a custom CSS Datamart workspace (chat, templates). The design direction is **committed teal unification**: one brand through-line, with Datamart allowed slightly more lift (shadow, motion) while HR reports stay flat and border-led.

**Key Characteristics:**

- Committed teal primary (`#0f766e`) on navigation active states, primary buttons, and status banners
- Single sans stack (system UI) with fixed rem scale, not fluid type
- Flat HR report surfaces: white cards on `slate-50` canvas, 1px borders
- Hybrid elevation: HR flat at rest; Datamart panels use light shadow vocabulary
- Confident, tactile buttons: solid fills, visible hover darkening, teal focus rings
- Data-first density: tables, metric grids, and period filters over decorative chrome

## 2. Colors

Committed teal carries 30–60% of interactive and navigational surfaces. Neutrals handle reading and tabular data.

### Primary

- **Command Teal** (`#0f766e`): Primary buttons, ETL run actions, focus ring hue, legacy `--color-primary`. The default "do something" color across HR surfaces.
- **Active Teal Tint** (`#ccfbf1` / `#f0fdfa`): Secondary button backgrounds, success banners, primary source badges. Light enough for large fills without washing out text.
- **Sidebar Active Glow** (teal-700 at 30% opacity + `#5eead4` text): Current nav item in the dark sidebar. Teal presence in the chrome, not just the canvas.

### Secondary

- **Sky Accent** (`#0284c7`): Legacy `--color-accent` in root tokens. Use sparingly for info states only; do not introduce as a second brand color on new screens.
- **Datamart Blue** (`#2b5eec`): Transitional accent in Datamart chat avatars and composer highlights. **Target state:** migrate to Command Teal variants; treat as deprecated for new work.

### Tertiary

- **Semantic Green** (`#16a34a`): Positive metric values, completed ETL status chips.
- **Semantic Amber** (`#d97706`): Warnings, in-progress ETL status.
- **Semantic Red** (`#dc2626`): Errors, negative metrics, destructive hover.

### Neutral

- **Ink** (`#0f172a`): Primary body text, metric values at rest.
- **Muted Slate** (`#64748b`): Secondary labels, table metadata, placeholders (must meet 4.5:1 on white; bump toward ink if borderline).
- **Page Canvas** (`#f8fafc`): Main content background (`bg-slate-50`).
- **Card Surface** (`#ffffff`): Cards, tables, modals.
- **Border** (`#e2e8f0`): Default 1px card and table borders.
- **Command Sidebar** (`#1e293b`): Left navigation shell; pairs with `#cbd5e1` default link text.

### Named Rules

**The Committed Teal Rule.** Teal appears on primary actions, active navigation, and positive system status. It is never decorative fill on idle cards. If a surface does not invite action or indicate selection, it stays neutral.

**The No Washed Gray Rule.** Gray text (`slate-400`–`slate-500`) on tinted backgrounds (teal-50, red-50, amber-50) is prohibited. Use a darker shade of the background hue or ink at reduced opacity.

## 3. Typography

**Display Font:** ui-sans-serif / system-ui stack (no separate display family)
**Body Font:** Same system sans stack
**Label/Mono Font:** ui-monospace for SQL, connection strings, and ETL table names

**Character:** Technical and legible. One family, weight contrast does the hierarchy. No display fonts in UI chrome. Sentence case is preferred; uppercase reserved for short nav section labels (≤1 word) and is being phased down on metric labels.

### Hierarchy

- **Headline** (700, 1.5rem / 24px, line-height 1.25): Page titles (`h1`, `text-2xl font-bold text-slate-800`). One per view.
- **Title** (600, 0.875rem / 14px): Card section headers, table column headers, form section titles.
- **Body** (400, 0.875rem / 14px): Descriptions, table cells, banner copy. Cap prose blocks at 65–75ch where applicable.
- **Label** (500, 0.75rem / 12px, letter-spacing 0.025em): Form labels, period filter label, compact metadata. Prefer sentence case over uppercase.
- **Metric** (700, 1.875rem / 30px, line-height 1): `MetricCard` values; tabular nums for currency and counts.

### Named Rules

**The Fixed Scale Rule.** Product UI uses fixed rem steps (`text-xs` through `text-2xl`), not fluid clamp headings. Users view at consistent DPI; exaggerated display type creates noise in sidebars and dense tables.

**The One Family Rule.** Do not add a second sans for headings. Hierarchy is weight and size, not font switching.

## 4. Elevation

Hybrid model. HR report pages are **flat by default**: depth comes from white cards on a tinted canvas and 1px `#e2e8f0` borders. Datamart workspace is **lightly lifted**: panels and toasts use diffuse shadows; sidebar mobile overlay uses backdrop blur sparingly.

### Shadow Vocabulary

- **Toast lift** (`box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1)`): Transient feedback only (toasts).
- **Datamart ambient** (`0 1px 2px rgba(15, 23, 42, 0.05)`): Subtle panel separation in workspace.
- **Datamart raised** (`0 4px 16px rgba(15, 23, 42, 0.08)`): Floating sidebar, composer focus states.

### Named Rules

**The Flat HR Rule.** Metric cards and data tables on HR routes do not carry box-shadow at rest. Hover may tint row background (`slate-50/80`), not lift the card.

**The Shadow-on-State Rule.** Shadows appear as feedback (toast, modal, mobile sidebar overlay), not as default card decoration.

## 5. Components

Confident and tactile: solid teal primaries, 150–250ms color transitions, visible `:focus-visible` rings.

### Buttons

- **Shape:** Gently rounded (8px / `rounded-lg`); primary CTAs on settings modals use 12px (`rounded-xl`).
- **Primary:** Command Teal background (`#0f766e`), white text, `8px 16px` padding, `text-sm font-medium`. Used for "Run ETL", "Save", "Add source".
- **Hover / Focus:** Background shifts to `#0d9488` (teal-600); `focus:ring-2 focus:ring-teal-500/30`. No bounce or scale transforms.
- **Secondary:** Teal-50 background (`#ccfbf1`), teal-700 text; for export and preview actions in report lists.
- **Ghost / Tertiary:** White or transparent with `border-slate-200`; hover `bg-slate-50`.

### Chips

- **Style:** Rounded-full pills (`text-xs font-medium px-2 py-0.5`). Status chips use semantic tinted backgrounds (green/red/yellow-100) with matching text-700.
- **State:** Primary source badge uses teal-50 + teal-700; database type badge uses slate-100 + slate-500.

### Cards / Containers

- **Corner Style:** 12px (`rounded-xl`) for metric cards, tables, and panel containers.
- **Background:** White on HR pages; Datamart may use `--dm-surface-muted` (`#f8fafc`) for inset areas.
- **Shadow Strategy:** None at rest on HR; see Elevation for Datamart.
- **Border:** 1px `border-slate-200` always on HR cards.
- **Internal Padding:** 20px (`p-5`) for metrics; 16px (`px-4 py-3`) for table cells.

### Inputs / Fields

- **Style:** White background, `border-slate-200`, 8px radius, `text-sm`. Placeholder `text-slate-400` (verify contrast).
- **Focus:** `focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500`; outline removed.
- **Error / Disabled:** Red-50 banner with red-800 text for form-level errors; `disabled:opacity-50` on buttons.

### Navigation

- **Shell:** 240px dark sidebar (`#1e293b`), full viewport height.
- **Typography:** `text-sm` links with 16px Lucide icons; section labels `text-[10px] uppercase tracking-wider text-slate-500`.
- **Default:** `text-slate-300`, hover `bg-slate-800 text-slate-100`.
- **Active:** `bg-teal-700/30 text-teal-300 font-medium`.
- **Mobile:** Datamart workspace sidebar collapses with fixed backdrop (`rgba(15,23,42,0.45)`); HR shell is desktop-first.

### MetricCard (signature component)

- White bordered card, 12px radius, 20px padding.
- Label: `text-xs text-slate-500 font-medium` (migrating from uppercase to sentence case).
- Value: `text-3xl font-bold`; semantic green/red when trend props set.
- Used across Dashboard and all HR report KPI rows.

## 6. Do's and Don'ts

### Do:

- **Do** use Command Teal (`#0f766e`) for every primary action and active nav state across HR and Datamart.
- **Do** keep HR report pages flat: white card + 1px border on `#f8fafc` canvas.
- **Do** use skeleton placeholders for loading metric grids and tables (target state; replace text-only "Loading…" pulses).
- **Do** pair icons with text labels in navigation and primary actions (16px icon, `text-sm` label).
- **Do** honor `prefers-reduced-motion: reduce` on all transitions and entrance animations.
- **Do** use semantic color only for status (success, warning, danger), never as decoration.

### Don't:

- **Don't** use `border-left` or `border-right` greater than 1px as a colored accent stripe on cards, toasts, or list items (no `border-l-4` status toasts; no `w-1` source card stripes).
- **Don't** introduce Datamart Blue (`#2b5eec`) or gradient avatars on new components; unify on teal.
- **Don't** put uppercase tracked eyebrows above every dashboard section; use sentence-case titles or spacing alone for grouping.
- **Don't** use identical metric-card grids without hierarchy (hero metrics vs supporting stats).
- **Don't** use gray text on colored tinted backgrounds without contrast verification.
- **Don't** animate `width`, `height`, or `margin` for layout; use `transform` and `opacity`.
- **Don't** use arbitrary z-index (`z-[100]`); use a semantic scale (toast: 50, modal backdrop: 40, modal: 50).
- **Don't** ship glassmorphism, gradient text, or hero-metric SaaS templates (big number + gradient accent + eyebrow kicker).
