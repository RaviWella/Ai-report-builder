"""Kind + output-format helpers shared by the report and payslip paths.

A template version's `presentation_spec` is either a tabular-report PresentationSpec
(no `kind`, treated as "report") or a payslip envelope `{"kind":"payslip", ...}`.
These helpers let the common viewer/export code branch without each caller
re-implementing the discrimination.
"""

from __future__ import annotations

ALL_FORMATS = ("view", "excel", "pdf")
# What each kind can physically produce (intersected with the builder's allow-list).
SUPPORTED_BY_KIND = {
    "report": ("view", "excel", "pdf"),
    "document": ("pdf",),
    # A declarative rule-engine report (governed calculation) — tabular like a report.
    "rule_report": ("view", "excel", "pdf"),
}


def kind_of(presentation_spec: dict | None) -> str:
    kind = (presentation_spec or {}).get("kind")
    return kind if kind in SUPPORTED_BY_KIND else "report"


def allowed_formats(presentation_spec: dict | None) -> list[str]:
    """The builder's allow-list, intersected with what the kind can produce, in a
    stable order. Falls back to the kind's supported set when unset (older specs)."""
    ps = presentation_spec or {}
    kind = kind_of(ps)
    supported = SUPPORTED_BY_KIND[kind]
    chosen = ps.get("allowed_formats")
    if not chosen:
        chosen = ["pdf"] if kind == "document" else list(ALL_FORMATS)
    return [f for f in ALL_FORMATS if f in supported and f in chosen]
