"""MintHRM Data Intake layer.

Canonical target registry + classifier + mapper for HR domain files.

Mirrors mint-analytics data_intake architecture exactly:
  canonical_targets  — CanonicalTarget / CanonicalField registry
  classifier         — scores a FileProfile against all targets
  mapper             — maps source headers to canonical fields
  canonical_rows     — streams CanonicalRow from an approved intake record
  ontology           — recognises unmapped HR concepts (not-wired warnings)
  tenant_config      — per-tenant alias / date-format / severity overrides
"""
