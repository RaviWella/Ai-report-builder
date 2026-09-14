"""AI router — the three metadata-only build-time tasks (SRS §5.2, §8).

Chat and Excel are equal, interleavable input modes in one session (FR-A5). All
endpoints converge on the same DataSpec (FR-A7). The AI never returns SQL and
never receives PII — Excel rows are stripped in ingestion before any AI call.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.security import BuilderRoles, require_roles
from app.core.tenancy import TenantContext, get_tenant_context
from app.services.ai_service import AIService
from app.services.chat_history import ChatHistoryService

router = APIRouter(
    prefix="/ai", tags=["ai"], dependencies=[Depends(require_roles(*BuilderRoles))]
)


class NLBody(BaseModel):
    request: str


class AdjustBody(BaseModel):
    instruction: str
    current_spec: dict


class ChatBody(BaseModel):
    message: str
    current_spec: dict | None = None
    # The result currently on screen ({columns, rows, prompt}) — lets the chat answer
    # follow-up questions about it ("what's the total of above?").
    context: dict | None = None


class DeriveFieldBody(BaseModel):
    description: str  # plain-language or rough formula; AI -> structured spec
    label: str | None = None  # column heading (e.g. the unmatched Excel column)


@router.post("/natural-language")
def natural_language(
    body: NLBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        proposal = AIService(db).from_natural_language(ctx, body.request)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"AI produced an invalid spec: {exc}") from exc
    return {
        "data_spec": proposal.data_spec.model_dump(mode="json"),
        "rationale": proposal.rationale,
        "source": proposal.source,  # WS-2: "deterministic" | "llm"
    }


@router.post("/chat")
def chat(
    body: ChatBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Conversational turn for the chat report builder. Always returns 200 with
    either a report (kind="report" + data_spec) or a conversational reply
    (kind="reply") — greetings, help, off-topic, or a graceful failure."""
    res = AIService(db).chat(ctx, body.message, body.current_spec, body.context)
    return {
        "kind": res.kind,
        "message": res.message,
        "data_spec": res.data_spec.model_dump(mode="json") if res.data_spec else None,
        "source": res.source,
        "mapping": res.mapping,
        "options": res.options,
        "gaps": res.gaps,
    }


# ── Chat history (ChatGPT-style sessions; results are immutable snapshots) ──
class SessionCreate(BaseModel):
    title: str | None = None


class AppendBody(BaseModel):
    messages: list[dict]
    working_data_spec: dict | None = None


class RenameBody(BaseModel):
    title: str


@router.post("/sessions")
def create_session(
    body: SessionCreate,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    return ChatHistoryService(db).create(ctx, body.title)


@router.get("/sessions")
def list_sessions(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    return {"sessions": ChatHistoryService(db).list(ctx)}


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    s = ChatHistoryService(db).get(ctx, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return s


@router.post("/sessions/{session_id}/messages")
def append_messages(
    session_id: str,
    body: AppendBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    s = ChatHistoryService(db).append(ctx, session_id, body.messages, body.working_data_spec)
    if s is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return s


@router.patch("/sessions/{session_id}")
def rename_session(
    session_id: str,
    body: RenameBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    s = ChatHistoryService(db).rename(ctx, session_id, body.title)
    if s is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return s


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    if not ChatHistoryService(db).delete(ctx, session_id):
        raise HTTPException(status_code=404, detail="Chat session not found")
    return {"deleted": True}


@router.post("/adjust")
def adjust(
    body: AdjustBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    try:
        proposal = AIService(db).adjust(ctx, body.instruction, body.current_spec)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"AI produced an invalid spec: {exc}") from exc
    return {"data_spec": proposal.data_spec.model_dump(mode="json"), "rationale": proposal.rationale}


@router.post("/derive-field")
def derive_field(
    body: DeriveFieldBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Plain-language / rough-formula -> a governed custom field (formula or
    banding). No SQL is produced; the result compiles deterministically."""
    try:
        calc = AIService(db).derive_field(ctx, body.description, body.label)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"Couldn’t build that field: {exc}") from exc
    return {"calculated_field": calc.model_dump(mode="json")}


@router.post("/excel-mapping")
async def excel_mapping(
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Upload a sample sheet (any point in a session). Rows are stripped LOCALLY
    before the AI sees only headers + inferred types (FR-A1/FR-A2). Human confirms
    each mapping in the UI."""
    content = await file.read()
    try:
        proposal = AIService(db).map_excel(
            ctx, content, filename=file.filename or "", content_type=file.content_type or ""
        )
    except (ValueError, ImportError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse upload: {exc}") from exc
    except Exception as exc:
        # pandas/xlrd parse failures should surface as a readable 400, not a 500.
        raise HTTPException(status_code=400, detail=f"Could not parse upload: {exc}") from exc
    return {
        "mappings": proposal.mappings,
        "rationale": proposal.rationale,
        "columns_seen": proposal.columns_seen,
        "note": "Data rows were stripped locally; only headers + inferred types were sent to the AI.",
    }


class DiscoverBody(BaseModel):
    term: str             # a concept / unmatched heading to locate across layers


@router.post("/discover")
def discover_in_source(
    body: DiscoverBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Drill down the datamart layers (marts → facts/dims → staging) to LOCATE a
    concept that isn't in a report mart, and explain how to surface it. Metadata-
    only and read-only — never guesses a join, so it can't produce wrong data."""
    from app.services.source_discovery import SourceDiscoveryService

    from app.services.tenant_scope import resolve_datamart_key
    datamart_key = resolve_datamart_key(ctx.tenant_id)
    return SourceDiscoveryService().discover(datamart_key, body.term)


class ExplainGapsBody(BaseModel):
    terms: list[str]      # unmatched headings to explain in business language


@router.post("/explain-gaps")
def explain_gaps(
    body: ExplainGapsBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Business-language explanation for headings that didn't map to a report field —
    is each collected in the source but not in reports (requestable), or not captured?
    Same drill-down the chat uses, so the Excel flow explains gaps identically."""
    from app.services.source_discovery import SourceDiscoveryService

    from app.services.tenant_scope import resolve_datamart_key
    datamart_key = resolve_datamart_key(ctx.tenant_id)
    return {"gaps": SourceDiscoveryService().explain_gaps(datamart_key, body.terms[:40])}


@router.get("/source-columns")
def source_columns(source: str, ctx: TenantContext = Depends(get_tenant_context)) -> dict:
    """Physical columns (name + type) of one `schema.table` source string — a
    RuleReportSpec's `source`. Powers the Rule Report builder's Filters/
    Add-column pickers so a single-source spec gets the same 'pick from a
    list, don't type blind' UX the Excel Upload panel's field picker already
    has, reusing the AI chat's own `list_columns` introspection query."""
    from app.services.ai_datamart_tools import _validate_schema_table, query_table_columns
    from app.services.tenant_scope import resolve_datamart_key

    schema, _sep, table = source.partition(".")
    bad = _validate_schema_table(schema, table)
    if bad:
        raise HTTPException(status_code=400, detail=bad)
    try:
        cols = query_table_columns(ctx, resolve_datamart_key(ctx.tenant_id), schema, table)
    except Exception as exc:  # noqa: BLE001 - a live datamart read; surface as a clean 502
        raise HTTPException(status_code=502, detail=f"Could not read {source}: {exc}") from exc
    return {"columns": cols}


class SuggestFieldsBody(BaseModel):
    header: str           # the unmatched spreadsheet heading
    limit: int = 3


@router.post("/suggest-fields")
def suggest_fields(
    body: SuggestFieldsBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Rank the best candidate fields for a column that didn't auto-map, so the user
    picks from a short list. Deterministic shortlist; AI only for the ambiguous tail."""
    limit = max(1, min(body.limit, 8))
    return {"suggestions": AIService(db).suggest_fields(ctx, body.header, limit=limit)}


class ColumnMappingBody(BaseModel):
    header: str            # the spreadsheet heading, verbatim
    ref: str | None = None  # the field the user confirmed/corrected to (None = skip)


@router.post("/column-mappings")
def remember_column_mapping(
    body: ColumnMappingBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Remember a header → field mapping the user confirmed or corrected, so the
    next upload of a sheet with the same heading auto-maps correctly. `ref=None`
    remembers a deliberate skip."""
    from app.services.column_mapping_store import ColumnMappingStore

    ColumnMappingStore(db).remember(ctx.tenant_id, body.header, body.ref, user_id=ctx.acting_user_id)
    # Layer 1 — promote the correction into the glossary so a *similar* header
    # fuzzy-matches next time, tenant-wide (not just this exact heading).
    if body.ref:
        from app.services.glossary_service import GlossaryService

        GlossaryService(db).learn_alias(ctx, body.ref, body.header)
    return {"remembered": body.header, "ref": body.ref}


@router.get("/column-mappings")
def list_column_mappings(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """All remembered header → field mappings for this tenant (governance view)."""
    from app.services.column_mapping_store import ColumnMappingStore

    return {"mappings": ColumnMappingStore(db).list(ctx.tenant_id)}


@router.delete("/column-mappings/{mapping_id}")
def delete_column_mapping(
    mapping_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Forget a remembered mapping so the header is guessed fresh next time."""
    from app.services.column_mapping_store import ColumnMappingStore

    ok = ColumnMappingStore(db).delete_by_id(ctx.tenant_id, mapping_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return {"deleted": mapping_id}
