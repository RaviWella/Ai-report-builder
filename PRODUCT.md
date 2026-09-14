# Product

## Register

product

## Users

Two primary roles, both inside a client HR organisation or MintHRM support:

- **Builders** — non-technical HR admins (and MintHRM support staff) who design, preview, and publish custom report templates. They are domain experts in HR, not in SQL or data modelling. They build reports either by chatting with an AI assistant, by uploading a sample Excel layout, or by mixing both in one session. Their context: occasional, deliberate work, often under pressure to produce a specific report a manager asked for. They must never feel they need a developer.
- **Viewers** — end-users who run already-published reports, apply runtime filters, and download branded Excel or PDF. Their context: fast, repeated, task-focused. They want the right report, the right filters, and a clean export.

The job to be done: turn a question about the workforce ("active employees by department with total basic salary") into a correct, branded, downloadable report, with zero developer involvement and zero exposure of raw schema or PII.

## Product Purpose

A MintHRM module that lets non-technical users design, preview, and publish custom HR reports from a client's data. A **Builder panel** designs and publishes report templates; a **Viewer panel** runs published reports with filters and exports. Everything resolves through a semantic layer (business names, never raw columns); the AI returns a structured spec, never SQL, and never sees PII.

Success looks like: an HR admin builds, previews, and publishes a report by hand or by chat, a viewer runs it with runtime filters, and the export is branded and correct, all without a developer and without a single hand-written query.

## Brand Personality

Trustworthy, precise, and quietly guiding. The product handles real payroll and headcount data that people make decisions on, so it must read as accurate and audit-grade first. But its users are non-technical, so precision is delivered with a calm, low-anxiety hand: clear steps, plain labels, visible structure. Three words: **trustworthy, precise, guided.**

Voice: plain and concrete. Say what a control does and what a number means. No jargon from the data layer (no "semantic ref", no "data_spec") leaks into user-facing copy. Confidence comes from clarity, not from decoration.

## Anti-references

- **Generic admin template.** No boilerplate Material-dashboard look: endless identical card grids, purple gradients, decorative sidebar chrome, hero-metric tiles.
- **Dense enterprise BI** (Cognos / SAP / Crystal Reports). No cramped gray walls of controls that intimidate a non-technical admin. The power is there; it should not be frightening.
- **AI-chatbot-first.** The chat assistant is one of three equal ways to build (chat, Excel upload, manual). The report being built is always the subject; the conversation is a tool, not the centre of gravity.

## Design Principles

- **The report is the subject.** Whatever the user does, build by chat, upload an Excel, drag fields, the report preview is the thing they are shaping and should stay visible and central. Tools serve it.
- **Guide a non-expert without dumbing it down.** Surface structure and next steps clearly enough that an HR admin never needs a developer, while keeping full control (fields, filters, grouping, formatting) reachable.
- **Earn trust through precision.** Numbers, formats, and column meanings must read as correct and governed. Make published-vs-draft, versions, and what-will-export unambiguous.
- **Three doors, one room.** Chat, Excel upload, and manual building are peers that edit the same spec. None should feel like the "real" way; switching between them mid-session must feel native.
- **Match the platform.** This module lives inside MintHRM. It inherits the platform design system (teal, Inter, pill inputs, soft-bordered surfaces) so an admin never feels they left the product.

## Accessibility & Inclusion

Target **WCAG 2.1 AA**: body text ≥4.5:1 contrast (watch the muted gray `#6B7280` on tinted `#F9FAFB` surfaces), large text ≥3:1, full keyboard navigation for the field selector, filter panel, and data grids, visible focus states, and a `prefers-reduced-motion` alternative for every transition. Data is shown in tables and exports, not encoded by colour alone; conditional formatting must carry a non-colour cue (text/weight/icon) as well.
