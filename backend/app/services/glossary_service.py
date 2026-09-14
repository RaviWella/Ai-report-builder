"""Business glossary tier — governed business-term definitions on top of the
catalogue (and the metrics layer).

A glossary term is the single authoritative definition of a business word
("Take-home Pay", "Attrition"), and points at the governed `ref` that computes it
(a `metric.<key>` or a field). Defining one VALIDATES that its `ref` resolves
against the live catalogue (a typo'd ref is rejected up front), then stores it per
tenant. The deterministic NL resolver loads these as synonyms so business language
maps onto governed refs; the builder UI shows the definition.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.db.metadata import SemanticGlossary
from app.domain.enums import AuditAction
from app.domain.semantic import GlossaryTerm, SemanticCatalog
from app.services.audit_service import AuditService
from app.services.semantic_service import SemanticService


def load_active_glossary(db: Session, tenant_id: str) -> list[GlossaryTerm]:
    """The tenant's current glossary (standalone so SemanticService can load it into
    a catalogue without importing the glossary service)."""
    rows = db.execute(
        select(SemanticGlossary).where(
            SemanticGlossary.active.is_(True)
        )
    ).scalars().all()
    return [GlossaryTerm.model_validate(r.definition) for r in rows]


# Default HR/payroll vocabulary proposed on seeding — only terms whose `ref`
# resolves in this tenant's catalogue are kept (best-effort, idempotent).
_SEED_TERMS = [
    GlossaryTerm(
        term="Take-home Pay", ref="metric.total_net", category="payroll", source="seed",
        aliases=["net pay", "net salary", "in-hand salary", "take home pay"],
        definition="The net amount an employee actually receives after all "
                   "deductions (EPF, tax, loans) are subtracted from gross pay.",
    ),
    GlossaryTerm(
        term="Headcount", ref="metric.headcount", category="workforce", source="seed",
        aliases=["staff count", "number of employees", "employee count"],
        definition="The number of active employees at a given point in time.",
    ),
    GlossaryTerm(
        term="Gross Pay", ref="metric.total_gross", category="payroll", source="seed",
        aliases=["gross salary", "total earnings"],
        definition="Total earnings before any deductions are applied.",
    ),
    GlossaryTerm(
        term="Deductions", ref="metric.total_deductions", category="payroll", source="seed",
        aliases=["total deductions", "withholdings"],
        definition="The total amount withheld from gross pay (EPF, tax, loans, "
                   "advances) before arriving at take-home pay.",
    ),
]


class GlossaryService:
    def __init__(self, db: Session):
        self.db = db
        self.semantic = SemanticService(db)
        self.audit = AuditService(db)

    def list(self, ctx: TenantContext) -> list[GlossaryTerm]:
        return load_active_glossary(self.db, ctx.tenant_id)

    def define(self, ctx: TenantContext, term: GlossaryTerm) -> GlossaryTerm:
        """Validate the term's `ref` resolves against the live catalogue, then store
        it (superseding any prior definition of the same term). Raises ValueError for
        an invalid definition."""
        if not term.term.strip():
            raise ValueError("A glossary term needs a name.")
        if not term.definition.strip():
            raise ValueError("A glossary term needs a definition.")
        self._assert_ref_resolves(ctx, term)

        key = term.key()
        for row in self.db.execute(
            select(SemanticGlossary).where(
                SemanticGlossary.term_key == key, SemanticGlossary.active.is_(True),
            )
        ).scalars():
            row.active = False
        self.db.add(SemanticGlossary(
            term_key=key,
            definition=term.model_dump(mode="json"), created_by=ctx.acting_user_id,
        ))
        self.db.commit()
        self.audit.log(
            user_id=ctx.acting_user_id, action=AuditAction.AI_INTERACTION,
            detail={"mode": "glossary_define", "term": term.term, "ref": term.ref},
        )
        return term

    def learn_alias(self, ctx: TenantContext, ref: str, alias: str) -> None:
        """Promote a confirmed column-header correction into the glossary: attach
        `alias` (the spreadsheet heading the user mapped) as a synonym of the term
        for `ref`, so tenant-wide FUZZY matching improves — not just exact-header
        replay. Creates a lightweight 'learned' term if the field has none yet.

        Governed and idempotent: only real field refs are promoted, aliases are
        de-duplicated, and learned terms carry source='learned' so an admin can see
        and curate them on the Glossary page. Best-effort — never raises into the
        upload path."""
        alias = (alias or "").strip()
        if not alias or not ref or ref.startswith("metric."):
            return
        try:
            catalog: SemanticCatalog = self.semantic.get_active_catalog(ctx.tenant_id)
            field = catalog.field_index().get(ref)
            if field is None:  # ref no longer in the catalogue — nothing to ground
                return
            norm = alias.lower()
            existing = next((t for t in self.list(ctx) if t.ref == ref), None)
            if existing is not None:
                if norm == existing.term.lower() or norm in {a.lower() for a in existing.aliases}:
                    return  # already covered — no-op
                self.define(ctx, existing.model_copy(update={"aliases": [*existing.aliases, alias]}))
            else:
                self.define(ctx, GlossaryTerm(
                    term=field.label, ref=ref, category="learned", source="learned",
                    aliases=[alias],
                    definition=f"Spreadsheet column headings that map to {field.label}.",
                ))
        except Exception:  # noqa: BLE001 - promotion must never break the upload
            self.db.rollback()

    def seed_defaults(self, ctx: TenantContext) -> list[GlossaryTerm]:
        """Create the default terms whose `ref` resolves in this tenant's catalogue
        and aren't already defined. Best-effort, idempotent."""
        existing = {t.key() for t in self.list(ctx)}
        created: list[GlossaryTerm] = []
        for cand in _SEED_TERMS:
            if cand.key() in existing:
                continue
            try:
                created.append(self.define(ctx, cand))
            except ValueError:
                continue  # ref doesn't resolve for this tenant — skip
        return created

    def _assert_ref_resolves(self, ctx: TenantContext, term: GlossaryTerm) -> None:
        """A term may be purely documentary (no ref). If it has one, it must point at
        a real governed metric or field — otherwise the resolver would map business
        language onto a dangling ref."""
        if not term.ref:
            return
        catalog: SemanticCatalog = self.semantic.get_active_catalog(ctx.tenant_id)
        if term.ref.startswith("metric."):
            if term.ref.split(".", 1)[1] not in catalog.metric_index():
                raise ValueError(f"Unknown metric ref {term.ref!r}; define the metric first.")
        elif term.ref not in catalog.field_index():
            raise ValueError(f"Unknown field ref {term.ref!r}.")
