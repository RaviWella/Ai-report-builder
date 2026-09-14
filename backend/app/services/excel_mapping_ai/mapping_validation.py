"""Never trust the AI's raw JSON: every returned header must be one of the
headers this turn was actually allowed to map, and every non-null ref must
resolve in the tenant's real catalogue — same never-trust-raw-JSON principle
as `rule_report_ai/spec_validation.py`, much simpler check."""

from __future__ import annotations

from app.domain.semantic import SemanticCatalog


def validate_mapping(
    catalog: SemanticCatalog, allowed_headers: list[str], raw_mappings: list[dict] | None,
) -> tuple[dict[str, str | None] | None, str | None]:
    """Returns (mapping, None) if every entry is well-formed, else (None,
    error). `mapping` is `{header: ref_or_None}`, one entry per validated
    item — never all of `allowed_headers` (the AI may only resolve some)."""
    if not raw_mappings:
        return None, None

    allowed = set(allowed_headers)
    bad_headers: list[str] = []
    bad_refs: list[str] = []
    out: dict[str, str | None] = {}
    for item in raw_mappings:
        header = item.get("header")
        ref = item.get("ref")
        if header not in allowed:
            bad_headers.append(str(header))
            continue
        if ref is not None:
            try:
                catalog.resolve(ref)
            except ValueError:
                bad_refs.append(f"{header!r} -> {ref!r}")
                continue
        out[header] = ref

    if bad_headers or bad_refs:
        parts = []
        if bad_headers:
            parts.append(f"header(s) not in the allowed list: {bad_headers}")
        if bad_refs:
            parts.append(f"unknown ref(s): {bad_refs}")
        return None, "; ".join(parts)
    return out, None
