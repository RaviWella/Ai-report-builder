"""Resolve per-turn flags and broker context before schema link."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..orchestration.intent_router import ChatIntent, classify_chat_intent
from ..llm.llm_response import extract_last_sql_from_history
from ..models import FollowUpMode
from ..orchestration.modify_mode import is_modify_turn, resolve_anchor_sql
from ..domain_sql.report_spec import ReportSpec, compile_report_spec
from ..scenario.scenario_scope import PRIMARY_SCENARIO_ID, normalize_target_scenario_ids
from ..scenario.scenario_history import format_add_scenario_history
from .. import config as dm_config


@dataclass
class ChatTurnSetup:
    question: str
    history_text: str
    targets: list[str]
    is_new_question: bool
    is_add_scenario: bool
    is_modify: bool
    anchor_sql: Optional[str]
    prior_pp: Optional[list[dict]]
    broker_last_sql: Optional[str]
    chat_intent: ChatIntent
    report_spec: Optional[ReportSpec]
    last_sql: Optional[str]


def build_turn_setup(
    *,
    question: str,
    history_text: str,
    follow_up_mode: Optional[FollowUpMode],
    target_scenario_ids: Optional[list[str]],
    previous_post_process_config: Optional[list[dict]],
    previous_primary_sql: Optional[str],
) -> ChatTurnSetup:
    last_sql = extract_last_sql_from_history(history_text)
    targets = normalize_target_scenario_ids(target_scenario_ids)
    is_new_question = follow_up_mode == FollowUpMode.NEW_QUESTION
    is_add_scenario = follow_up_mode == FollowUpMode.ADD_SCENARIO
    is_modify = is_modify_turn(
        follow_up_mode,
        is_new_question=is_new_question,
        is_add_scenario=is_add_scenario,
    )
    if is_add_scenario:
        history_text = format_add_scenario_history(history_text)

    anchor_sql = (
        resolve_anchor_sql(
            previous_primary_sql=previous_primary_sql,
            last_sql=last_sql,
            targets=targets,
        )
        if is_modify
        else None
    )
    prior_pp = None if (is_new_question or is_add_scenario) else previous_post_process_config
    if targets and PRIMARY_SCENARIO_ID not in targets:
        prior_pp = None

    if is_new_question or is_add_scenario:
        broker_last_sql = None
    elif anchor_sql:
        broker_last_sql = anchor_sql
    else:
        broker_last_sql = last_sql
        if targets and previous_primary_sql and PRIMARY_SCENARIO_ID in targets:
            broker_last_sql = previous_primary_sql
        elif targets and PRIMARY_SCENARIO_ID not in targets:
            broker_last_sql = None

    chat_intent = classify_chat_intent(
        question,
        last_sql=broker_last_sql,
        has_prior_post_process=bool(prior_pp),
        follow_up_mode=follow_up_mode,
    )
    report_spec = (
        compile_report_spec(question, chat_intent=chat_intent)
        if dm_config.DATAMART_REPORT_SPEC_ENABLED
        else None
    )

    return ChatTurnSetup(
        question=question,
        history_text=history_text,
        targets=targets,
        is_new_question=is_new_question,
        is_add_scenario=is_add_scenario,
        is_modify=is_modify,
        anchor_sql=anchor_sql,
        prior_pp=prior_pp,
        broker_last_sql=broker_last_sql,
        chat_intent=chat_intent,
        report_spec=report_spec,
        last_sql=last_sql,
    )
