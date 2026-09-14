"""Report run/preview/export orchestration (run-time flow, SRS §10.2).

Run-time flow (NO AI participates):
  resolve published version -> load pinned semantic catalogue -> compile + run on
  the read replica -> (optionally) render -> audit.

This binds the report to the EXACT semantic version it was published against
(semantic_version_ref), so older versions stay reproducible after a mapping change.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.db.metadata import ReportRun
from app.domain.enums import AuditAction, ExportFormat
from app.domain.report_spec import DataSpec, PresentationSpec
from app.query_engine.runner import QueryResult, run_query
from app.rendering.render_service import render
from app.repositories.template_repo import TemplateRepo
from app.services.audit_service import AuditService
from app.services.result_cache import cached_snapshot_ref
from app.services.semantic_service import SemanticService
from app.services.tenant_scope import resolve_datamart_key


@dataclass
class ResolvedReport:
    data_spec: DataSpec
    presentation_spec: PresentationSpec
    semantic_version_ref: int


def _total_labels(data_spec: DataSpec) -> set[str]:
    """Column headers the user flagged to sum (fields with total=True) — matched
    against the export's column headers to place a SUM in the totals row."""
    return {
        (f.label or f.ref.split(".")[-1].replace("_", " ").title())
        for f in data_spec.fields if getattr(f, "total", False)
    }


def _is_blank(v: Any) -> bool:
    """A runtime param counts as 'not supplied' when None/empty/all-empty range."""
    if v is None or v == "":
        return True
    if isinstance(v, (list, tuple)):
        return len(v) == 0 or all(x in (None, "") for x in v)
    return False


def _round_numbers(rows: list[dict[str, Any]], places: int = 2) -> None:
    """Round numeric cell values to `places` decimals, in place — removes floating-
    point tails (e.g. 190.82000000000005 -> 190.82) so the viewer and Excel/PDF show a
    clean number. Integers and non-numerics are left untouched."""
    from decimal import Decimal

    for row in rows:
        for k, v in row.items():
            if isinstance(v, bool):
                continue
            if isinstance(v, float):
                row[k] = round(v, places)
            elif isinstance(v, Decimal):
                row[k] = round(v, places)


def _apply_row_numbers(rows: list[dict[str, Any]], column: str | None) -> None:
    """Number rows 1..N under `column`, in place — presentation-only (a display
    convenience, not part of the governed spec). `column` is made the row dict's
    FIRST key (not just set on the existing dict, which would append it last):
    the Excel/PDF renderers align cells to `result.columns` POSITIONALLY, by each
    row dict's key order, not by name — so a numbering column must lead the row
    exactly where it leads `result.columns`, or every other cell shifts left by
    one. No-op if `column` isn't set."""
    if not column:
        return
    for i, row in enumerate(rows, start=1):
        original = dict(row)
        row.clear()
        row[column] = i
        row.update(original)


def _inject_subtotals(rows: list[dict[str, Any]], cfg: dict | None) -> list[dict[str, Any]]:
    """Insert a synthetic "Total" row after each run of consecutive rows sharing
    the same `group_by` key (rows must already be ordered by that key — e.g. via
    the spec's `order_by`). Presentation-only, generic to any rule report: `cfg`
    is `{group_by: [...], sum_columns: [...], label_column: str, label: str}`.
    The injected row copies the group's LAST row (so descriptive columns like a
    name carry over), overrides `label_column` with `label` and `sum_columns`
    with the running sums, and is tagged `_row_kind: "subtotal"` so a renderer
    can style it — it is never itself summed or counted as data. No-op if `cfg`
    or `rows` is empty."""
    if not cfg or not rows:
        return rows
    group_by = cfg.get("group_by") or []
    sum_columns = cfg.get("sum_columns") or []
    label_column = cfg.get("label_column")
    label = cfg.get("label", "Total")
    if not group_by or not label_column:
        return rows

    out: list[dict[str, Any]] = []
    current_key: tuple | None = None
    last_row: dict[str, Any] | None = None
    running: dict[str, Any] = {}

    def flush() -> None:
        if last_row is None:
            return
        out.append({
            **last_row, label_column: label,
            **{c: running.get(c, 0) for c in sum_columns},
            "_row_kind": "subtotal",
        })

    for row in rows:
        key = tuple(row.get(g) for g in group_by)
        if key != current_key:
            flush()
            current_key = key
            running = {c: 0 for c in sum_columns}
        for c in sum_columns:
            v = row.get(c)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                running[c] += v
        out.append(row)
        last_row = row
    flush()
    return out


def _pivot_column_label(raw: Any, date_format: str | None) -> str:
    """The display header for one dynamic pivot column. `raw` is whatever
    value `column_field` held on a source row (e.g. a `datetime.date`, or a
    plain string like "01" if the report already formats it) — try to read
    it as a date and apply `date_format` (e.g. "%d %b" -> "01 Aug"); anything
    that isn't date-shaped, or no format given, is shown as-is."""
    import datetime as _dt

    if not date_format:
        return str(raw)
    if isinstance(raw, _dt.datetime):
        return raw.strftime(date_format)
    if isinstance(raw, _dt.date):
        return raw.strftime(date_format)
    try:
        return _dt.date.fromisoformat(str(raw)).strftime(date_format)
    except ValueError:
        return str(raw)


def _apply_pivot(
    rows: list[dict[str, Any]], columns: list[str], pivot: dict | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Reshape LONG rows (one row per e.g. employee+date) into WIDE rows (one
    row per employee, one column per DISTINCT `column_field` value actually
    present in `rows`) — see PivotSpec's docstring. The column set is driven
    entirely by the data, so a date-range filter naturally yields one column
    per date in range without this function knowing anything about dates.

    Each identity row's per-cell status (when `status_field` is set) is
    carried in a `_cell_status: {column_label: status}` key — excluded from
    the returned column list so it never becomes a visible column itself
    (the same trick `_row_kind` already uses for a subtotal row), read only
    by the renderers to pick a cell's background color. No-op if `pivot` or
    `rows` is empty."""
    if not pivot or not rows:
        return rows, columns
    from app.domain.report_spec import PivotSpec

    p = PivotSpec.model_validate(pivot)
    identity_cols = [c for c in columns if c not in (p.column_field, p.value_field, p.status_field)]

    grouped: dict[tuple, dict[str, Any]] = {}
    order: list[tuple] = []
    # label -> one raw value seen for it, so dynamic columns sort by the
    # underlying value (chronologically for dates) rather than alphabetically
    # by their formatted label ("10 Aug" would otherwise sort before "2 Aug").
    raw_by_label: dict[str, Any] = {}

    for row in rows:
        key = tuple(row.get(c) for c in identity_cols)
        if key not in grouped:
            grouped[key] = {c: row.get(c) for c in identity_cols}
            grouped[key]["_cell_status"] = {}
            order.append(key)
        raw = row.get(p.column_field)
        label = _pivot_column_label(raw, p.column_label_format)
        raw_by_label.setdefault(label, raw)
        grouped[key][label] = row.get(p.value_field)
        if p.status_field:
            grouped[key]["_cell_status"][label] = row.get(p.status_field)

    sorted_labels = sorted(raw_by_label, key=lambda lbl: (raw_by_label[lbl] is None, raw_by_label[lbl]))
    new_columns = [*identity_cols, *sorted_labels]
    new_rows = [grouped[k] for k in order]
    # Not every identity necessarily has a row for every dynamic column (e.g.
    # an employee who joined mid-range has no data for earlier dates) — a
    # row missing a label's key entirely, rather than holding None for it,
    # broke the renderers' ref/label-identity cell lookup (resolve_row_key),
    # which then fell back to a POSITIONAL guess into that row's own
    # (shorter) key list and could land on the `_cell_status` dict itself —
    # "Unsupported type <class 'dict'> in write()". Backfill explicitly so
    # every row has every dynamic column as a real (possibly None) key.
    for row in new_rows:
        for label in sorted_labels:
            row.setdefault(label, None)
    return new_rows, new_columns


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TemplateRepo(db)
        self.semantic = SemanticService(db)
        self.audit = AuditService(db)

    def _datamart_key(self, tenant_id: str) -> str:
        return resolve_datamart_key(tenant_id)

    def _export_branding(self, ctx: TenantContext, opts: dict):  # noqa: ANN202
        """Build the export header/footer for a rule report from its options:
        company name (top banner), a description, and a 'Generated by … on …' stamp."""
        from datetime import datetime, timezone

        from app.domain.report_spec import Branding

        header_parts: list[str] = []
        if opts.get("show_company"):
            header_parts.append(ctx.tenant_id.replace("_", " ").title())
        if opts.get("description"):
            header_parts.append(str(opts["description"]).strip())
        footer = "Confidential"
        if opts.get("show_meta"):
            when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            footer = f"Generated by {ctx.acting_user_id} on {when} UTC · Confidential"
        return Branding(header=" — ".join(p for p in header_parts if p) or None, footer=footer)

    def _resolve_published(self, ctx: TenantContext, template_id: str) -> ResolvedReport:
        tpl = self.repo.get_template(template_id)
        if tpl is None:
            raise ValueError("Template not found for this tenant")
        version = self.repo.get_published_version(template_id)
        if version is None:
            raise ValueError("Template has no published version")
        if (version.presentation_spec or {}).get("kind") == "document":
            raise ValueError("This is a per-record document — render it as a document, not a table report.")
        return ResolvedReport(
            data_spec=DataSpec.model_validate(version.data_spec),
            presentation_spec=PresentationSpec.model_validate(version.presentation_spec),
            semantic_version_ref=version.semantic_version_ref,
        )

    def _published_version(self, ctx: TenantContext, template_id: str):  # noqa: ANN202
        if self.repo.get_template(template_id) is None:
            raise ValueError("Template not found for this tenant")
        version = self.repo.get_published_version(template_id)
        if version is None:
            raise ValueError("Template has no published version")
        return version

    def rule_report_chat_session(self, ctx: TenantContext, template_id: str) -> dict | None:
        """The chat conversation linked to this rule report (session_id passed to
        create/update_rule_report — presentation_spec.chat_session_id), so
        reopening the report to edit it can resume that SAME conversation
        instead of starting blank. Tenant-wide, not creator-only — ANY user in
        the tenant editing this report should see how it was built (see
        ChatHistoryService.get_for_template()). Returns None (never raises) for
        a template/version that doesn't exist, has no linked session, or whose
        linked session was since deleted — all just mean "nothing to resume"."""
        from app.services.chat_history import ChatHistoryService

        version = self.repo.get_published_version(template_id)
        if version is None:
            return None
        session_id = (version.presentation_spec or {}).get("chat_session_id")
        if not session_id:
            return None
        return ChatHistoryService(self.db).get_for_template(ctx, session_id)

    def view_meta(self, ctx: TenantContext, template_id: str) -> dict:
        """Everything the common viewer needs to render a template's Generate
        controls, for BOTH reports and payslips: its kind, the output formats the
        builder allowed, and the runtime filters (period, employee, …)."""
        from app.services.template_kind import allowed_formats, kind_of

        version = self._published_version(ctx, template_id)
        ps = version.presentation_spec or {}
        return {
            "kind": kind_of(version.presentation_spec),
            "allowed_formats": allowed_formats(version.presentation_spec),
            "filters": self.runtime_filters(ctx, template_id),
            "data_quality": self._data_quality(ctx),  # WS-3 serve policy (from stored results)
            # rule reports: friendly column titles + output order for the viewer
            "labels": ps.get("labels", {}),
            "columns": (ps.get("spec") or {}).get("output", []),
        }

    def _data_quality(self, ctx: TenantContext) -> dict:
        """The latest stored validation summary for the tenant — so the viewer can
        warn when a critical data-quality assertion is failing. Never hits the
        datamart (reads mart_validation_result)."""
        from app.services.validation_service import ValidationService

        try:
            return ValidationService(self.db).latest(ctx).get("summary", {})
        except Exception:  # noqa: BLE001 - data-quality must never break meta
            return {}

    def runtime_filters(self, ctx: TenantContext, template_id: str) -> list[dict]:
        """The view-time filters the builder enabled for this published template,
        with field metadata so the viewer can render the right control. Reads the
        data_spec only, so it works for reports AND payslips (no PresentationSpec)."""
        version = self._published_version(ctx, template_id)
        ps = version.presentation_spec or {}
        if ps.get("kind") == "rule_report":
            from app.domain.rule_report import RuleReportSpec
            spec = RuleReportSpec.model_validate(ps.get("spec", {}))
            return [
                {"param": f.name, "ref": f.column, "op": f.op,
                 "label": f.label or f.name, "type": f.type, "role": "dimension",
                 "required": f.required, "enum_values": None}
                for f in spec.filters
            ]
        data_spec = DataSpec.model_validate(version.data_spec)
        catalog = self.semantic.get_pinned_catalog(ctx.tenant_id, version.semantic_version_ref)
        fidx = catalog.field_index()
        param_meta = {p.name: p for p in data_spec.runtime_params}

        out: list[dict] = []
        seen: set[str] = set()
        for f in data_spec.filters:
            if not f.param or f.param in seen:
                continue
            seen.add(f.param)
            fld = fidx.get(f.ref)
            rp = param_meta.get(f.param)
            out.append(
                {
                    "param": f.param,
                    "ref": f.ref,
                    "op": f.op.value,
                    "label": (rp.label if rp and rp.label else (fld.label if fld else f.param)),
                    "type": (rp.type.value if rp else (fld.type.value if fld else "string")),
                    "role": fld.role.value if fld else "dimension",
                    "required": rp.required if rp else False,
                    "enum_values": (rp.enum_values if rp else None) or (fld.sample_values if fld else None),
                }
            )
        return out

    def field_values(self, ctx: TenantContext, ref: str, limit: int = 500) -> list[Any]:
        """Distinct values for a dimension field — populates viewer dropdowns."""
        from app.query_engine.values import distinct_values

        catalog = self.semantic.get_active_catalog(ctx.tenant_id)
        return distinct_values(
            ctx=ctx, datamart_key=self._datamart_key(ctx.tenant_id),
            catalog=catalog, ref=ref, limit=limit,
        )

    def run(
        self,
        ctx: TenantContext,
        template_id: str,
        params: dict[str, Any],
        *,
        preview: bool = False,
        log_fmt: str = "view",
    ) -> QueryResult:
        version = self._published_version(ctx, template_id)
        if (version.presentation_spec or {}).get("kind") == "rule_report":
            return self._run_rule(ctx, template_id, version, params)

        resolved = self._resolve_published(ctx, template_id)
        # Required runtime params (e.g. payroll period) must be supplied — guards
        # direct API calls and scheduled exports, not just the UI.
        missing = [
            rp.label or rp.name
            for rp in resolved.data_spec.runtime_params
            if rp.required and _is_blank(params.get(rp.name))
        ]
        if missing:
            raise ValueError(f"Please choose a value for: {', '.join(missing)}")
        catalog = self.semantic.get_pinned_catalog(ctx.tenant_id, resolved.semantic_version_ref)
        datamart_key = self._datamart_key(ctx.tenant_id)
        # Freshness anchor (cached briefly) — keys the result cache AND stamps the run.
        snapshot = cached_snapshot_ref(ctx, datamart_key)
        started = time.monotonic()
        result = run_query(
            ctx=ctx, datamart_key=datamart_key, spec=resolved.data_spec,
            catalog=catalog, params=params, preview=preview,
            snapshot_ref=snapshot, use_cache=True,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        self.audit.log(
            user_id=ctx.acting_user_id,
            action=AuditAction.REPORT_RUN,
            target_type="template",
            target_id=template_id,
            detail={"preview": preview, "row_count": result.row_count,
                    "params": list(params), "cached": result.from_cache},
        )
        # WS-1 — record run lineage for real runs (not the building-time preview).
        if not preview:
            self._log_run(ctx, template_id, resolved, result, log_fmt, duration_ms, snapshot)
        return result

    def _run_rule(self, ctx: TenantContext, template_id: str, version, params: dict[str, Any]):  # noqa: ANN001,ANN202
        """Run a declarative rule-report (governed calculation) via the rule engine.
        The RuleReportSpec is stored in presentation_spec.spec; runtime filters come
        from the spec. Executes read-only on the tenant's mart like any report."""
        from app.domain.rule_report import RuleReportSpec
        from app.query_engine.rule_runner import run_rule_report

        spec = RuleReportSpec.model_validate((version.presentation_spec or {}).get("spec", {}))
        missing = [f.label or f.name for f in spec.filters
                   if f.required and _is_blank(params.get(f.name))]
        if missing:
            raise ValueError(f"Please choose a value for: {', '.join(missing)}")
        result = run_rule_report(
            ctx=ctx, datamart_key=self._datamart_key(ctx.tenant_id), spec=spec, params=params,
        )
        _round_numbers(result.rows)   # clean floating-point tails to 2 dp (viewer + exports)
        ps = version.presentation_spec or {}
        # Pivot FIRST — a wide (one-row-per-employee) reshape of the long result —
        # so row numbering/subtotals below, if also configured, apply to the final
        # (post-pivot) rows, not the pre-pivot per-day ones.
        result.rows, result.columns = _apply_pivot(result.rows, result.columns, ps.get("pivot"))
        s_no_col = ps.get("row_number_column")
        if s_no_col:
            _apply_row_numbers(result.rows, s_no_col)
            if s_no_col not in result.columns:
                result.columns = [s_no_col, *result.columns]
        result.rows = _inject_subtotals(result.rows, ps.get("subtotal"))
        if s_no_col:   # a subtotal row isn't itself row N of anything — blank it
            for row in result.rows:
                if row.get("_row_kind") == "subtotal":
                    row[s_no_col] = None
        result.row_count = len(result.rows)
        self.audit.log(
            user_id=ctx.acting_user_id,
            action=AuditAction.REPORT_RUN, target_type="template", target_id=template_id,
            detail={"kind": "rule_report", "row_count": result.row_count, "params": list(params)},
        )
        return result

    @staticmethod
    def _rule_presentation(rule, name: str, labels: dict | None,
                           export_options: dict | None = None,
                           row_number_column: str | None = None,
                           subtotal: dict | None = None,
                           totals: list[str] | None = None,
                           pivot: dict | None = None,
                           session_id: str | None = None) -> dict:
        """The presentation_spec for a rule report: the validated spec, friendly column
        titles (labels), export-header options (company / description / stamp), and
        optional output-shaping (a row-number column, per-group subtotal rows, which
        `output` columns get a grand-total row in Excel/PDF, an optional wide/pivot
        reshape — see PivotSpec) — all display concerns, never part of the governed
        RuleReportSpec itself. `session_id` (when the report was built/edited via the
        AI chat) links back to that conversation so reopening the report to edit it
        can resume the SAME chat instead of starting blank — see
        ChatHistoryService.get_for_template()."""
        return {
            "kind": "rule_report", "title": name,
            "spec": rule.model_dump(by_alias=True),
            "labels": {k: v for k, v in (labels or {}).items() if v},
            "export_options": export_options or {},
            "row_number_column": row_number_column or None,
            "subtotal": subtotal or None,
            "totals": totals or [],
            "pivot": pivot or None,
            "chat_session_id": session_id or None,
            "allowed_formats": ["view", "excel", "pdf"],
        }

    def _link_chat_session(self, session_id: str | None, template_id: str) -> None:
        """Best-effort: populate AISession.template_id (a column that's
        existed since the schema was scaffolded but was never set anywhere)
        so the session ALSO points back at the report — a missing/invalid
        session_id must never fail the save."""
        if not session_id:
            return
        from app.db.metadata import AISession

        session = self.db.get(AISession, session_id)
        if session is not None:
            session.template_id = template_id

    def create_rule_report(self, ctx: TenantContext, *, name: str, spec: dict,
                           description: str | None = None, category: str = "General",
                           labels: dict | None = None, export_options: dict | None = None,
                           row_number_column: str | None = None,
                           subtotal: dict | None = None,
                           totals: list[str] | None = None,
                           pivot: dict | None = None,
                           session_id: str | None = None) -> dict:
        """Create + publish a rule-report template from a JSON spec. The spec is
        validated (governed shape) and stored in presentation_spec; it then runs
        + exports through the normal report path. Catalog-independent. `category`
        is the module it's filed under; `labels` are optional friendly column titles."""
        from app.domain.report_spec import PivotSpec
        from app.domain.rule_report import RuleReportSpec

        rule = RuleReportSpec.model_validate(spec)   # raises on a malformed spec
        if pivot is not None:
            PivotSpec.model_validate(pivot)   # raises on a malformed pivot config
        tpl = self.repo.create_template(
            name=name, description=description,
            created_by=ctx.acting_user_id, module=category or "General",
        )
        version = self.repo.add_version(
            template_id=tpl.id, data_spec={},
            presentation_spec=self._rule_presentation(
                rule, name, labels, export_options, row_number_column, subtotal, totals, pivot,
                session_id),
            semantic_version_ref=0, status="published", created_by=ctx.acting_user_id,
        )
        self.repo.set_published(tpl.id, version.id)
        self._link_chat_session(session_id, tpl.id)
        self.db.commit()
        self.audit.log(
            user_id=ctx.acting_user_id,
            action=AuditAction.VERSION_PUBLISHED, target_type="template", target_id=tpl.id,
            detail={"kind": "rule_report", "name": name},
        )
        return {"template_id": tpl.id, "version_id": version.id, "name": name}

    def update_rule_report(self, ctx: TenantContext, template_id: str, *, name: str,
                           spec: dict, description: str | None = None,
                           category: str | None = None, labels: dict | None = None,
                           new_version: bool = False, note: str = "",
                           export_options: dict | None = None,
                           row_number_column: str | None = None,
                           subtotal: dict | None = None,
                           totals: list[str] | None = None,
                           pivot: dict | None = None,
                           session_id: str | None = None) -> dict:
        """Save an edit to a rule report. By default the CURRENT published version is
        updated in place (so routine edits don't spam the version history). Set
        `new_version=True` to snapshot a NEW version — deliberately, with a `note`
        describing what changed (kept in the version's presentation_spec)."""
        from app.domain.report_spec import PivotSpec
        from app.domain.rule_report import RuleReportSpec

        rule = RuleReportSpec.model_validate(spec)
        if pivot is not None:
            PivotSpec.model_validate(pivot)   # raises on a malformed pivot config
        tpl = self.repo.get_template(template_id)
        if tpl is None:
            raise ValueError("Report not found")
        if name and name.strip():
            tpl.name = name.strip()
        if category and category.strip():
            tpl.module = category.strip()
        if description is not None:
            tpl.description = description.strip() or None

        presentation = self._rule_presentation(
            rule, name, labels, export_options, row_number_column, subtotal, totals, pivot,
            session_id)
        if note.strip():
            presentation["note"] = note.strip()
        self._link_chat_session(session_id, template_id)

        current = self.repo.get_published_version(template_id)
        if new_version or current is None:
            version = self.repo.add_version(
                template_id=template_id, data_spec={}, presentation_spec=presentation,
                semantic_version_ref=0, status="published", created_by=ctx.acting_user_id,
            )
            self.repo.set_published(template_id, version.id)
            version_id = version.id
        else:
            current.presentation_spec = presentation   # update in place — no new version
            self.db.flush()
            version_id = current.id
        self.db.commit()
        self.audit.log(
            user_id=ctx.acting_user_id,
            action=AuditAction.VERSION_PUBLISHED, target_type="template", target_id=template_id,
            detail={"kind": "rule_report", "name": name,
                    "new_version": bool(new_version or current is None)},
        )
        return {"template_id": template_id, "version_id": version_id, "name": name}

    def _log_run(
        self, ctx: TenantContext, template_id: str, resolved: "ResolvedReport",
        result: QueryResult, fmt: str, duration_ms: int, snapshot: str | None,
    ) -> None:
        """Persist a ReportRun row and stamp the result with its provenance, so an
        export/footer can show 'version vX · run <id> · checksum <…>'."""
        run = ReportRun(
            report_id=template_id,
            semantic_version_ref=resolved.semantic_version_ref,
            compiled_sql_hash=result.compiled_sql_hash,
            result_checksum=result.result_checksum,
            datamart_snapshot_ref=snapshot,
            row_count=result.row_count, duration_ms=duration_ms,
            status="ok", fmt=fmt, executed_by=ctx.acting_user_id,
        )
        self.db.add(run)
        self.db.commit()
        result.run_id = run.id
        result.semantic_version_ref = resolved.semantic_version_ref
        result.datamart_snapshot_ref = snapshot

    def preview_spec(
        self, ctx: TenantContext, data_spec: DataSpec, params: dict[str, Any]
    ) -> QueryResult:
        """Live preview during building (Phase 2) — runs an unsaved data_spec on a
        small sample against the ACTIVE catalogue."""
        catalog = self.semantic.get_active_catalog(ctx.tenant_id)
        datamart_key = self._datamart_key(ctx.tenant_id)
        return run_query(
            ctx=ctx,
            datamart_key=datamart_key,
            spec=data_spec,
            catalog=catalog,
            params=params,
            preview=True,
            snapshot_ref=cached_snapshot_ref(ctx, datamart_key),
            use_cache=True,
        )

    def export(
        self,
        ctx: TenantContext,
        template_id: str,
        params: dict[str, Any],
        fmt: ExportFormat,
    ) -> tuple[bytes, str]:
        from app.services.template_kind import allowed_formats, kind_of

        version = self._published_version(ctx, template_id)
        ps = version.presentation_spec
        # The allow-list speaks "excel"/"pdf"/"view"; ExportFormat speaks "xlsx"/"pdf".
        fmt_token = "excel" if fmt == ExportFormat.XLSX else fmt.value
        if fmt_token not in allowed_formats(ps):
            raise ValueError(f"This template doesn't allow {fmt_token.upper()} download.")

        # Documents (one page per record) render through the common Generate too,
        # scoped by the same runtime params (period year/month, record key).
        if kind_of(ps) == "document":
            from app.services.document_service import DocumentService

            year, month = params.get("doc_year"), params.get("doc_month")
            content = DocumentService(self.db).render(
                ctx, template_id,
                year=int(year) if year not in (None, "") else None,
                month=int(month) if month not in (None, "") else None,
                record_key=(params.get("doc_record") or None),
            )
            self.audit.log(
                user_id=ctx.acting_user_id,
                action=AuditAction.REPORT_EXPORTED, target_type="template",
                target_id=template_id, detail={"format": "pdf", "kind": "document"},
            )
            return content, "application/pdf"

        # Rule-engine reports are tabular but have no DataSpec/PresentationSpec — render
        # the QueryResult with a default presentation (headers come from the columns).
        if kind_of(ps) == "rule_report":
            result = self.run(ctx, template_id, params, log_fmt=fmt_token)
            title = (ps or {}).get("title") or (ps or {}).get("spec", {}).get("name") or "Report"
            labels = (ps or {}).get("labels") or {}
            from app.domain.report_spec import ColumnPresentation, PivotSpec
            cols = [ColumnPresentation(ref=c, label=labels.get(c) or c.replace("_", " ").title())
                    for c in result.columns]
            branding = self._export_branding(ctx, (ps or {}).get("export_options") or {})
            totals = set((ps or {}).get("totals") or [])
            pivot_cfg = (ps or {}).get("pivot")
            pivot = PivotSpec.model_validate(pivot_cfg) if pivot_cfg else None
            content, mime = render(
                result, PresentationSpec(title=title, columns=cols, branding=branding, pivot=pivot),
                fmt, totals)
            self.audit.log(
                user_id=ctx.acting_user_id,
                action=AuditAction.REPORT_EXPORTED, target_type="template", target_id=template_id,
                detail={"format": fmt.value, "kind": "rule_report", "row_count": result.row_count},
            )
            return content, mime

        resolved = self._resolve_published(ctx, template_id)
        result = self.run(ctx, template_id, params, log_fmt=fmt_token)
        total_labels = _total_labels(resolved.data_spec)
        content, mime = render(result, resolved.presentation_spec, fmt, total_labels)
        self.audit.log(
            user_id=ctx.acting_user_id,
            action=AuditAction.REPORT_EXPORTED,
            target_type="template",
            target_id=template_id,
            detail={"format": fmt.value, "row_count": result.row_count},
        )
        return content, mime
