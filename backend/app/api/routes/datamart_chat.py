"""
Datamart Chat API - Route handlers
Exposes the datamart text-to-SQL agent, session management, and workspace
(session groups, templates, template versions, template groups) over HTTP.
"""
import asyncio
import contextlib
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_api_key
from app.services.ai_services.datamart.workspace.runtime_context import (
    require_datamart_context,
    sync_datamart_metadata,
)
from app.services.ai_services.datamart.workspace.tenant_dependency import datamart_runtime_dependency
from app.services.ai_services.datamart.agent import ask
from app.services.ai_services.datamart.pipeline_trace import PipelineTrace
from app.services.ai_services.datamart.orchestration.clarification_flow import merge_clarified_question
from app.services.ai_services.datamart.orchestration.intent_router import classify_chat_intent
from app.services.ai_services.datamart.validation.validation_runner import build_grounding_preview
from app.services.ai_services.datamart.config import SAMPLE_QUESTIONS
from app.services.ai_services.datamart.scenario.block_merge import merge_extra_result_blocks
from app.services.ai_services.datamart.scenario.scenario_scope import (
    apply_target_scope_to_result,
    normalize_target_scenario_ids,
)
from app.services.ai_services.datamart.models import (
    CatalogSyncSummary,
    DatamartBootstrapResponse,
    DatamartChatRequest,
    GroundingPreviewRequest,
    GroundingPreviewResponse,
    DatamartChartConfigV1,
    DatamartResponse,
    DatamartResultBlock,
    ExecuteSqlOverrideRequest,
    FollowUpMode,
    MessageResponse,
    PatchMessageReportMetaRequest,
    PatchMessageReportMetaResponse,
    PatchTemplateVersionReportMetaRequest,
    PatchTemplateVersionReportMetaResponse,
    MoveSessionToGroupRequest,
    MoveTemplateToGroupRequest,
    PromoteToTemplateRequest,
    PutMessageChartsRequest,
    PutMessageChartsResponse,
    SaveVersionRequest,
    SessionCreateRequest,
    SessionGroupCreateRequest,
    SessionGroupListResponse,
    SessionGroupRenameRequest,
    SessionGroupResponse,
    SessionListItem,
    SessionListResponse,
    SessionMessagesResponse,
    SessionRenameRequest,
    SqlExecuteResponse,
    SuggestionsResponse,
    UndoLastModificationResponse,
    TemplateChatRequest,
    TemplateGroupCreateRequest,
    TemplateGroupListResponse,
    TemplateGroupRenameRequest,
    TemplateGroupResponse,
    TemplateListResponse,
    TemplateRenameRequest,
    TemplateResponse,
    TemplateVersionListResponse,
    TemplateVersionResponse,
)
from app.services.ai_services.datamart.postprocess.post_processor import (
    apply as apply_post_processing,
    finalize_datamart_rows_after_post_process,
    shrink_outer_limit_for_append_sql,
)
from app.services.ai_services.datamart.schema import execute_sql
from app.services.ai_services.datamart.sql.sql_exec_guard import ensure_select_limit
from app.services.ai_services.datamart.sql.sql_safety import validate_readonly_sql
from app.services.ai_services.datamart.llm.llm_response import extract_last_sql_from_history
from app.services.ai_services.datamart.workspace.auth_context import (
    get_datamart_tenant_id_from_auth,
    get_datamart_user_id,
)
from app.services.ai_services.datamart.workspace.session_service import (
    LastAssistantSnapshot,
    LLMContext,
    append_turn,
    build_llm_context,
    build_template_context,
    create_session,
    delete_session,
    delete_turns_from,
    get_message_by_id,
    session_has_turn,
    get_messages_paged,
    get_clarification_anchor_question,
    get_last_assistant_turn_snapshot,
    get_max_turn_index,
    get_session,
    get_user_question_at_turn,
    list_sessions,
    rename_session,
    undo_last_modification,
    update_assistant_message_charts,
    update_assistant_report_meta,
)
from app.services.ai_services.datamart.scenario.extra_blocks import normalize_sql_one_line
from app.services.ai_services.datamart.workspace.workspace_service import (
    create_session_group,
    create_template_group,
    delete_session_group,
    delete_template,
    delete_template_group,
    get_template,
    get_template_group,
    get_template_version,
    get_or_create_template_session,
    list_session_groups,
    list_template_groups,
    list_template_versions,
    list_templates,
    move_session_to_group,
    move_template_to_group,
    promote_to_template,
    rename_session_group,
    rename_template,
    rename_template_group,
    save_template_version,
    patch_template_version_report_meta,
    toggle_pin_template,
)

logger = logging.getLogger("ai_services.datamart")

router = APIRouter(
    dependencies=[
        Depends(verify_api_key),
        Depends(datamart_runtime_dependency),
    ]
)


def _pipeline_trace_from_stored(raw: object):
    from app.services.ai_services.datamart.pipeline_trace import PipelineTrace

    if isinstance(raw, dict):
        try:
            return PipelineTrace.model_validate(raw)
        except Exception:
            return None
    return None


def _extra_blocks_for_response(
    stored: Optional[list],
) -> Optional[list[DatamartResultBlock]]:
    """Convert persisted extra_result_blocks JSON to API DatamartResultBlock list."""
    if not stored:
        return None
    out: list[DatamartResultBlock] = []
    for blk in stored:
        if not isinstance(blk, dict):
            continue
        bid = str(blk.get("block_id") or "").strip()
        if not bid:
            continue
        sql_val = blk.get("sql_script") or blk.get("sql")
        val = blk.get("validation")
        out.append(
            DatamartResultBlock(
                block_id=bid,
                title=blk.get("title"),
                sql=str(sql_val) if sql_val else None,
                post_process_config=blk.get("post_process_config")
                if isinstance(blk.get("post_process_config"), list)
                else None,
                validation=val if isinstance(val, dict) else None,
                pipeline_trace=_pipeline_trace_from_stored(blk.get("pipeline_trace")),
            )
        )
    return out or None


def _result_block_from_merge_meta(
    meta: dict,
    live: Optional[DatamartResultBlock],
) -> DatamartResultBlock:
    if live is not None:
        return live
    bid = str(meta.get("block_id") or "")
    sql_val = meta.get("sql_script") or meta.get("sql")
    val = meta.get("validation")
    return DatamartResultBlock(
        block_id=bid,
        title=meta.get("title"),
        sql=str(sql_val) if sql_val else None,
        post_process_config=meta.get("post_process_config")
        if isinstance(meta.get("post_process_config"), list)
        else None,
        validation=val if isinstance(val, dict) else None,
        pipeline_trace=_pipeline_trace_from_stored(meta.get("pipeline_trace")),
    )


def _template_group_response(g) -> TemplateGroupResponse:
    """Map workspace DTO to API model (ids and timestamps are already JSON-safe strings)."""
    return TemplateGroupResponse(
        id=g.id,
        name=g.name,
        position=g.position,
        created_at=g.created_at,
        updated_at=g.updated_at,
    )


def _short_label(text: Optional[str], max_len: int = 48) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    if len(t) <= max_len:
        return t
    return f"{t[: max_len - 1].rstrip()}…"


def _execute_stored_sql_pipeline(
    sql_script: str,
    post_process_config: Optional[list],
) -> SqlExecuteResponse:
    """
    Run shrink → execute_sql → optional post_process.
    Returns SqlExecuteResponse without message_id / block_id (caller fills those).
    """
    try:
        sql_run = ensure_select_limit(
            shrink_outer_limit_for_append_sql(sql_script, post_process_config)
        )
        columns, rows, row_count = execute_sql(sql_run, validate_binding=False)
        raw_columns = raw_rows = None
        raw_row_count = None
        if post_process_config:
            raw_columns = list(columns)
            raw_rows = [list(r) for r in rows]
            raw_row_count = row_count
            try:
                columns, rows = apply_post_processing(columns, rows, post_process_config)
                row_count = len(rows)
                rows = finalize_datamart_rows_after_post_process(rows, len(raw_rows))
                row_count = len(rows)
            except ValueError as pp_exc:
                return SqlExecuteResponse(
                    message_id="",
                    sql=sql_script,
                    post_process_config=post_process_config,
                    columns=columns,
                    rows=rows,
                    row_count=row_count,
                    error=f"Post-processing warning: {pp_exc}",
                )
        return SqlExecuteResponse(
            message_id="",
            sql=sql_script,
            post_process_config=post_process_config,
            columns=columns,
            rows=rows,
            row_count=row_count,
            raw_columns=raw_columns,
            raw_rows=raw_rows,
            raw_row_count=raw_row_count,
        )
    except RuntimeError as exc:
        return SqlExecuteResponse(
            message_id="",
            sql=sql_script,
            post_process_config=post_process_config,
            error=str(exc),
        )


# ── Helpers ───────────────────────────────────────────────────────

def _parse_uuid(value: str, field: str = "id") -> uuid.UUID:
    """Parse a UUID string, raising HTTP 422 on invalid format."""
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {field} format: {value!r}",
        )


def _require_user_session(db: Session, session_id: str):
    """Load a chat session owned by the authenticated user (HRIS user_emp_id / JWT user_id)."""
    session_uuid = _parse_uuid(session_id, "session_id")
    session = get_session(db, session_uuid, user_id=get_datamart_user_id())
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )
    return session


# ── Bootstrap / metadata sync ─────────────────────────────────────

@router.get(
    "/bootstrap",
    response_model=DatamartBootstrapResponse,
    summary="Resolve tenant warehouse profile; refresh=true runs full sync (catalog + metadata)",
)
def datamart_bootstrap(
    refresh: bool = False,
    sync_phase: Optional[str] = Query(
        None,
        description="Staged full sync: prepare | catalog | metadata | full. "
        "UI calls prepare → catalog → metadata for progress steps.",
    ),
) -> DatamartBootstrapResponse:
    """
    Warehouse introspection for the status pill.

    ``refresh=true`` or ``sync_phase=full``: full sync in one request (legacy).

    Staged sync (Sync button UI):
      prepare — invalidate caches
      catalog — refresh semantic_catalogs/{tenant}.yaml
      metadata — recount tables in hr_semantic / hr / hr_snap
    """
    from app.services.ai_services.datamart.workspace.runtime_context import (
        invalidate_datamart_metadata_caches,
    )
    from app.services.ai_services.datamart.semantic.semantic_catalog_sync import (
        refresh_semantic_catalog_for_tenant,
    )

    ctx = require_datamart_context()
    phase = (sync_phase or "").strip().lower()
    if refresh and not phase:
        phase = "full"

    catalog_sync: Optional[CatalogSyncSummary] = None

    if phase == "prepare":
        invalidate_datamart_metadata_caches(ctx.tenant_id)
        meta = sync_datamart_metadata(ctx.tenant_id, force_refresh=False)
        return DatamartBootstrapResponse(**meta)

    if phase == "catalog":
        invalidate_datamart_metadata_caches(ctx.tenant_id)
        try:
            summary = refresh_semantic_catalog_for_tenant(ctx.tenant_id)
            catalog_sync = CatalogSyncSummary(**summary)
        except Exception as exc:  # noqa: BLE001
            logger.exception("semantic catalog refresh failed tenant=%s", ctx.tenant_id)
            catalog_sync = CatalogSyncSummary(ok=False, error=str(exc)[:500])
        meta = sync_datamart_metadata(ctx.tenant_id, force_refresh=False)
        if catalog_sync is not None:
            meta = {**meta, "catalog_sync": catalog_sync.model_dump(mode="json")}
        return DatamartBootstrapResponse(**meta)

    if phase == "metadata":
        meta = sync_datamart_metadata(ctx.tenant_id, force_refresh=True)
        return DatamartBootstrapResponse(**meta)

    if phase == "full":
        invalidate_datamart_metadata_caches(ctx.tenant_id)
        logger.info(
            "datamart full sync tenant=%s db=%s",
            ctx.tenant_id,
            ctx.database_name,
        )
        try:
            summary = refresh_semantic_catalog_for_tenant(ctx.tenant_id)
            catalog_sync = CatalogSyncSummary(**summary)
        except Exception as exc:  # noqa: BLE001
            logger.exception("semantic catalog refresh failed tenant=%s", ctx.tenant_id)
            catalog_sync = CatalogSyncSummary(ok=False, error=str(exc)[:500])
        meta = sync_datamart_metadata(ctx.tenant_id, force_refresh=True)
        if catalog_sync is not None:
            meta = {**meta, "catalog_sync": catalog_sync.model_dump(mode="json")}
        return DatamartBootstrapResponse(**meta)

    meta = sync_datamart_metadata(ctx.tenant_id, force_refresh=refresh)
    return DatamartBootstrapResponse(**meta)


# ── Chat ──────────────────────────────────────────────────────────


def _validation_to_json(result: DatamartResponse) -> Optional[dict]:
    if (
        result.validation is None
        and result.pipeline_trace is None
        and result.pipeline_meta is None
    ):
        return None
    payload: dict = {}
    if result.validation is not None:
        payload = result.validation.model_dump(mode="json")
    if result.pipeline_trace is not None:
        payload["pipeline_trace"] = result.pipeline_trace.model_dump(mode="json")
    if result.pipeline_meta is not None:
        payload["pipeline_meta"] = result.pipeline_meta.model_dump(mode="json")
    return payload or None


@router.post(
    "/grounding/preview",
    response_model=GroundingPreviewResponse,
    summary="Preview schema grounding and retrieval validation (no LLM)",
)
def datamart_grounding_preview(
    req: GroundingPreviewRequest,
    db: Session = Depends(get_db),
) -> GroundingPreviewResponse:
    """Build grounding for a question without generating SQL."""
    last_sql: Optional[str] = None
    if req.session_id:
        session_uuid = _parse_uuid(req.session_id, "session_id")
        _require_user_session(db, req.session_id)
        snap = get_last_assistant_turn_snapshot(db, session_uuid)
        if snap and snap.sql_script:
            last_sql = snap.sql_script

    intent = classify_chat_intent(
        req.question,
        last_sql=last_sql,
        has_prior_post_process=False,
        follow_up_mode=req.follow_up_mode,
    )
    tenant_id = get_datamart_tenant_id_from_auth()

    def _run() -> GroundingPreviewResponse:
        from app.services.ai_services.datamart.workspace.runtime_context import (
            run_with_datamart_context,
        )

        return run_with_datamart_context(
            tenant_id,
            build_grounding_preview,
            question=req.question,
            chat_intent=intent,
            last_sql=last_sql,
            confirmed_tables=req.confirmed_tables,
        )

    return _run()


def _format_sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def execute_datamart_chat_turn(
    req: DatamartChatRequest,
    db: Session,
    *,
    on_pipeline_update: Optional[Callable[[PipelineTrace], None]] = None,
) -> DatamartResponse:
    """
    Full pipeline:
    1. Resolve or create the session.
    2. Build LLM context from session history (with auto-summarisation).
    3. Run the agent (DataHub -> schema -> LLM -> SQL -> execute).
    4. Persist the turn to the session.
    5. Return the structured response with session_id.
    """
    if req.session_id:
        session = _require_user_session(db, req.session_id)
        session_uuid = session.id
    else:
        if req.edit_from_turn_index is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="edit_from_turn_index requires an existing session_id.",
            )
        session = create_session(db, user_id=get_datamart_user_id())
        session_uuid = session.id

    if req.edit_from_turn_index is not None:
        turn_idx = req.edit_from_turn_index
        if not session_has_turn(db, session_uuid, turn_idx):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Turn {turn_idx} not found in this session.",
            )
        delete_turns_from(db, session_uuid, turn_idx)
        logger.info(
            "datamart_chat: edit_resend session=%s from_turn=%d",
            session_uuid,
            turn_idx,
        )

    logger.info(
        "datamart_chat: session=%s question_chars=%s edit_from=%s",
        session_uuid,
        len(req.question or ""),
        req.edit_from_turn_index,
    )

    llm_context = build_llm_context(db, session_uuid)
    targets = normalize_target_scenario_ids(req.target_scenario_ids)
    needs_prior_snapshot = (
        req.follow_up_mode in (FollowUpMode.ADD_SCENARIO, FollowUpMode.CONTINUE_LAST)
        or bool(targets)
        or (
            req.follow_up_mode is None
            and (
                llm_context.previous_post_process_config is not None
                or llm_context.previous_extra_result_blocks
            )
        )
    )
    prior_for_scope = (
        get_last_assistant_turn_snapshot(db, session_uuid)
        if needs_prior_snapshot
        else None
    )

    question_for_agent = req.question
    agent_follow_up_mode = req.follow_up_mode
    if req.session_id or session_uuid:
        anchor = get_clarification_anchor_question(db, session_uuid)
        if anchor and (
            req.follow_up_mode == FollowUpMode.CLARIFY_REPLY
            or req.follow_up_mode is None
        ):
            question_for_agent = merge_clarified_question(anchor, req.question)
            agent_follow_up_mode = FollowUpMode.NEW_QUESTION
            logger.info(
                "datamart_chat: clarify_reply merged anchor_chars=%s reply_chars=%s",
                len(anchor),
                len(req.question or ""),
            )

    tenant_id = get_datamart_tenant_id_from_auth()
    try:
        result = ask(
            question=question_for_agent,
            history_text=llm_context.history_text,
            previous_post_process_config=llm_context.previous_post_process_config,
            follow_up_mode=agent_follow_up_mode,
            target_scenario_ids=req.target_scenario_ids,
            previous_extra_result_blocks=llm_context.previous_extra_result_blocks,
            previous_primary_sql=(
                prior_for_scope.sql_script
                if prior_for_scope and prior_for_scope.sql_script
                else None
            ),
            confirmed_table_names=req.confirmed_tables,
            tenant_id=tenant_id,
            on_pipeline_update=on_pipeline_update,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error in datamart_chat: %s", exc)
        from app.core.config import settings

        detail = "An unexpected error occurred."
        if settings.DEBUG:
            detail = f"{type(exc).__name__}: {exc}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        ) from exc

    if not result.error or result.narrative:
        is_add_scenario = req.follow_up_mode == FollowUpMode.ADD_SCENARIO
        prior_snapshot = prior_for_scope if needs_prior_snapshot else None
        llm_primary_sql: Optional[str] = None
        if is_add_scenario and prior_snapshot and prior_snapshot.sql_script:
            llm_primary_sql = result.sql
            result.sql = prior_snapshot.sql_script
            result.post_process_config = prior_snapshot.post_process_config
            primary_exec = _execute_stored_sql_pipeline(
                prior_snapshot.sql_script,
                prior_snapshot.post_process_config,
            )
            if primary_exec.error and not primary_exec.columns:
                result.error = primary_exec.error
            else:
                result.columns = primary_exec.columns
                result.rows = primary_exec.rows
                result.row_count = primary_exec.row_count
                result.raw_columns = primary_exec.raw_columns
                result.raw_rows = primary_exec.raw_rows
                result.raw_row_count = primary_exec.raw_row_count
                if primary_exec.error:
                    result.error = primary_exec.error
                elif result.error and primary_exec.columns:
                    result.error = None
            if (
                not result.extra_result_blocks
                and llm_primary_sql
                and normalize_sql_one_line(llm_primary_sql)
                != normalize_sql_one_line(prior_snapshot.sql_script)
            ):
                import uuid as _uuid

                fallback_id = str(_uuid.uuid4())
                from app.services.ai_services.datamart.scenario.extra_blocks import (
                    run_extra_datamart_block,
                )
                from app.services.ai_services.datamart.prompts.chat_prompts import (
                    format_chat_system_prompt,
                )
                blk = run_extra_datamart_block(
                    spec={
                        "block_id": fallback_id,
                        "title": req.question[:80].strip() or "New scenario",
                        "sql": llm_primary_sql,
                        "post_process": None,
                    },
                    system_prompt=format_chat_system_prompt(),
                    primary_sql=prior_snapshot.sql_script,
                )
                result.extra_result_blocks = [blk]
        follow_up_merge = (
            req.follow_up_mode == FollowUpMode.CONTINUE_LAST
            or req.follow_up_mode == FollowUpMode.ADD_SCENARIO
            or (
                req.follow_up_mode is None
                and (
                    llm_context.previous_post_process_config is not None
                    or llm_context.previous_extra_result_blocks
                )
            )
        )
        merge_previous = (
            prior_snapshot.extra_result_blocks
            if is_add_scenario and prior_snapshot
            else llm_context.previous_extra_result_blocks
        )
        extra_meta = merge_extra_result_blocks(
            question=req.question,
            previous=merge_previous,
            new_blocks=result.extra_result_blocks,
            follow_up_continue=bool(follow_up_merge),
            target_scenario_ids=targets,
        )
        if extra_meta and result.extra_result_blocks:
            new_by_id = {b.block_id: b for b in result.extra_result_blocks if b.sql}
            merged_blocks: list[DatamartResultBlock] = []
            for meta in extra_meta:
                bid = str(meta.get("block_id") or "")
                if bid in new_by_id:
                    merged_blocks.append(new_by_id[bid])
                else:
                    merged_blocks.append(_result_block_from_merge_meta(meta, None))
            result.extra_result_blocks = merged_blocks or None

        if targets and prior_snapshot:
            result = apply_target_scope_to_result(
                result,
                targets=targets,
                prior_sql=prior_snapshot.sql_script,
                prior_post_process=prior_snapshot.post_process_config,
                prior_extra_blocks=prior_snapshot.extra_result_blocks,
                execute_primary=_execute_stored_sql_pipeline,
            )

        if is_add_scenario and prior_snapshot and prior_snapshot.sql_script:
            prev_block_ids = {
                str(b.get("block_id"))
                for b in (merge_previous or [])
                if isinstance(b, dict) and b.get("block_id")
            }
            has_new_block = bool(
                result.extra_result_blocks
                and any(
                    b.block_id not in prev_block_ids and b.columns and b.rows
                    for b in result.extra_result_blocks
                )
            ) or bool(
                extra_meta
                and any(
                    str(b.get("block_id")) not in prev_block_ids
                    for b in extra_meta
                    if isinstance(b, dict) and b.get("block_id")
                )
            )
            if not has_new_block:
                import uuid as _uuid

                from app.services.ai_services.datamart.prompts.chat_prompts import (
                    format_chat_system_prompt,
                )
                from app.services.ai_services.datamart.scenario.extra_blocks import (
                    run_extra_datamart_block,
                )
                from app.services.ai_services.datamart.schema_broker import (
                    BrokerMode,
                    build_schema_grounding,
                )
                from app.services.ai_services.datamart.sql.sql_repairs import (
                    attempt_missing_sql_repair,
                )

                sql_for_extra = llm_primary_sql
                if sql_for_extra and normalize_sql_one_line(sql_for_extra) == normalize_sql_one_line(
                    prior_snapshot.sql_script
                ):
                    sql_for_extra = None
                if not sql_for_extra:
                    grounding = build_schema_grounding(
                        question=req.question,
                        mode=BrokerMode.CHAT,
                        last_sql=None,
                    )
                    _n, sql_for_extra, _p = attempt_missing_sql_repair(
                        req.question,
                        grounding,
                        "",
                        "",
                    )
                if sql_for_extra:
                    fallback_id = str(_uuid.uuid4())
                    blk = run_extra_datamart_block(
                        spec={
                            "block_id": fallback_id,
                            "title": _short_label(req.question, 80) or "New scenario",
                            "sql": sql_for_extra,
                            "post_process": None,
                        },
                        system_prompt=format_chat_system_prompt(),
                        primary_sql=prior_snapshot.sql_script,
                    )
                    merged_new = list(result.extra_result_blocks or [])
                    merged_new.append(blk)
                    result.extra_result_blocks = merged_new
                    extra_meta = merge_extra_result_blocks(
                        question=req.question,
                        previous=merge_previous,
                        new_blocks=result.extra_result_blocks,
                        follow_up_continue=True,
                    )
                    if extra_meta and result.extra_result_blocks:
                        new_by_id = {
                            b.block_id: b for b in result.extra_result_blocks if b.sql
                        }
                        merged_blocks = []
                        for meta in extra_meta:
                            bid = str(meta.get("block_id") or "")
                            if bid in new_by_id:
                                merged_blocks.append(new_by_id[bid])
                            else:
                                merged_blocks.append(
                                    _result_block_from_merge_meta(meta, None)
                                )
                        result.extra_result_blocks = merged_blocks or None

        report_layout = (
            prior_snapshot.report_layout
            if is_add_scenario and prior_snapshot and prior_snapshot.report_layout
            else llm_context.previous_report_layout
        )
        if isinstance(report_layout, dict):
            report_layout = dict(report_layout)
            report_layout.setdefault("view_mode", "stacked")
        elif is_add_scenario:
            report_layout = {"schema_version": 1, "view_mode": "stacked", "widgets": []}
        elif result.sql or result.extra_result_blocks:
            report_layout = {
                "schema_version": 1,
                "view_mode": "stacked",
                "widgets": [],
                "active_panel_id": "primary",
            }

        if is_add_scenario:
            prior_turn = get_max_turn_index(db, session_uuid)
            prior_user_q = (
                get_user_question_at_turn(db, session_uuid, prior_turn)
                if prior_turn is not None
                else None
            )
            layout = dict(report_layout or {"schema_version": 1, "view_mode": "stacked", "widgets": []})
            if not layout.get("primary_label") and prior_user_q:
                layout["primary_label"] = _short_label(prior_user_q)
            if prior_snapshot and prior_snapshot.narrative:
                layout["primary_narrative"] = prior_snapshot.narrative.strip()
            prev_ids_for_panel = {
                str(b.get("block_id"))
                for b in (merge_previous or [])
                if isinstance(b, dict) and b.get("block_id")
            }
            new_panel_id: Optional[str] = None
            if result.extra_result_blocks:
                for blk in result.extra_result_blocks:
                    if blk.block_id not in prev_ids_for_panel:
                        new_panel_id = blk.block_id
            layout["active_panel_id"] = new_panel_id or layout.get("active_panel_id") or "primary"
            layout.setdefault("view_mode", "stacked")
            layout.setdefault("schema_version", 1)
            report_layout = layout
            if result.columns and result.row_count:
                result.error = None
            if extra_meta:
                new_ids = {
                    str(b.block_id)
                    for b in (result.extra_result_blocks or [])
                    if b.sql
                }
                for meta in extra_meta:
                    bid = str(meta.get("block_id") or "")
                    if bid in new_ids and not (meta.get("title") or "").strip():
                        meta["title"] = _short_label(req.question, 80) or "New scenario"

        follow_up_value = (
            req.follow_up_mode.value if req.follow_up_mode is not None else None
        )
        turn_result = append_turn(
            db=db,
            session_id=session_uuid,
            question=req.question,
            narrative=result.narrative,
            sql_script=result.sql,
            post_process_config=result.post_process_config,
            extra_result_blocks=extra_meta,
            follow_up_mode=follow_up_value,
            report_layout=report_layout,
            validation=_validation_to_json(result),
        )
        result.message_id = turn_result.assistant_message_id
        result.turn_index = turn_result.turn_index
        result.report_layout = report_layout

    result.session_id = str(session_uuid)
    return result


@router.post("/chat", response_model=DatamartResponse,
             summary="Send a message to the datamart agent")
def datamart_chat(
    req: DatamartChatRequest,
    db: Session = Depends(get_db),
) -> DatamartResponse:
    """Blocking JSON response (legacy). Prefer ``/chat/stream`` for live pipeline UI."""
    return execute_datamart_chat_turn(req, db)


@router.post(
    "/chat/stream",
    summary="Send a message with live pipeline progress (SSE)",
)
async def datamart_chat_stream(
    req: DatamartChatRequest,
) -> StreamingResponse:
    """
    Server-Sent Events while the agent runs, then a final ``result`` event.

    Events:
    - ``pipeline`` — ``PipelineTrace`` JSON snapshot after each step change
    - ``result`` — full ``DatamartResponse`` when the turn is persisted
    - ``error`` — ``{ "message": "..." }`` on failure
    - ``done`` — stream complete
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()

    def on_pipeline(trace: PipelineTrace) -> None:
        loop.call_soon_threadsafe(
            queue.put_nowait,
            ("pipeline", trace.model_dump(mode="json")),
        )

    def _run_turn_in_thread() -> DatamartResponse:
        from app.core.database import SessionLocal

        session = SessionLocal()
        try:
            return execute_datamart_chat_turn(
                req,
                session,
                on_pipeline_update=on_pipeline,
            )
        finally:
            session.close()

    async def event_stream() -> AsyncIterator[str]:
        turn_task = asyncio.create_task(asyncio.to_thread(_run_turn_in_thread))
        try:
            while True:
                done = turn_task.done()
                try:
                    item = await asyncio.wait_for(
                        queue.get(),
                        timeout=0.2 if not done else 0.02,
                    )
                except asyncio.TimeoutError:
                    if done and queue.empty():
                        break
                    continue
                event, payload = item
                yield _format_sse(event, payload)

            result = await turn_task
            yield _format_sse("result", result.model_dump(mode="json"))
            yield _format_sse("done", {})
        except HTTPException as exc:
            detail = exc.detail
            if not isinstance(detail, str):
                detail = str(detail)
            yield _format_sse("error", {"message": detail})
        except Exception as exc:  # noqa: BLE001
            logger.exception("datamart_chat_stream failed: %s", exc)
            from app.core.config import settings

            detail = "An unexpected error occurred."
            if settings.DEBUG:
                detail = f"{type(exc).__name__}: {exc}"
            yield _format_sse("error", {"message": detail})
        finally:
            if not turn_task.done():
                turn_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await turn_task

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Sessions ──────────────────────────────────────────────────────

@router.get("/sessions", response_model=SessionListResponse,
            summary="List all sessions for the current user")
def list_user_sessions(db: Session = Depends(get_db)) -> SessionListResponse:
    items = list_sessions(db, user_id=get_datamart_user_id())
    return SessionListResponse(sessions=[
        SessionListItem(id=i.id, title=i.title, created_at=i.created_at,
                        updated_at=i.updated_at, message_count=i.message_count,
                        group_id=i.group_id)
        for i in items
    ])


@router.post("/sessions", response_model=SessionListItem,
             status_code=status.HTTP_201_CREATED, summary="Create a new empty session")
def create_new_session(
    req: SessionCreateRequest,
    db: Session = Depends(get_db),
) -> SessionListItem:
    session = create_session(db, user_id=get_datamart_user_id(), title=req.title)
    return SessionListItem(id=str(session.id), title=session.title,
                           created_at=session.created_at.isoformat(),
                           updated_at=session.updated_at.isoformat(),
                           message_count=0, group_id=None)


@router.get("/sessions/{session_id}", response_model=SessionListItem,
            summary="Get session metadata")
def get_session_detail(
    session_id: str,
    db: Session = Depends(get_db),
) -> SessionListItem:
    session = _require_user_session(db, session_id)
    return SessionListItem(id=str(session.id), title=session.title,
                           created_at=session.created_at.isoformat(),
                           updated_at=session.updated_at.isoformat(),
                           message_count=0,
                           group_id=str(session.group_id) if session.group_id else None)


@router.get("/sessions/{session_id}/messages", response_model=SessionMessagesResponse,
            summary="Load paginated message history for a session")
def get_session_messages(
    session_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
) -> SessionMessagesResponse:
    session_uuid = _parse_uuid(session_id, "session_id")
    _require_user_session(db, session_id)

    paged = get_messages_paged(db, session_uuid, page=page, page_size=page_size)
    return SessionMessagesResponse(
        session_id=session_id,
        messages=[
            MessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                sql_script=m.sql_script,
                question_ref=m.question_ref,
                post_process_config=m.post_process_config,
                chart_configs=m.chart_configs,
                extra_result_blocks=m.extra_result_blocks,
                turn_index=m.turn_index,
                is_summarised=m.is_summarised,
                created_at=m.created_at,
                follow_up_mode=m.follow_up_mode,
                report_layout=m.report_layout,
                validation=m.validation,
            )
            for m in paged.messages
        ],
        total_turns=paged.total_turns, page=paged.page,
        page_size=paged.page_size, has_more=paged.has_more,
    )


@router.post(
    "/sessions/{session_id}/undo-last-modification",
    response_model=UndoLastModificationResponse,
    summary="Undo the latest continue_last modification in a session",
)
def undo_session_last_modification(
    session_id: str,
    db: Session = Depends(get_db),
) -> UndoLastModificationResponse:
    session_uuid = _parse_uuid(session_id, "session_id")
    _require_user_session(db, session_id)
    try:
        result = undo_last_modification(db, session_uuid)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return UndoLastModificationResponse(
        session_id=session_id,
        removed_turn_index=result.removed_turn_index,
        restored_turn_index=result.restored_turn_index,
        restored_assistant_message_id=result.restored_assistant_message_id,
    )


@router.post("/sessions/{session_id}/messages/{message_id}/execute",
             response_model=SqlExecuteResponse,
             summary="Re-execute the SQL stored in a past assistant message")
def execute_message_sql(
    session_id: str,
    message_id: str,
    body: ExecuteSqlOverrideRequest | None = None,
    db: Session = Depends(get_db),
) -> SqlExecuteResponse:
    session_uuid = _parse_uuid(session_id, "session_id")
    _require_user_session(db, session_id)

    msg_uuid = _parse_uuid(message_id, "message_id")
    message = get_message_by_id(db, msg_uuid, session_uuid)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")
    if message.role != "assistant":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Only assistant messages contain executable SQL.")
    if not message.sql_script:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="This message has no stored SQL script.")

    sql_to_run = message.sql_script
    if body and body.sql and body.sql.strip():
        override = body.sql.strip()
        safety_err = validate_readonly_sql(override)
        if safety_err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=safety_err)
        sql_to_run = override

    base = _execute_stored_sql_pipeline(sql_to_run, message.post_process_config)
    return base.model_copy(update={"message_id": message_id, "block_id": None, "sql": sql_to_run})


@router.post(
    "/sessions/{session_id}/messages/{message_id}/blocks/{block_id}/execute",
    response_model=SqlExecuteResponse,
    summary="Re-execute one extra_result_blocks SQL entry on an assistant message",
)
def execute_message_block_sql(
    session_id: str,
    message_id: str,
    block_id: str,
    db: Session = Depends(get_db),
) -> SqlExecuteResponse:
    session_uuid = _parse_uuid(session_id, "session_id")
    _require_user_session(db, session_id)

    msg_uuid = _parse_uuid(message_id, "message_id")
    message = get_message_by_id(db, msg_uuid, session_uuid)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")
    if message.role != "assistant":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only assistant messages contain executable SQL blocks.",
        )
    block_meta: Optional[dict] = None
    for blk in message.extra_result_blocks or []:
        if isinstance(blk, dict) and str(blk.get("block_id")) == block_id:
            block_meta = blk
            break
    if block_meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No extra_result_blocks entry with block_id={block_id!r}.",
        )
    sql_script = block_meta.get("sql_script")
    if not sql_script:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This block has no stored SQL script.",
        )
    ppc = block_meta.get("post_process_config")
    if not isinstance(ppc, list):
        ppc = None
    base = _execute_stored_sql_pipeline(str(sql_script), ppc)
    return base.model_copy(update={"message_id": message_id, "block_id": block_id})


@router.put(
    "/sessions/{session_id}/messages/{message_id}/charts",
    response_model=PutMessageChartsResponse,
    summary="Replace chart definitions on an assistant message",
)
def put_message_charts(
    session_id: str,
    message_id: str,
    req: PutMessageChartsRequest,
    db: Session = Depends(get_db),
) -> PutMessageChartsResponse:
    """
    Persist declarative chart configs (JSON schema v1). Only assistant messages
    with stored SQL may hold charts. Empty ``charts`` clears the attachment.
    """
    session_uuid = _parse_uuid(session_id, "session_id")
    _require_user_session(db, session_id)

    msg_uuid = _parse_uuid(message_id, "message_id")
    message = get_message_by_id(db, msg_uuid, session_uuid)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")
    if message.role != "assistant":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Charts can only be attached to assistant messages.",
        )
    if not message.sql_script:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This message has no SQL script; add a query result before charting.",
        )

    allowed_block_ids = {
        str(b.get("block_id"))
        for b in (message.extra_result_blocks or [])
        if isinstance(b, dict) and b.get("block_id")
    }
    for c in req.charts:
        rid = c.result_block_id
        if rid and rid not in allowed_block_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Chart result_block_id {rid!r} does not match any extra_result_blocks "
                f"on this message.",
            )

    charts_json = [c.model_dump(mode="json") for c in req.charts]
    stored: Optional[list] = charts_json if charts_json else None

    ok = update_assistant_message_charts(db, session_uuid, msg_uuid, stored)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update message charts.",
        )
    return PutMessageChartsResponse(message_id=message_id, chart_configs=charts_json)


@router.patch(
    "/sessions/{session_id}/messages/{message_id}/report-meta",
    response_model=PatchMessageReportMetaResponse,
    summary="Update scenario labels and report canvas layout",
)
def patch_message_report_meta(
    session_id: str,
    message_id: str,
    req: PatchMessageReportMetaRequest,
    db: Session = Depends(get_db),
) -> PatchMessageReportMetaResponse:
    session_uuid = _parse_uuid(session_id, "session_id")
    _require_user_session(db, session_id)

    msg_uuid = _parse_uuid(message_id, "message_id")
    updated = update_assistant_report_meta(
        db,
        session_uuid,
        msg_uuid,
        report_layout=req.report_layout,
        primary_label=req.primary_label,
        block_labels=req.block_labels,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant message not found.",
        )
    return PatchMessageReportMetaResponse(
        message_id=message_id,
        report_layout=updated.report_layout,
        extra_result_blocks=updated.extra_result_blocks,
    )


@router.patch("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT,
              summary="Rename a session")
def rename_session_endpoint(
    session_id: str, req: SessionRenameRequest,
    db: Session = Depends(get_db),
) -> None:
    session_uuid = _parse_uuid(session_id, "session_id")
    _require_user_session(db, session_id)
    rename_session(db, session_uuid, req.title)


@router.patch("/sessions/{session_id}/group", status_code=status.HTTP_204_NO_CONTENT,
              summary="Move a session to a group (or ungroup)")
def move_session_group(
    session_id: str, req: MoveSessionToGroupRequest,
    db: Session = Depends(get_db),
) -> None:
    session_uuid = _parse_uuid(session_id, "session_id")
    _require_user_session(db, session_id)
    group_uuid = _parse_uuid(req.group_id, "group_id") if req.group_id else None
    move_session_to_group(db, session_uuid, group_uuid)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Soft-delete a session")
def delete_session_endpoint(
    session_id: str,
    db: Session = Depends(get_db),
) -> None:
    session_uuid = _parse_uuid(session_id, "session_id")
    _require_user_session(db, session_id)
    delete_session(db, session_uuid)


# ── Session groups ────────────────────────────────────────────────

@router.get("/session-groups", response_model=SessionGroupListResponse,
            summary="List all session groups")
def list_session_groups_endpoint(
    db: Session = Depends(get_db),
) -> SessionGroupListResponse:
    groups = list_session_groups(db, user_id=get_datamart_user_id())
    return SessionGroupListResponse(groups=[
        SessionGroupResponse(id=g.id, name=g.name, position=g.position,
                             created_at=g.created_at, updated_at=g.updated_at)
        for g in groups
    ])


@router.post("/session-groups", response_model=SessionGroupResponse,
             status_code=status.HTTP_201_CREATED, summary="Create a session group")
def create_session_group_endpoint(
    req: SessionGroupCreateRequest,
    db: Session = Depends(get_db),
) -> SessionGroupResponse:
    g = create_session_group(db, user_id=get_datamart_user_id(), name=req.name)
    return SessionGroupResponse(id=g.id, name=g.name, position=g.position,
                                created_at=g.created_at, updated_at=g.updated_at)


@router.patch("/session-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT,
              summary="Rename a session group")
def rename_session_group_endpoint(
    group_id: str, req: SessionGroupRenameRequest,
    db: Session = Depends(get_db),
) -> None:
    rename_session_group(db, _parse_uuid(group_id, "group_id"), req.name)


@router.delete("/session-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a session group (sessions become ungrouped)")
def delete_session_group_endpoint(
    group_id: str,
    db: Session = Depends(get_db),
) -> None:
    delete_session_group(db, _parse_uuid(group_id, "group_id"))


# ── Templates ─────────────────────────────────────────────────────

@router.get("/templates", response_model=TemplateListResponse,
             summary="List all templates for the current user")
def list_templates_endpoint(
    db: Session = Depends(get_db),
) -> TemplateListResponse:
    templates = list_templates(db, user_id=get_datamart_user_id())
    
    # Fetch all template groups for the user to avoid N+1 queries
    template_groups = list_template_groups(db, user_id=get_datamart_user_id())
    group_map = {g.id: g for g in template_groups}
    
    return TemplateListResponse(templates=[
        TemplateResponse(
            id=t.id, name=t.name, group_id=t.group_id,
            group=_template_group_response(group_map[t.group_id])
            if t.group_id and t.group_id in group_map
            else None,
            is_pinned=t.is_pinned,
            created_at=t.created_at,
            updated_at=t.updated_at,
            latest_version=TemplateVersionResponse(**vars(t.latest_version))
            if t.latest_version else None,
        )
        for t in templates
    ])


@router.post("/templates/promote", response_model=TemplateResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Promote a chat message result to a new template")
def promote_message_to_template(
    req: PromoteToTemplateRequest,
    db: Session = Depends(get_db),
) -> TemplateResponse:
    """
    Promote a chat message to a template.
    Copies sql_script, post_process_config, and narrative from the source message.
    """
    session_uuid = _parse_uuid(req.session_id, "session_id")
    msg_uuid = _parse_uuid(req.message_id, "message_id")

    _require_user_session(db, req.session_id)

    message = get_message_by_id(db, msg_uuid, session_uuid)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")
    if not message.sql_script:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="This message has no SQL script to promote.")

    extra_blocks = (
        [b for b in message.extra_result_blocks if isinstance(b, dict)]
        if message.extra_result_blocks
        else None
    )
    report_layout = (
        dict(message.report_layout)
        if isinstance(message.report_layout, dict)
        else None
    )

    t = promote_to_template(
        db=db,
        user_id=get_datamart_user_id(),
        name=req.name,
        sql_script=message.sql_script,
        post_process_config=message.post_process_config,
        narrative=message.content,
        chart_configs=message.chart_configs,
        extra_result_blocks=extra_blocks,
        report_layout=report_layout,
        source_session_id=session_uuid,
        source_message_id=msg_uuid,
    )
    
    # Fetch the template group if it exists
    group_response = None
    if t.group_id:
        group = get_template_group(db, _parse_uuid(t.group_id, "group_id"))
        if group:
            group_response = _template_group_response(group)
    
    return TemplateResponse(
        id=t.id, name=t.name, group_id=t.group_id, group=group_response, is_pinned=t.is_pinned,
        created_at=t.created_at, updated_at=t.updated_at,
        latest_version=TemplateVersionResponse(**vars(t.latest_version))
        if t.latest_version else None,
    )


@router.get("/templates/{template_id}", response_model=TemplateResponse,
             summary="Get a template with its latest version")
def get_template_endpoint(
    template_id: str,
    db: Session = Depends(get_db),
) -> TemplateResponse:
    t = get_template(db, _parse_uuid(template_id, "template_id"))
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    
    # Fetch the template group if it exists
    group_response = None
    if t.group_id:
        group = get_template_group(db, _parse_uuid(t.group_id, "group_id"))
        if group:
            group_response = _template_group_response(group)
    
    return TemplateResponse(
        id=t.id, name=t.name, group_id=t.group_id, group=group_response, is_pinned=t.is_pinned,
        created_at=t.created_at, updated_at=t.updated_at,
        latest_version=TemplateVersionResponse(**vars(t.latest_version))
        if t.latest_version else None,
    )


@router.patch("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT,
              summary="Rename a template")
def rename_template_endpoint(
    template_id: str, req: TemplateRenameRequest,
    db: Session = Depends(get_db),
) -> None:
    rename_template(db, _parse_uuid(template_id, "template_id"), req.name)


@router.patch("/templates/{template_id}/group", status_code=status.HTTP_204_NO_CONTENT,
              summary="Move a template to a group (or ungroup)")
def move_template_group(
    template_id: str, req: MoveTemplateToGroupRequest,
    db: Session = Depends(get_db),
) -> None:
    tmpl_uuid = _parse_uuid(template_id, "template_id")
    group_uuid = _parse_uuid(req.group_id, "group_id") if req.group_id else None
    move_template_to_group(db, tmpl_uuid, group_uuid)


@router.patch("/templates/{template_id}/pin", summary="Toggle pin on a template")
def pin_template_endpoint(
    template_id: str,
    db: Session = Depends(get_db),
) -> dict:
    new_state = toggle_pin_template(db, _parse_uuid(template_id, "template_id"))
    return {"is_pinned": new_state}


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Soft-delete a template")
def delete_template_endpoint(
    template_id: str,
    db: Session = Depends(get_db),
) -> None:
    delete_template(db, _parse_uuid(template_id, "template_id"))


@router.get("/templates/{template_id}/versions", response_model=TemplateVersionListResponse,
            summary="List all versions of a template (newest first)")
def list_versions_endpoint(
    template_id: str,
    db: Session = Depends(get_db),
) -> TemplateVersionListResponse:
    versions = list_template_versions(db, _parse_uuid(template_id, "template_id"))
    return TemplateVersionListResponse(versions=[
        TemplateVersionResponse(**vars(v)) for v in versions
    ])


@router.post("/templates/{template_id}/versions", response_model=TemplateVersionResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Save the current template state as a new named version")
def save_version_endpoint(
    template_id: str, req: SaveVersionRequest,
    db: Session = Depends(get_db),
) -> TemplateVersionResponse:
    """
    Explicitly save a new version of a template.
    Versions are immutable once created. Editing always creates a new version.
    """
    tmpl_uuid = _parse_uuid(template_id, "template_id")
    if get_template(db, tmpl_uuid) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")

    chart_payload: Optional[list] = None
    if req.chart_configs is not None:
        chart_payload = [
            DatamartChartConfigV1.model_validate(c).model_dump(mode="json")
            for c in req.chart_configs
        ]

    extra_blocks_payload: Optional[list] = None
    if req.extra_result_blocks is not None:
        extra_blocks_payload = [
            b for b in req.extra_result_blocks if isinstance(b, dict)
        ]

    report_layout_payload: Optional[dict] = None
    if req.report_layout is not None and isinstance(req.report_layout, dict):
        report_layout_payload = dict(req.report_layout)

    version = save_template_version(
        db=db,
        template_id=tmpl_uuid,
        sql_script=req.sql_script,
        post_process_config=req.post_process_config,
        narrative=req.narrative,
        label=req.label,
        chart_configs=chart_payload,
        extra_result_blocks=extra_blocks_payload,
        report_layout=report_layout_payload,
    )
    return TemplateVersionResponse(**vars(version))


@router.patch(
    "/templates/{template_id}/versions/{version_id}/report-meta",
    response_model=PatchTemplateVersionReportMetaResponse,
    summary="Update scenario labels and report canvas layout on a template version",
)
def patch_template_version_report_meta_endpoint(
    template_id: str,
    version_id: str,
    req: PatchTemplateVersionReportMetaRequest,
    db: Session = Depends(get_db),
) -> PatchTemplateVersionReportMetaResponse:
    tmpl_uuid = _parse_uuid(template_id, "template_id")
    if get_template(db, tmpl_uuid) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")

    ver_uuid = _parse_uuid(version_id, "version_id")
    updated = patch_template_version_report_meta(
        db,
        ver_uuid,
        report_layout=req.report_layout,
        primary_label=req.primary_label,
        block_labels=req.block_labels,
    )
    if updated is None or updated.template_id != template_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")
    return PatchTemplateVersionReportMetaResponse(
        version_id=version_id,
        report_layout=updated.report_layout,
        extra_result_blocks=updated.extra_result_blocks,
    )


@router.get("/templates/{template_id}/versions/{version_id}",
            response_model=TemplateVersionResponse,
            summary="Get a specific template version")
def get_version_endpoint(
    template_id: str,
    version_id: str,
    db: Session = Depends(get_db),
) -> TemplateVersionResponse:
    version = get_template_version(db, _parse_uuid(version_id, "version_id"))
    if version is None or version.template_id != template_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")
    return TemplateVersionResponse(**vars(version))


@router.post("/templates/{template_id}/versions/{version_id}/execute",
             response_model=SqlExecuteResponse,
             summary="Execute the SQL stored in a template version")
def execute_version_sql(
    template_id: str,
    version_id: str,
    body: ExecuteSqlOverrideRequest | None = None,
    db: Session = Depends(get_db),
) -> SqlExecuteResponse:
    """
    Run the SQL script stored in a specific template version directly against
    the warehouse. Post-processing config is re-applied if present.
    """
    version = get_template_version(db, _parse_uuid(version_id, "version_id"))
    if version is None or version.template_id != template_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")

    sql_to_run = version.sql_script
    if body and body.sql and body.sql.strip():
        override = body.sql.strip()
        safety_err = validate_readonly_sql(override)
        if safety_err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=safety_err)
        sql_to_run = override

    try:
        sql_run = ensure_select_limit(
            shrink_outer_limit_for_append_sql(sql_to_run, version.post_process_config)
        )
        columns, rows, row_count = execute_sql(sql_run, validate_binding=False)
        raw_columns = raw_rows = None
        raw_row_count = None
        if version.post_process_config:
            raw_columns = list(columns)
            raw_rows = [list(r) for r in rows]
            raw_row_count = row_count
            try:
                columns, rows = apply_post_processing(columns, rows, version.post_process_config)
                row_count = len(rows)
                rows = finalize_datamart_rows_after_post_process(rows, len(raw_rows))
                row_count = len(rows)
            except ValueError as pp_exc:
                return SqlExecuteResponse(
                    message_id=version_id,
                    sql=sql_to_run,
                    post_process_config=version.post_process_config,
                    columns=columns,
                    rows=rows,
                    row_count=row_count,
                    error=f"Post-processing warning: {pp_exc}",
                )
        return SqlExecuteResponse(
            message_id=version_id,
            sql=sql_to_run,
            post_process_config=version.post_process_config,
            columns=columns,
            rows=rows,
            row_count=row_count,
            raw_columns=raw_columns,
            raw_rows=raw_rows,
            raw_row_count=raw_row_count,
        )
    except RuntimeError as exc:
        return SqlExecuteResponse(
            message_id=version_id,
            sql=sql_to_run,
            post_process_config=version.post_process_config,
            error=str(exc),
        )


@router.post(
    "/templates/{template_id}/versions/{version_id}/execute-block/{block_id}",
    response_model=SqlExecuteResponse,
    summary="Re-execute one extra_result_blocks SQL entry on a template version",
)
def execute_template_version_block_sql(
    template_id: str,
    version_id: str,
    block_id: str,
    db: Session = Depends(get_db),
) -> SqlExecuteResponse:
    version = get_template_version(db, _parse_uuid(version_id, "version_id"))
    if version is None or version.template_id != template_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")

    block_meta: Optional[dict] = None
    for blk in version.extra_result_blocks or []:
        if isinstance(blk, dict) and str(blk.get("block_id")) == block_id:
            block_meta = blk
            break
    if block_meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No extra_result_blocks entry with block_id={block_id!r}.",
        )
    sql_script = block_meta.get("sql_script") or block_meta.get("sql")
    if not sql_script:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This block has no stored SQL script.",
        )
    ppc = block_meta.get("post_process_config")
    if not isinstance(ppc, list):
        ppc = None
    base = _execute_stored_sql_pipeline(str(sql_script), ppc)
    return base.model_copy(update={"message_id": version_id, "block_id": block_id})


@router.post("/templates/{template_id}/chat", response_model=DatamartResponse,
             summary="Send a modification request for a template (conservative, separate agent)")
def template_chat(
    template_id: str,
    req: TemplateChatRequest,
    db: Session = Depends(get_db),
) -> DatamartResponse:
    """
    Dedicated template modification endpoint using a specialized agent.

    This endpoint is fundamentally different from the main /chat endpoint:

    DESIGN PHILOSOPHY:
    ─────────────────────────────────────────────────────────────────────
    - Conservative modification: never rewrites SQL from scratch
    - Preserve template integrity: original template NEVER changed
    - Prefer post-processing: uses POST_PROCESS instead of SQL rewrites where possible
    - Incremental changes: modifies only what user requested
    - Safe-by-design: validates modifications don't break query structure

    WORKFLOW:
    ─────────────────────────────────────────────────────────────────────
    1. User opens an existing template
    2. User types modification request: "add salary column", "filter by department"
    3. Specialized template agent:
       - Analyzes current template SQL and structure
       - Generates CONSERVATIVE modifications
       - Suggests post-processing for complex changes
       - Returns proposed changes (NOT persisted yet)
    4. User can:
       - Click "Execute" to test the modifications
       - Accept and save as a new template version
       - Reject and try a different modification

    KEY DIFFERENCE FROM MAIN CHAT:
    ─────────────────────────────────────────────────────────────────────
    Main Chat (/chat):
      - Generates SQL from scratch based on questions
      - Optimized for "answer my question" scenarios
      - Can rewrite query entirely if needed

    Template Chat (/templates/{id}/chat):
      - Modifies existing SQL incrementally
      - Optimized for "refine this template" scenarios
      - Avoids breaking changes to data structure
      - Prefers adding transformations over changing SQL
      - Original template never harmed until explicitly saved

    GUARANTEES:
    ─────────────────────────────────────────────────────────────────────
    ✓ Original template version never modified
    ✓ Modifications kept in template session (hidden from sidebar)
    ✓ User must explicitly save to persist changes
    ✓ Each saved version is a snapshot (immutable)
    ✓ Full modification history maintained for context
    """
    tmpl_uuid = _parse_uuid(template_id, "template_id")
    template = get_template(db, tmpl_uuid)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")

    if template.latest_version is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template has no version yet. Cannot modify.",
        )

    # Get or create the hidden session for this template
    session_uuid = get_or_create_template_session(db, tmpl_uuid, get_datamart_user_id())

    # Build enhanced template context with full modification history
    llm_context = build_template_context(
        db=db,
        session_id=session_uuid,
        template_name=template.name,
        template_current_sql=template.latest_version.sql_script,
        template_current_narrative=template.latest_version.narrative,
        template_post_process_config=template.latest_version.post_process_config,
    )

    mode = req.follow_up_mode or FollowUpMode.CONTINUE_LAST
    lv = template.latest_version
    is_add_scenario = mode == FollowUpMode.ADD_SCENARIO
    continue_last = mode in (None, FollowUpMode.CONTINUE_LAST)
    targets = normalize_target_scenario_ids(req.target_scenario_ids)

    # Seed context from saved template when the hidden modify session has no turns yet.
    if llm_context.previous_post_process_config is None and continue_last:
        llm_context = LLMContext(
            history_text=llm_context.history_text,
            next_turn_index=llm_context.next_turn_index,
            previous_post_process_config=lv.post_process_config,
            previous_extra_result_blocks=lv.extra_result_blocks,
            previous_report_layout=(
                dict(lv.report_layout) if isinstance(lv.report_layout, dict) else None
            ),
        )
    elif llm_context.previous_extra_result_blocks is None and lv.extra_result_blocks:
        llm_context = LLMContext(
            history_text=llm_context.history_text,
            next_turn_index=llm_context.next_turn_index,
            previous_post_process_config=llm_context.previous_post_process_config,
            previous_extra_result_blocks=lv.extra_result_blocks,
            previous_report_layout=llm_context.previous_report_layout,
        )

    history_text = llm_context.history_text
    if continue_last and not extract_last_sql_from_history(history_text):
        history_text = (
            f"{history_text}\n\n--- Saved template SQL (modify from this) ---\n"
            f"{lv.sql_script}\n"
        )

    prior_pp = (
        None
        if mode in (FollowUpMode.NEW_QUESTION, FollowUpMode.ADD_SCENARIO)
        else llm_context.previous_post_process_config
    )

    prior_for_scope = get_last_assistant_turn_snapshot(db, session_uuid)
    template_primary_sql = lv.sql_script if lv else None
    tenant_id = get_datamart_tenant_id_from_auth()

    try:
        # Same agent pipeline as /datamart/chat for equal reasoning (schema broker, repairs, post-process).
        result = ask(
            question=req.question,
            history_text=history_text,
            previous_post_process_config=prior_pp,
            follow_up_mode=mode,
            target_scenario_ids=req.target_scenario_ids,
            previous_extra_result_blocks=llm_context.previous_extra_result_blocks,
            previous_primary_sql=(
                prior_for_scope.sql_script
                if prior_for_scope and prior_for_scope.sql_script
                else template_primary_sql
            ),
            tenant_id=tenant_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error in template_chat: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="An unexpected error occurred.") from exc

    prior_snapshot = prior_for_scope
    if not prior_snapshot.sql_script:
        prior_snapshot = LastAssistantSnapshot(
            sql_script=lv.sql_script,
            post_process_config=lv.post_process_config,
            extra_result_blocks=lv.extra_result_blocks,
            report_layout=(
                dict(lv.report_layout) if isinstance(lv.report_layout, dict) else None
            ),
            narrative=lv.narrative,
        )

    if is_add_scenario and prior_snapshot.sql_script:
        llm_primary_sql = result.sql
        result.sql = prior_snapshot.sql_script
        result.post_process_config = prior_snapshot.post_process_config
        primary_exec = _execute_stored_sql_pipeline(
            prior_snapshot.sql_script,
            prior_snapshot.post_process_config,
        )
        if primary_exec.error and not primary_exec.columns:
            result.error = primary_exec.error
        else:
            result.columns = primary_exec.columns
            result.rows = primary_exec.rows
            result.row_count = primary_exec.row_count
            result.raw_columns = primary_exec.raw_columns
            result.raw_rows = primary_exec.raw_rows
            result.raw_row_count = primary_exec.raw_row_count
            if primary_exec.error:
                result.error = primary_exec.error
            elif result.error and primary_exec.columns:
                result.error = None

    merge_previous = (
        prior_snapshot.extra_result_blocks
        if is_add_scenario
        else llm_context.previous_extra_result_blocks
    )
    continue_merge = is_add_scenario or (
        continue_last
        and (
            mode == FollowUpMode.CONTINUE_LAST
            or (
                mode is None
                and (
                    llm_context.previous_post_process_config is not None
                    or llm_context.previous_extra_result_blocks
                )
            )
        )
    )
    extra_meta = merge_extra_result_blocks(
        question=req.question,
        previous=merge_previous,
        new_blocks=result.extra_result_blocks,
        follow_up_continue=bool(continue_merge),
        target_scenario_ids=targets,
    )
    if extra_meta and result.extra_result_blocks:
        new_by_id = {b.block_id: b for b in result.extra_result_blocks if b.sql}
        merged_blocks: list[DatamartResultBlock] = []
        for meta in extra_meta:
            bid = str(meta.get("block_id") or "")
            if bid in new_by_id:
                merged_blocks.append(new_by_id[bid])
            else:
                merged_blocks.append(_result_block_from_merge_meta(meta, None))
        result.extra_result_blocks = merged_blocks or None
    elif continue_last and not result.extra_result_blocks and lv.extra_result_blocks:
        result.extra_result_blocks = _extra_blocks_for_response(lv.extra_result_blocks)

    scope_prior_sql = prior_snapshot.sql_script if prior_snapshot else template_primary_sql
    scope_prior_pp = (
        prior_snapshot.post_process_config
        if prior_snapshot
        else lv.post_process_config
    )
    scope_prior_extras = (
        prior_snapshot.extra_result_blocks
        if prior_snapshot and prior_snapshot.extra_result_blocks
        else lv.extra_result_blocks
    )
    if targets and scope_prior_sql:
        result = apply_target_scope_to_result(
            result,
            targets=targets,
            prior_sql=scope_prior_sql,
            prior_post_process=scope_prior_pp,
            prior_extra_blocks=scope_prior_extras,
            execute_primary=_execute_stored_sql_pipeline,
        )

    report_layout = (
        prior_snapshot.report_layout
        if is_add_scenario and prior_snapshot.report_layout
        else llm_context.previous_report_layout
    )
    if isinstance(report_layout, dict):
        result.report_layout = dict(report_layout)
    elif continue_last and isinstance(lv.report_layout, dict) and not result.report_layout:
        result.report_layout = dict(lv.report_layout)
    elif is_add_scenario:
        result.report_layout = {"schema_version": 1, "view_mode": "stacked", "widgets": []}

    if is_add_scenario and prior_snapshot and prior_snapshot.narrative:
        rl = dict(result.report_layout or {"schema_version": 1, "view_mode": "stacked", "widgets": []})
        rl["primary_narrative"] = prior_snapshot.narrative.strip()
        result.report_layout = rl

    # Execute the modified SQL to show results in the template modification chat
    if result.sql and not result.error:
        try:
            sql_run = ensure_select_limit(
                shrink_outer_limit_for_append_sql(result.sql, result.post_process_config)
            )
            columns, rows, row_count = execute_sql(sql_run, validate_binding=False)
            result.columns = columns
            result.rows = rows
            result.row_count = row_count

            if result.post_process_config:
                result.raw_columns = list(columns)
                result.raw_rows = [list(r) for r in rows]
                result.raw_row_count = row_count
                try:
                    columns, rows = apply_post_processing(
                        columns, rows, result.post_process_config
                    )
                    rows = finalize_datamart_rows_after_post_process(
                        rows, len(result.raw_rows)
                    )
                    result.columns = columns
                    result.rows = rows
                    result.row_count = len(rows)
                except ValueError as pp_exc:
                    result.error = f"Post-processing warning: {pp_exc}"
                    result.raw_columns = None
                    result.raw_rows = None
                    result.raw_row_count = None
        except RuntimeError as exec_exc:
            # SQL execution failed: include the error but keep the modification suggestion
            result.error = str(exec_exc)
            result.columns = []
            result.rows = []
            result.row_count = 0

    # Append the modification request and response to the template session
    # (not persisting to the template itself — just conversation history)
    if not result.error or result.narrative:
        extra_meta: Optional[list[dict]] = None
        if result.extra_result_blocks:
            extra_meta = []
            for b in result.extra_result_blocks:
                if not b.sql:
                    continue
                meta_item: dict = {
                    "block_id": b.block_id,
                    "title": b.title,
                    "sql_script": b.sql,
                    "post_process_config": b.post_process_config,
                }
                if b.validation:
                    meta_item["validation"] = b.validation
                if b.pipeline_trace is not None:
                    meta_item["pipeline_trace"] = b.pipeline_trace.model_dump(mode="json")
                extra_meta.append(meta_item)
            if not extra_meta:
                extra_meta = None

        turn_result = append_turn(
            db=db,
            session_id=session_uuid,
            question=req.question,
            narrative=result.narrative,
            sql_script=result.sql,
            post_process_config=result.post_process_config,
            extra_result_blocks=extra_meta,
            follow_up_mode=mode.value if mode is not None else None,
            report_layout=(
                dict(result.report_layout)
                if isinstance(result.report_layout, dict)
                else None
            ),
            validation=_validation_to_json(result),
        )
        result.message_id = turn_result.assistant_message_id

    result.session_id = str(session_uuid)
    return result


# ── Template groups ───────────────────────────────────────────────

@router.get("/template-groups", response_model=TemplateGroupListResponse,
            summary="List all template groups")
def list_template_groups_endpoint(
    db: Session = Depends(get_db),
) -> TemplateGroupListResponse:
    groups = list_template_groups(db, user_id=get_datamart_user_id())
    return TemplateGroupListResponse(
        groups=[_template_group_response(g) for g in groups],
    )


@router.post("/template-groups", response_model=TemplateGroupResponse,
             status_code=status.HTTP_201_CREATED, summary="Create a template group")
def create_template_group_endpoint(
    req: TemplateGroupCreateRequest,
    db: Session = Depends(get_db),
) -> TemplateGroupResponse:
    g = create_template_group(db, user_id=get_datamart_user_id(), name=req.name)
    return _template_group_response(g)


@router.patch("/template-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT,
              summary="Rename a template group")
def rename_template_group_endpoint(
    group_id: str, req: TemplateGroupRenameRequest,
    db: Session = Depends(get_db),
) -> None:
    rename_template_group(db, _parse_uuid(group_id, "group_id"), req.name)


@router.delete("/template-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a template group (templates become ungrouped)")
def delete_template_group_endpoint(
    group_id: str,
    db: Session = Depends(get_db),
) -> None:
    delete_template_group(db, _parse_uuid(group_id, "group_id"))


# ── Suggestions ───────────────────────────────────────────────────

@router.get("/suggestions", response_model=SuggestionsResponse,
            summary="Get sample questions for the empty-state UI")
def get_suggestions() -> SuggestionsResponse:
    return SuggestionsResponse(questions=SAMPLE_QUESTIONS)
