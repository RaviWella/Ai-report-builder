"""Semantic Layer Service (Architecture §4.3).

Owns the per-tenant catalogue. Responsibilities:
  - resolve the active catalogue for a tenant (latest, or a pinned version)
  - bootstrap a seed catalogue from the ER mapping when none exists
  - introspect the live datamart to PROPOSE entities/fields for enrichment
    (runs only when the read replica is reachable — i.e. via VPN)

Both the AI Adapter and the Query Engine resolve business names through this
service. The AI only ever receives `catalog.metadata_for_ai()`.
"""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.tenancy import TenantContext
from app.db.datamart import get_datamart_engine
from app.db.postgres import get_postgres_database
from app.domain.enums import AggFn, FieldRole, FieldType
from app.domain.semantic import Entity, JoinDef, PhysicalColumn, SemanticCatalog, SemanticField
from app.repositories.semantic_repo import SemanticRepo
from app.repositories.tenant_provision import mark_tenant_provisioned
from app.services.tenant_scope import clear_datamart_key_cache, resolve_datamart_key
from app.tenancy.pg_schema import subdomain_to_pg_schema
from app.services.semantic_seed import build_seed_catalog

log = get_logger(__name__)

# information_schema type -> our FieldType
_PG_TYPE_MAP = {
    "integer": FieldType.INTEGER,
    "bigint": FieldType.INTEGER,
    "smallint": FieldType.INTEGER,
    "numeric": FieldType.DECIMAL,
    "double precision": FieldType.DECIMAL,
    "real": FieldType.DECIMAL,
    "money": FieldType.DECIMAL,
    "boolean": FieldType.BOOLEAN,
    "date": FieldType.DATE,
    "timestamp without time zone": FieldType.DATETIME,
    "timestamp with time zone": FieldType.DATETIME,
}


def _field_refs(catalog: SemanticCatalog) -> set[str]:
    """The set of (ref, type) pairs — used to detect whether a re-introspection
    actually changed anything before bumping the version."""
    return {f"{f.ref}:{f.type.value}" for e in catalog.entities for f in e.fields}


_ACRONYMS = {"Epf": "EPF", "Etf": "ETF", "Apit": "APIT", "Nic": "NIC", "Ot": "OT",
             "Eom": "(EOM)", "Mom": "MoM", "Fte": "FTE", "Ytd": "YTD", "Id": "ID",
             "Pct": "%"}


def _humanize_label(col: str) -> str:
    """attendance_rate_pct -> 'Attendance Rate %'; employee_epf -> 'Employee EPF'."""
    label = col.replace("_", " ").title()
    for word, acr in _ACRONYMS.items():
        label = re.sub(rf"\b{word}\b", acr, label)
    return label.strip()


def _map_dict_type(dtype: str | None) -> FieldType:
    """Map a SQL type to a FieldType. Handles dictionary forms with precision
    (e.g. 'numeric(14,2)', 'varchar(64)') and information_schema's full names."""
    base = (dtype or "").split("(")[0].strip().lower()
    return _PG_TYPE_MAP.get(base, FieldType.STRING)


# Identifiers only — NOT amounts (so 'epf_employee'/'total_bank' stay non-PII).
_PII_HINTS = ("fullname", "full_name", "first_name", "last_name", "nic",
              "passport", "epf_no", "etf_no", "email", "phone", "mobile",
              "address", "date_of_birth", "_dob", "bank_account", "account_no",
              "account_number")


def _looks_pii(col: str) -> bool:
    c = col.lower()
    return any(h in c for h in _PII_HINTS)


def _humanize_payitem(col: str) -> str:
    """addition_blend_allowance -> 'Blend Allowance'; deduction_loan -> 'Loan (Ded.)'."""
    if col.startswith("addition_"):
        return col[len("addition_") :].replace("_", " ").title()
    if col.startswith("deduction_"):
        return col[len("deduction_") :].replace("_", " ").title() + " (Ded.)"
    return col.replace("_", " ").title()


class SemanticService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = SemanticRepo(db)

    def _attach_governed(self, catalog: SemanticCatalog | None) -> SemanticCatalog | None:
        """Load the tenant's governed extras — canonical metrics and the business
        glossary — into the catalogue. They live in their own tables, governed
        separately from the introspected field set."""
        from app.services.glossary_service import load_active_glossary
        from app.services.metrics_service import load_active_metrics

        if catalog is not None:
            catalog.metrics = load_active_metrics(self.db, catalog.tenant_id)
            catalog.glossary = load_active_glossary(self.db, catalog.tenant_id)
        return catalog

    def _seed_governed_defaults(self, tenant_id: str) -> None:
        """On first bootstrap, also seed the default canonical metrics and business
        glossary so the conversational builder's metric/synonym matching works
        out-of-the-box for a freshly-onboarded tenant — no manual seeding step.

        Best-effort and idempotent: seeds skip refs the tenant's datamart lacks
        (e.g. paysheet pay items when the replica is unreachable), and any failure
        is swallowed so it never blocks catalogue bootstrap. Metrics first, then
        glossary (glossary terms may point at the just-seeded metrics)."""
        from app.domain.enums import Role

        ctx = TenantContext(
            tenant_id=tenant_id,
            pg_schema=subdomain_to_pg_schema(tenant_id),
            acting_user_id="system",
            role=Role.SYSTEM,
            on_behalf=True,
        )
        try:
            from app.services.glossary_service import GlossaryService
            from app.services.metrics_service import MetricsService

            metrics = MetricsService(self.db).seed_defaults(ctx)
            terms = GlossaryService(self.db).seed_defaults(ctx)
            log.info(
                "governed_defaults_seeded",
                tenant_id=tenant_id,
                metrics=len(metrics),
                glossary=len(terms),
            )
        except Exception as exc:  # noqa: BLE001 - never block bootstrap on seed failure
            self.db.rollback()
            log.warning("governed_seed_skipped", tenant_id=tenant_id, error=str(exc)[:160])

    def get_active_catalog(self, tenant_id: str) -> SemanticCatalog:
        """Latest catalogue for the tenant. On first use it ZERO-TOUCH bootstraps a
        full catalogue (curated seed + the tenant's own dynamic paysheet pay items)
        so a newly-onboarded SaaS tenant never sees a missing/partial layer."""
        version = self.repo.latest_version()
        if version is None:
            datamart_key = self._datamart_key(tenant_id)
            catalog = self._assemble_catalog(tenant_id, datamart_key, version=1)
            try:
                self.repo.save_new_version(catalog)
                self.db.commit()
            except Exception:  # noqa: BLE001 - lost a race to another first-access; reload
                self.db.rollback()
                v = self.repo.latest_version() or 1
                return self._attach_governed(self.repo.get(v) or catalog)
            log.info("semantic_bootstrapped", tenant_id=tenant_id, entities=len(catalog.entities))
            self._seed_governed_defaults(tenant_id)
            return self._attach_governed(catalog)
        catalog = self.repo.get(version)
        assert catalog is not None
        return self._attach_governed(catalog)

    def _datamart_key(self, tenant_id: str) -> str:
        return resolve_datamart_key(tenant_id)

    def _ensure_tenant(self, tenant_id: str, datamart_key: str) -> None:
        """Ensure platform registry reflects this tenant (datamart_key may differ from subdomain).

        Tenant schema provisioning is handled by PostgresTenantSessionManager on session open;
        this only syncs platform.tenant_provision_status for workers and explicit rebuild paths.
        """
        platform = get_postgres_database().session()
        try:
            platform.execute(text("SET search_path TO platform, public"))
            mark_tenant_provisioned(
                platform,
                tenant_id,
                subdomain_to_pg_schema(tenant_id),
                datamart_key=datamart_key,
                provisioned_by="semantic_service",
            )
            platform.commit()
        finally:
            platform.close()
        # This can persist a new datamart_key — every other worker's cached
        # resolve_datamart_key() must stop serving the old one immediately,
        # not wait out the TTL.
        clear_datamart_key_cache(tenant_id)

    def _assemble_catalog(
        self, tenant_id: str, datamart_key: str, version: int
    ) -> SemanticCatalog:
        """Auto-introspect the datamart's physical `hr` marts + dims into the full
        catalogue (zero `hr_semantic` dependency, self-updating). Fault-tolerant: if
        the datamart is unreachable (e.g. VPN down) it falls back to the offline seed
        so the builder still works."""
        from app.services import semantic_autobuild

        try:
            catalog = semantic_autobuild.build_catalog(tenant_id, datamart_key, version=version)
        except Exception as exc:  # noqa: BLE001 - datamart unreachable -> offline seed
            log.warning("autocatalog_failed_seed_fallback", tenant_id=tenant_id, error=str(exc)[:160])
            catalog = build_seed_catalog(tenant_id, version=version)

        # Learn each low-cardinality dimension's ACTUAL values from the datamart, so
        # the chat resolver's value filters (status, category, …) are catalog-driven
        # rather than reading a hand-coded value list.
        try:
            self._enrich_dimension_values(catalog, datamart_key)
        except Exception as exc:  # noqa: BLE001 - datamart unreachable -> no samples
            log.warning("dimension_values_skipped", tenant_id=tenant_id, error=str(exc))
        return catalog

    def _enrich_dimension_values(
        self, catalog: SemanticCatalog, datamart_key: str, max_cardinality: int = 30
    ) -> None:
        """Populate `sample_values` for every low-cardinality STRING dimension by
        sampling its distinct values from the datamart. A dimension with more than
        `max_cardinality` distinct values (e.g. names) is left unsampled. Each column
        probe runs inside its own savepoint so one bad column never aborts the rest,
        and the whole pass is best-effort — when the datamart is unreachable the
        catalogue simply ships without samples and the resolver falls back to its
        default vocabulary. This is what keeps the chat's value filters per-tenant
        and data-driven (no hand-coded status/category lists)."""
        engine = get_datamart_engine(datamart_key)
        sampled = 0
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            for ent in catalog.entities:
                for f in ent.fields:
                    if f.role != FieldRole.DIMENSION or f.type != FieldType.STRING:
                        continue
                    schema = f.physical.schema_name or ent.base_schema
                    table = f.physical.table or ent.base_table
                    col = f.physical.column
                    if not (schema and table and col):
                        continue
                    sp = conn.begin_nested()
                    try:
                        q = text(
                            f'SELECT DISTINCT "{col}" AS v FROM "{schema}"."{table}" '
                            f'WHERE "{col}" IS NOT NULL LIMIT :lim'
                        )
                        rows = conn.execute(q, {"lim": max_cardinality + 1}).fetchall()
                        sp.commit()
                    except Exception:  # noqa: BLE001 - column/table absent -> skip
                        sp.rollback()
                        continue
                    vals = [str(r.v).strip() for r in rows if str(r.v).strip()]
                    if 0 < len(vals) <= max_cardinality:
                        f.sample_values = sorted(set(vals))
                        sampled += 1
        log.info("dimension_values_enriched", tenant_id=catalog.tenant_id, dimensions=sampled)

    def get_pinned_catalog(self, tenant_id: str, version: int) -> SemanticCatalog:
        """Resolve the EXACT semantic version a report was saved against (SRS §7.3).
        This is what keeps old report versions reproducible after a mapping change.
        """
        catalog = self.repo.get(version)
        if catalog is None:
            raise ValueError(
                f"Pinned semantic version {version} not found for tenant {tenant_id}; "
                "cannot reproduce this report version."
            )
        return self._attach_governed(catalog)

    # ------------------------------------------------------------------ #
    # Live introspection — proposes a catalogue from the datamart schema.
    # Requires datamart reachability (VPN). Result is reviewed/enriched by
    # the tech team before being saved as a new version.
    # ------------------------------------------------------------------ #
    def introspect_datamart(
        self, ctx: TenantContext, datamart_key: str, schemas: tuple[str, ...] = ("hr",)
    ) -> SemanticCatalog:
        engine = get_datamart_engine(datamart_key)
        proposed_entities: dict[str, Entity] = {}

        sql = text(
            """
            SELECT table_schema, table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = ANY(:schemas)
            ORDER BY table_schema, table_name, ordinal_position
            """
        )
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            rows = conn.execute(sql, {"schemas": list(schemas)}).fetchall()

        for schema, table_name, column_name, data_type in rows:
            # Only surface stable consumer objects (views/marts) as entities.
            if not (table_name.startswith(("vw_", "mart_", "dim_"))):
                continue
            entity_key = table_name.replace("vw_", "").replace("mart_", "").replace("dim_", "")
            ent = proposed_entities.get(entity_key)
            if ent is None:
                ent = Entity(
                    name=entity_key.replace("_", " ").title(),
                    key=entity_key,
                    base_schema=schema,
                    base_table=table_name,
                    primary_key=column_name,  # refined during enrichment
                    fields=[],
                )
                proposed_entities[entity_key] = ent
            ftype = _PG_TYPE_MAP.get(data_type, FieldType.STRING)
            role = FieldRole.MEASURE if ftype in (FieldType.DECIMAL, FieldType.INTEGER) else FieldRole.DIMENSION
            ent.fields.append(
                SemanticField(
                    ref=f"{entity_key}.{column_name}",
                    label=column_name.replace("_", " ").title(),
                    type=ftype,
                    role=role,
                    physical=PhysicalColumn(table=table_name, column=column_name, schema_name=schema),
                )
            )

        next_version = (self.repo.latest_version() or 0) + 1
        catalog = SemanticCatalog(
            version=next_version,
            entities=list(proposed_entities.values()),
            joins=[],  # joins are declared manually during enrichment
        )
        log.info(
            "semantic_introspected",
            entities=len(catalog.entities),
            proposed_version=next_version,
        )
        return catalog

    def save_catalog(self, catalog: SemanticCatalog) -> None:
        self.repo.save_new_version(catalog)

    # ------------------------------------------------------------------ #
    # Rebuild: curated seed + auto-introspected dynamic paysheet pay items.
    # The dynamic allowances/deductions vary per tenant, so they MUST be
    # introspected from the tenant's datamart (not hand-coded). Saved as a new
    # semantic version; existing reports stay pinned to their old version.
    # ------------------------------------------------------------------ #
    def rebuild_catalog(self, ctx: TenantContext, datamart_key: str) -> SemanticCatalog:
        """Force a fresh introspection -> a NEW semantic version (admin action)."""
        self._ensure_tenant(ctx.tenant_id, datamart_key)
        next_version = (self.repo.latest_version() or 0) + 1
        catalog = self._assemble_catalog(ctx.tenant_id, datamart_key, version=next_version)
        self.repo.save_new_version(catalog)
        log.info(
            "semantic_rebuilt", version=next_version,
            entities=len(catalog.entities),
        )
        return catalog

    def refresh_if_changed(self, tenant_id: str, datamart_key: str) -> int | None:
        """Re-introspect and bump the version ONLY if the field set changed (used by
        the nightly job). Returns the new version, or None if nothing changed —
        avoids accumulating identical versions. Reports stay pinned regardless."""
        self._ensure_tenant(tenant_id, datamart_key)
        current_version = self.repo.latest_version()
        current = self.repo.get(current_version) if current_version else None
        candidate = self._assemble_catalog(tenant_id, datamart_key, version=(current_version or 0) + 1)

        if current is not None and _field_refs(current) == _field_refs(candidate):
            return None
        self.repo.save_new_version(candidate)
        log.info("semantic_refreshed", tenant_id=tenant_id, version=candidate.version)
        return candidate.version

    _PAYSHEET_TABLE = "mart_horizontal_paysheet_dynamic"

    def _column_meta(self, engine, core: str, table: str) -> list[tuple]:  # noqa: ANN001
        """Column metadata for ANY datamart table, PREFERRING the governed
        `vw_data_dictionary` (business descriptions + authoritative PII flags).
        Falls back to information_schema if the dictionary view is absent.
        Returns (column, data_type, description|None, pii)."""
        # Qualify with the semantic schema — a raw engine.connect() does NOT set
        # the tenant search_path. `sem` comes from settings, not user input.
        sem = settings.datamart_schema_semantic
        dict_sql = text(
            f"""
            SELECT field_name AS col, data_type AS dtype,
                   NULLIF(TRIM(COALESCE(description, '')), 'TBD') AS descr,
                   COALESCE(pii, false) AS pii
            FROM "{sem}".vw_data_dictionary
            WHERE object_name = :tbl
            ORDER BY ordinal_position
            """
        )
        try:
            with engine.connect() as conn:
                rows = conn.execute(dict_sql, {"tbl": table}).fetchall()
            if rows:
                return [(r.col, r.dtype, r.descr, bool(r.pii)) for r in rows]
        except Exception as exc:  # noqa: BLE001 - dictionary missing -> fall back
            log.warning("data_dictionary_unavailable", error=str(exc))

        info_sql = text(
            """
            SELECT column_name AS col, data_type AS dtype
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :tbl
            ORDER BY ordinal_position
            """
        )
        with engine.connect() as conn:
            rows = conn.execute(info_sql, {"schema": core, "tbl": table}).fetchall()
        return [(r.col, r.dtype, None, False) for r in rows]

    def _paysheet_columns(self, engine, core: str) -> list[tuple]:  # noqa: ANN001
        return self._column_meta(engine, core, self._PAYSHEET_TABLE)

    # Conformed summary marts to expose as standalone entities (their dimensions
    # are embedded, so no joins are needed). Add a mart here and EVERY tenant that
    # has it gets a self-service reporting entity on the next rebuild.
    # NB: attendance / leave / salary-bands / headcount / turnover are already
    # curated in the SEED (via vw_ views) — only list marts NOT covered there, to
    # avoid duplicate entities.
    _SUMMARY_MARTS = [
        ("mart_statutory_summary", "Statutory Summary", "statutory_summary"),
    ]
    # Columns to never surface (surrogate keys / load bookkeeping).
    _SKIP_COLS = ("tenant_id", "source_system", "_refreshed_at", "_loaded_at",
                  "_source_updated_at")
    # Numeric columns that are really dimensions, not measures.
    _DIM_NUMERIC = ("year", "month", "month_number", "payroll_year", "payroll_month",
                    "payroll_half")

    def _introspect_summary_marts(self, datamart_key: str) -> list[Entity]:
        """Auto-build a standalone entity for each conformed summary mart present
        in this tenant's datamart."""
        engine = get_datamart_engine(datamart_key)
        core = settings.datamart_schema_core
        entities: list[Entity] = []
        for table, name, key in self._SUMMARY_MARTS:
            cols = self._column_meta(engine, core, table)
            if not cols:
                continue
            fields: list[SemanticField] = []
            pk = None
            for col, dt, descr, pii in cols:
                lc = col.lower()
                if lc.endswith("_sk") and pk is None:
                    pk = col  # use a surrogate key as the entity PK
                if col in self._SKIP_COLS or lc.endswith("_sk"):
                    continue
                ftype = _map_dict_type(dt)
                numeric = ftype in (FieldType.DECIMAL, FieldType.INTEGER)
                role = (
                    FieldRole.MEASURE
                    if numeric and lc not in self._DIM_NUMERIC
                    else FieldRole.DIMENSION
                )
                fields.append(
                    SemanticField(
                        ref=f"{key}.{col}", label=_humanize_label(col),
                        description=descr, type=ftype, role=role,
                        physical=PhysicalColumn(table=table, column=col, schema_name=core),
                        allowed_aggregations=[AggFn.SUM, AggFn.AVG, AggFn.MIN, AggFn.MAX]
                        if role == FieldRole.MEASURE else [],
                        pii=bool(pii) or _looks_pii(col),
                    )
                )
            if fields:
                entities.append(
                    Entity(name=name, key=key, base_schema=core, base_table=table,
                           primary_key=pk or fields[0].physical.column, fields=fields)
                )
        return entities

    def _introspect_paysheet(self, datamart_key: str) -> Entity | None:
        """Build a 'Paysheet' entity from mart_horizontal_paysheet_dynamic — the
        wide, per-tenant pivot of every pay item (additions + deductions). Field
        metadata comes from the data dictionary when available."""
        engine = get_datamart_engine(datamart_key)
        core = settings.datamart_schema_core
        rows = self._paysheet_columns(engine, core)
        if not rows:
            return None

        skip = {"tenant_id", "employee_sk", "payroll_period_sk", "_refreshed_at",
                "branch", "payroll_half"}
        dims_int = {"payroll_year", "payroll_month"}

        fields: list[SemanticField] = []
        for col, dt, descr, pii in rows:
            if col in skip:
                continue
            ftype = _map_dict_type(dt)
            numeric = ftype in (FieldType.DECIMAL, FieldType.INTEGER)
            role = (
                FieldRole.MEASURE if (numeric and col not in dims_int) else FieldRole.DIMENSION
            )
            fields.append(
                SemanticField(
                    ref=f"paysheet.{col}",
                    label=_humanize_payitem(col),
                    description=descr,
                    type=ftype,
                    role=role,
                    physical=PhysicalColumn(table=self._PAYSHEET_TABLE, column=col, schema_name=core),
                    allowed_aggregations=[AggFn.SUM, AggFn.AVG, AggFn.MIN, AggFn.MAX] if role == FieldRole.MEASURE else [],
                    # Trust the dictionary's PII flag, but err on the side of privacy
                    # for obvious identifiers (a name/NIC is PII even if unflagged).
                    pii=bool(pii) or _looks_pii(col),
                )
            )
        return Entity(
            name="Paysheet",
            key="paysheet",
            base_schema=core,
            base_table="mart_horizontal_paysheet_dynamic",
            primary_key="employee_sk",
            description="Wide paysheet — every pay item (additions + deductions) per employee × period.",
            fields=fields,
        )

    def _tables_exist(self, engine, schema: str, tables: list[str]) -> bool:  # noqa: ANN001
        sql = text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = :s AND table_name = ANY(:t)"
        )
        with engine.connect() as conn:
            n = conn.execute(sql, {"s": schema, "t": tables}).scalar() or 0
        return n >= len(tables)

    def _transaction_entities(self, datamart_key: str) -> tuple[list[Entity], list[JoinDef]]:
        """Long, pre-aggregated pay-item summary (mart_dynamic_pay_items: one row
        per pay item per period — total amount + how many employees got it) plus
        the period dimension. This powers a 'Grand Summary' style report:
        Transaction Name | Amount | Number of Employees, filtered by period.
        Returns ([], []) if the marts aren't present for this tenant."""
        engine = get_datamart_engine(datamart_key)
        core = settings.datamart_schema_core
        if not self._tables_exist(engine, core, ["mart_dynamic_pay_items", "dim_payroll_period"]):
            return [], []

        def pc(table: str, column: str) -> PhysicalColumn:
            return PhysicalColumn(table=table, column=column, schema_name=core)

        sums = [AggFn.SUM, AggFn.AVG, AggFn.MIN, AggFn.MAX]
        payitem = Entity(
            name="Pay Item Summary", key="payitem",
            base_schema=core, base_table="mart_dynamic_pay_items",
            primary_key="canonical_pay_item_sk",
            description="One row per pay item per period — total amount and the number of "
                        "employees who received it (a Grand-Summary source).",
            fields=[
                SemanticField(ref="payitem.transaction_name", label="Transaction Name",
                              type=FieldType.STRING, role=FieldRole.DIMENSION,
                              physical=pc("mart_dynamic_pay_items", "variable_item_name")),
                SemanticField(ref="payitem.amount", label="Amount",
                              type=FieldType.DECIMAL, role=FieldRole.MEASURE,
                              physical=pc("mart_dynamic_pay_items", "total_amount"),
                              allowed_aggregations=sums),
                SemanticField(ref="payitem.employees", label="Number of Employees",
                              type=FieldType.INTEGER, role=FieldRole.MEASURE,
                              physical=pc("mart_dynamic_pay_items", "employee_count"),
                              allowed_aggregations=[AggFn.SUM, AggFn.MAX]),
                SemanticField(ref="payitem.avg_amount", label="Average Amount",
                              type=FieldType.DECIMAL, role=FieldRole.MEASURE,
                              physical=pc("mart_dynamic_pay_items", "avg_amount"),
                              allowed_aggregations=sums),
            ],
        )
        period = Entity(
            name="Payroll Period", key="payroll_period",
            base_schema=core, base_table="dim_payroll_period",
            primary_key="payroll_period_sk",
            description="Payroll periods — year, month and the cut-off start/end dates.",
            fields=[
                SemanticField(ref="payroll_period.year", label="Payroll Year",
                              type=FieldType.INTEGER, role=FieldRole.DIMENSION,
                              physical=pc("dim_payroll_period", "payroll_year")),
                SemanticField(ref="payroll_period.month", label="Payroll Month",
                              type=FieldType.INTEGER, role=FieldRole.DIMENSION,
                              physical=pc("dim_payroll_period", "payroll_month")),
                SemanticField(ref="payroll_period.start", label="Period Start",
                              type=FieldType.DATE, role=FieldRole.DIMENSION,
                              physical=pc("dim_payroll_period", "period_start_date")),
                SemanticField(ref="payroll_period.end", label="Period End",
                              type=FieldType.DATE, role=FieldRole.DIMENSION,
                              physical=pc("dim_payroll_period", "period_end_date")),
            ],
        )
        join = JoinDef(
            left_entity="Pay Item Summary", right_entity="Payroll Period",
            left_key="payroll_period_sk", right_key="payroll_period_sk", join_type="left",
        )
        return [payitem, period], [join]
