"""
Datamart AI Service — Pydantic Models
=======================================
Request and response schemas shared between the agent and the API route.
"""
import re
from enum import Enum
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .pipeline_trace import PipelineTrace
from .validation.validation_models import DatamartValidation, RetrievalValidation, SchemaLink


_COL_NAME_PATTERN = re.compile(r"^[\w][\w .%\-/]{0,254}$", re.UNICODE)


# ── Chat request ──────────────────────────────────────────────────

class DatamartChartConfigV1(BaseModel):
    """
    Declarative chart binding (v1). Serialized to JSONB; rendered with Recharts on the client.

    ``data_source``:
      - ``final``: columns/rows after post-processing (or raw SQL rows if no post-process).
      - ``sql_raw``: use pre-post-process snapshot when available; otherwise same as final.

    ``result_block_id``:
      - ``None``: chart uses the primary SQL result for this message.
      - Non-empty: must match ``block_id`` of an entry in the message's ``extra_result_blocks``.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    id: UUID
    chart_type: Literal["bar", "column", "pie", "line"]
    title: Optional[str] = Field(default=None, max_length=200)
    data_source: Literal["final", "sql_raw"] = "final"
    result_block_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="When set, bind this chart to that extra result block's dataset.",
    )
    row_scope: Literal["all", "sql_detail_only", "append_summaries_only"] = Field(
        default="all",
        description="Row slice for charting when post-process appends summary rows.",
    )
    category_column: str = Field(..., min_length=1, max_length=256)
    value_column: str = Field(..., min_length=1, max_length=256)
    show_legend: bool = True
    sort_order: Optional[
        Literal[
            "original",
            "value_desc",
            "value_asc",
            "category_asc",
            "category_desc",
        ]
    ] = Field(
        default=None,
        description="Row order for column/bar/line charts before rendering.",
    )

    @field_validator("category_column", "value_column")
    @classmethod
    def _valid_sql_column_alias(cls, v: str) -> str:
        v = v.strip()
        if not _COL_NAME_PATTERN.match(v):
            raise ValueError(
                f"Invalid column name {v!r}: use letters, numbers, spaces, or common punctuation."
            )
        return v


class PutMessageChartsRequest(BaseModel):
    """Replace all charts attached to an assistant message (empty list clears)."""

    charts: list[DatamartChartConfigV1] = Field(default_factory=list, max_length=24)


class PutMessageChartsResponse(BaseModel):
    message_id: str
    chart_configs: list[dict[str, Any]]


class PatchMessageReportMetaRequest(BaseModel):
    """Update scenario labels and/or canvas layout on an assistant message."""

    report_layout: Optional[dict[str, Any]] = Field(
        default=None,
        description="Full or partial report_layout v1 object (merged server-side).",
    )
    primary_label: Optional[str] = Field(default=None, max_length=200)
    block_labels: Optional[dict[str, str]] = Field(
        default=None,
        description="Map of extra_result_blocks block_id → display title.",
    )


class PatchMessageReportMetaResponse(BaseModel):
    message_id: str
    report_layout: Optional[dict[str, Any]] = None
    extra_result_blocks: Optional[list[dict[str, Any]]] = None


class PatchTemplateVersionReportMetaRequest(BaseModel):
    """Update scenario labels and/or canvas layout on a template version."""

    report_layout: Optional[dict[str, Any]] = Field(
        default=None,
        description="Full or partial report_layout v1 object (merged server-side).",
    )
    primary_label: Optional[str] = Field(default=None, max_length=200)
    block_labels: Optional[dict[str, str]] = Field(
        default=None,
        description="Map of extra_result_blocks block_id → display title.",
    )


class PatchTemplateVersionReportMetaResponse(BaseModel):
    version_id: str
    report_layout: Optional[dict[str, Any]] = None
    extra_result_blocks: Optional[list[dict[str, Any]]] = None


class ExecuteSqlOverrideRequest(BaseModel):
    """Optional body for re-execute endpoints — run different SQL without persisting."""

    sql: Optional[str] = Field(
        default=None,
        max_length=100_000,
        description="When set, run this SQL instead of the stored script (message is not updated).",
    )


class FollowUpMode(str, Enum):
    """How the next user message relates to the prior assistant turn in a session."""

    CONTINUE_LAST = "continue_last"
    """Modify or extend the previous result (refine SQL / post-process / analytical follow-up)."""
    ADD_SCENARIO = "add_scenario"
    """Unrelated follow-up: keep prior scenario(s), add a new SQL dataset in the same report."""
    NEW_QUESTION = "new_question"
    """Standalone question — fresh schema discovery and SQL, not an edit of the last query."""
    CLARIFY_REPLY = "clarify_reply"
    """Answer to the assistant's clarification — merges with the prior question and re-runs validation."""


class DatamartChatRequest(BaseModel):
    """Incoming chat request from the frontend."""

    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(
        default=None,
        description="UUID of the active session. If None, a new session is created.",
    )
    edit_from_turn_index: Optional[int] = Field(
        default=None,
        ge=1,
        description=(
            "When set, delete this turn and all later turns in the session, "
            "then append the new question as a replacement (ChatGPT-style edit & resend)."
        ),
    )
    follow_up_mode: Optional[FollowUpMode] = Field(
        default=None,
        description=(
            "When the session already has a prior assistant reply: continue_last applies "
            "changes to that result; new_question runs a fresh query; clarify_reply merges "
            "with the prior question after an assistant clarification turn. Omit for legacy "
            "auto-classification (treats most follow-ups as refinements when prior SQL exists)."
        ),
    )
    target_scenario_ids: Optional[list[str]] = Field(
        default=None,
        max_length=32,
        description=(
            "When follow_up_mode is continue_last and the report has multiple scenarios: "
            "panel ids to modify — use 'primary' for the main SQL and block_id values for extras. "
            "Omit when only one scenario exists."
        ),
    )
    confirmed_tables: Optional[list[str]] = Field(
        default=None,
        max_length=32,
        description=(
            "Optional table short names confirmed by the user after grounding preview. "
            "When set, schema broker limits discovery to these tables (plus join partners)."
        ),
    )
    # Legacy field kept for backward compatibility (non-session mode)
    history: list[dict[str, str]] = Field(default_factory=list)


# ── Chat response ─────────────────────────────────────────────────

class DatamartResultBlock(BaseModel):
    """
    One additional SQL dataset in the same assistant turn as the primary ``sql``.

    Stored metadata (without rows) lives in ``datamart_chat_messages.extra_result_blocks``;
    the API returns full blocks on fresh turns and re-hydrates via the block execute endpoint.
    """

    model_config = ConfigDict(extra="ignore")

    block_id: str = Field(..., min_length=4, max_length=64)
    title: Optional[str] = Field(default=None, max_length=200)
    narrative: str = ""
    sql: Optional[str] = None
    post_process_config: Optional[list[dict[str, Any]]] = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    raw_columns: Optional[list[str]] = None
    raw_rows: Optional[list[list[Any]]] = None
    raw_row_count: Optional[int] = None
    error: Optional[str] = None
    validation: Optional[dict[str, Any]] = Field(
        default=None,
        description="Per-block generation validation snapshot (overall trust for this scenario).",
    )
    pipeline_trace: Optional[PipelineTrace] = Field(
        default=None,
        description="Agent pathway for this scenario only (add-scenario turns).",
    )


class GroundingPreviewRequest(BaseModel):
    """Preview retrieval grounding without running the LLM."""

    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    follow_up_mode: Optional[FollowUpMode] = None
    confirmed_tables: Optional[list[str]] = Field(default=None, max_length=32)


class PipelineTurnMeta(BaseModel):
    """S5 respond metadata: domain, tier, and sources for one chat turn."""

    model_config = ConfigDict(extra="forbid")

    domain: Optional[str] = Field(
        default=None,
        description="Classified business domain (payroll, recruitment, …).",
    )
    sql_tier: Optional[Literal["A", "B", "C"]] = Field(
        default=None,
        description="SQL resolution tier: A=template, B=verified, C=LLM.",
    )
    sql_source: Optional[str] = Field(
        default=None,
        description="Resolver source tag (e.g. recruitment_pipeline_template, verified:id).",
    )
    tables_linked: list[str] = Field(
        default_factory=list,
        description="Short table names from schema link (capped for UI).",
    )


class GroundingPreviewResponse(BaseModel):
    """Retrieval validation and grounded table list for UI confirm step."""

    question: str
    retrieval: RetrievalValidation
    tables_selected: list[str] = Field(default_factory=list)
    schema_links: list[SchemaLink] = Field(default_factory=list)
    can_proceed: bool = True
    prompt_preview_chars: int = 0


class DatamartResponse(BaseModel):
    """Structured response returned by the agent."""

    question: str
    narrative: str = ""
    sql: Optional[str] = None
    post_process_config: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description=(
            "Optional post-processing steps applied to the SQL result. "
            "Stored verbatim so historical results are always reproducible."
        ),
    )
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    raw_columns: Optional[list[str]] = Field(
        default=None,
        description="SQL result columns before post-processing (when post_process_config ran).",
    )
    raw_rows: Optional[list[list[Any]]] = Field(
        default=None,
        description="SQL result rows before post-processing.",
    )
    raw_row_count: Optional[int] = Field(
        default=None,
        description="Row count before post-processing.",
    )
    error: Optional[str] = None
    session_id: Optional[str] = None
    message_id: Optional[str] = Field(
        default=None,
        description="UUID of the persisted assistant message. Used by the frontend to promote to template.",
    )
    turn_index: Optional[int] = Field(
        default=None,
        description="1-based conversation turn index for this user/assistant pair.",
    )
    chart_configs: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Charts saved on this assistant message (same schema as PutMessageChartsRequest).",
    )
    extra_result_blocks: Optional[list[DatamartResultBlock]] = Field(
        default=None,
        description="Additional independent SELECT pipelines in the same reply.",
    )
    report_layout: Optional[dict[str, Any]] = Field(
        default=None,
        description="Canvas layout and scenario labels for this assistant turn.",
    )
    validation: Optional[DatamartValidation] = Field(
        default=None,
        description="Retrieval and generation validation metadata (trust badge, sources, warnings).",
    )
    pipeline_trace: Optional[PipelineTrace] = Field(
        default=None,
        description="Ordered agent steps (grounding → retrieval → SQL → validate → execute) for UI.",
    )
    pipeline_meta: Optional[PipelineTurnMeta] = Field(
        default=None,
        description="Domain, SQL tier, and source summary for the turn (S5 respond).",
    )


# ── Session schemas ───────────────────────────────────────────────

class SessionCreateRequest(BaseModel):
    title: str = Field(default="New conversation", max_length=255)


class SessionRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class SessionListItem(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    group_id: Optional[str] = None


class SessionListResponse(BaseModel):
    sessions: list[SessionListItem]


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sql_script: Optional[str] = None
    question_ref: Optional[str] = None
    post_process_config: Optional[list[dict[str, Any]]] = None
    chart_configs: Optional[list[dict[str, Any]]] = None
    extra_result_blocks: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Metadata-only extra datasets: block_id, title, sql_script, post_process_config.",
    )
    turn_index: int
    is_summarised: bool
    created_at: str
    follow_up_mode: Optional[str] = None
    report_layout: Optional[dict[str, Any]] = None
    validation: Optional[dict[str, Any]] = None


class UndoLastModificationResponse(BaseModel):
    session_id: str
    removed_turn_index: int
    restored_turn_index: int
    restored_assistant_message_id: Optional[str] = None


class SessionMessagesResponse(BaseModel):
    session_id: str
    messages: list[MessageResponse]
    total_turns: int = 0
    page: int = 1
    page_size: int = 5
    has_more: bool = False


class SqlExecuteResponse(BaseModel):
    """Result of re-executing a stored SQL script (with post-processing re-applied)."""
    message_id: str
    block_id: Optional[str] = Field(
        default=None,
        description="When set, this payload is for an extra_result_blocks entry, not the primary SQL.",
    )
    sql: str
    post_process_config: Optional[list[dict[str, Any]]] = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    raw_columns: Optional[list[str]] = None
    raw_rows: Optional[list[list[Any]]] = None
    raw_row_count: Optional[int] = None
    error: Optional[str] = None


# ── Suggestions ───────────────────────────────────────────────────

class SuggestionsResponse(BaseModel):
    questions: list[str]


class CatalogSyncSummary(BaseModel):
    """Result of semantic_catalog_tool refresh --write (when bootstrap refresh=true)."""

    ok: bool = True
    catalog_path: Optional[str] = None
    table_count: int = 0
    topics_tables_added: dict[str, list[str]] = Field(default_factory=dict)
    topics_tables_removed: dict[str, list[str]] = Field(default_factory=dict)
    joins_added: int = 0
    dimension_stubs_added: list[str] = Field(default_factory=list)
    removed_dimensions: list[str] = Field(default_factory=list)
    warehouse_only_tables: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class DatamartBootstrapResponse(BaseModel):
    tenant_id: str
    profile: str
    database_name: str
    query_schemas: list[str]
    primary_schema: str
    # Per schema in query_schemas: base tables + views (hr_semantic is view-heavy).
    table_counts: dict[str, int]
    total_tables: int
    ready: bool
    synced_at: str
    fingerprint: str
    catalog_sync: Optional[CatalogSyncSummary] = None


# ── Session groups ────────────────────────────────────────────────

class SessionGroupCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class SessionGroupRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class SessionGroupResponse(BaseModel):
    id: str
    name: str
    position: int
    created_at: str
    updated_at: str


class SessionGroupListResponse(BaseModel):
    groups: list[SessionGroupResponse]


class MoveSessionToGroupRequest(BaseModel):
    group_id: Optional[str] = Field(
        default=None,
        description="UUID of the target group, or null to ungroup.",
    )


# ── Template groups ───────────────────────────────────────────────

class TemplateGroupCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class TemplateGroupRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class TemplateGroupResponse(BaseModel):
    id: str
    name: str
    position: int
    created_at: str
    updated_at: str


class TemplateGroupListResponse(BaseModel):
    groups: list[TemplateGroupResponse]


# ── Templates ─────────────────────────────────────────────────────

class TemplateVersionResponse(BaseModel):
    id: str
    template_id: str
    version_num: int
    label: Optional[str] = None
    sql_script: str
    post_process_config: Optional[list[dict[str, Any]]] = None
    chart_configs: Optional[list[dict[str, Any]]] = None
    extra_result_blocks: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Metadata-only extra datasets: block_id, title, sql_script, post_process_config.",
    )
    report_layout: Optional[dict[str, Any]] = None
    narrative: Optional[str] = None
    source_session_id: Optional[str] = None
    source_message_id: Optional[str] = None
    is_latest: bool
    created_at: str


class TemplateResponse(BaseModel):
    id: str
    name: str
    group_id: Optional[str] = None
    group: Optional[TemplateGroupResponse] = None
    is_pinned: bool
    created_at: str
    updated_at: str
    latest_version: Optional[TemplateVersionResponse] = None


class TemplateListResponse(BaseModel):
    templates: list[TemplateResponse]


class TemplateVersionListResponse(BaseModel):
    versions: list[TemplateVersionResponse]


class PromoteToTemplateRequest(BaseModel):
    """Promote a chat message result to a new template."""
    name: str = Field(..., min_length=1, max_length=255)
    session_id: str
    message_id: str


class SaveVersionRequest(BaseModel):
    """Save the current template state as a new named version."""
    sql_script: str = Field(..., min_length=1)
    post_process_config: Optional[list[dict[str, Any]]] = None
    chart_configs: Optional[list[dict[str, Any]]] = None
    extra_result_blocks: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Additional scenario SQL blocks (same JSON shape as chat messages).",
    )
    report_layout: Optional[dict[str, Any]] = None
    narrative: Optional[str] = None
    label: Optional[str] = Field(default=None, max_length=255)


class TemplateRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class MoveTemplateToGroupRequest(BaseModel):
    group_id: Optional[str] = Field(
        default=None,
        description="UUID of the target group, or null to ungroup.",
    )


class TemplateChatRequest(BaseModel):
    """Request body for the template modify-chat endpoint."""
    question: str = Field(..., min_length=1, max_length=2000)
    follow_up_mode: Optional[FollowUpMode] = Field(
        default=None,
        description=(
            "How this message relates to the current template: "
            "continue_last (modify), add_scenario (extra dataset), new_question (replace primary SQL)."
        ),
    )
    target_scenario_ids: Optional[list[str]] = Field(
        default=None,
        max_length=32,
        description=(
            "With continue_last on a multi-scenario template: panel ids to modify "
            "('primary' and/or extra block_id values)."
        ),
    )
