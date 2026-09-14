"""
Datamart AI Service — public facade
=====================================
Thin entry points for workspace chat and template modification.

Chat uses a simple pipeline: semantic YAML + DataHub + warehouse introspection → LLM SQL → execute.
"""
from __future__ import annotations

from typing import Callable, Optional

from .chat_pipeline import run_chat_pipeline
from .pipeline_events import reset_pipeline_listener, set_pipeline_listener
from .pipeline_trace import PipelineTrace
from .workspace.auth_context import get_datamart_tenant_id_from_auth
from .llm.llm_response import build_history_text, merge_post_process_configs
from .models import DatamartResponse, FollowUpMode
from .workspace.runtime_context import run_with_datamart_context
from .orchestration.template_pipeline import run_template_modification_pipeline
from .orchestration.template_sql_guard import preserve_order_by_from_template
from .sql.sql_refs import warehouse_table_names_from_sql

__all__ = [
    "ask",
    "ask_template_modification",
    "build_history_text",
    "merge_post_process_configs",
    "preserve_order_by_from_template",
    "warehouse_table_names_from_sql",
]


def ask(
    question: str,
    history: list[dict] | None = None,
    history_text: str | None = None,
    previous_post_process_config: Optional[list[dict]] = None,
    follow_up_mode: Optional[FollowUpMode] = None,
    target_scenario_ids: Optional[list[str]] = None,
    previous_extra_result_blocks: Optional[list[dict]] = None,
    previous_primary_sql: Optional[str] = None,
    confirmed_table_names: Optional[list[str]] = None,
    tenant_id: Optional[str] = None,
    on_pipeline_update: Optional[Callable[[PipelineTrace], None]] = None,
) -> DatamartResponse:
    if history_text is not None:
        resolved_history = history_text
    elif history:
        resolved_history = build_history_text(history)
    else:
        resolved_history = "(No previous messages)"

    tid = (tenant_id or get_datamart_tenant_id_from_auth()).strip()

    def _run() -> DatamartResponse:
        token = set_pipeline_listener(on_pipeline_update)
        try:
            return run_with_datamart_context(
                tid,
                run_chat_pipeline,
                question,
                resolved_history,
                previous_post_process_config,
                follow_up_mode,
                target_scenario_ids,
                previous_extra_result_blocks,
                previous_primary_sql,
                confirmed_table_names,
            )
        finally:
            reset_pipeline_listener(token)

    return _run()


def ask_template_modification(
    question: str,
    history_text: str,
    template_sql: str,
    template_narrative: str,
    template_post_process_config: Optional[list[dict]] = None,
    tenant_id: Optional[str] = None,
) -> DatamartResponse:
    tid = (tenant_id or get_datamart_tenant_id_from_auth()).strip()
    return run_with_datamart_context(
        tid,
        run_template_modification_pipeline,
        question,
        history_text,
        template_sql,
        template_narrative,
        template_post_process_config,
    )
