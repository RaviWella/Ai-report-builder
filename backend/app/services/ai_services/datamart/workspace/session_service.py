"""
Datamart Chat — Session & History Service
==========================================
All database operations for sessions, messages, and summaries.

Responsibilities:
  - Create / list / rename / soft-delete sessions
  - Append message pairs (user + assistant) to a session
  - Build LLM context (with rolling summarisation when needed)
  - Trigger summarisation when unsummarised turn count exceeds the limit

Public API (all async):
  create_session(db, user_id, title) -> DatamartChatSession
  list_sessions(db, user_id)         -> list[SessionSummary]
  get_session(db, session_id)        -> DatamartChatSession | None
  rename_session(db, session_id, title)
  delete_session(db, session_id)
  get_messages(db, session_id)       -> list[DatamartChatMessage]
  append_turn(db, session_id, question, narrative, sql)
  build_llm_context(db, session_id)  -> LLMContext
"""
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import delete, select, update, func as sa_func
from sqlalchemy.orm import Session

from app.models.datamart_chat import (
    DatamartChatMessage,
    DatamartChatSession,
    DatamartChatSummary,
)
from ..config import AI_PROXY_MODEL
from ..llm.llm_client import get_llm
from .workspace_scope import resolve_workspace_tenant_id

logger = logging.getLogger("ai_services.datamart")

# ── Constants ─────────────────────────────────────────────────────

# Number of unsummarised turns to keep in full before triggering summarisation.
CONTEXT_TURN_LIMIT: int = 10

# Max JSON chars per message for POST_PROCESS in LLM history (keeps tail in budget).
_HISTORY_POST_PROCESS_JSON_MAX_CHARS: int = 1_200

# Fallback when request auth context is missing (tests / scripts only).
DEFAULT_USER_ID: str = "default-user"


# ── Data transfer objects ─────────────────────────────────────────

@dataclass
class SessionListItem:
    """Lightweight session descriptor for the sidebar list."""
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    group_id: Optional[str] = None


@dataclass
class MessageDTO:
    """Single message turn for the frontend."""
    id: str
    role: str
    content: str
    sql_script: Optional[str]
    question_ref: Optional[str]
    post_process_config: Optional[list[dict]]
    chart_configs: Optional[list[dict]]
    extra_result_blocks: Optional[list[dict]]
    turn_index: int
    is_summarised: bool
    created_at: str
    follow_up_mode: Optional[str] = None
    report_layout: Optional[dict] = None
    validation: Optional[dict] = None


@dataclass
class UndoLastModificationResult:
    """Result of removing the last continue_last modification turn."""

    removed_turn_index: int
    restored_turn_index: int
    restored_assistant_message_id: Optional[str]


@dataclass
class LLMContext:
    """
    Assembled context passed to the agent for generating the next response.

    history_text: formatted string of recent turns for the LLM prompt
    next_turn_index: the turn_index to use for the new message pair
    previous_post_process_config: POST_PROCESS from the latest assistant message (if any)
    """
    history_text: str
    next_turn_index: int
    previous_post_process_config: Optional[list[dict]] = None
    previous_extra_result_blocks: Optional[list[dict]] = None
    previous_report_layout: Optional[dict] = None


# ── Session CRUD ──────────────────────────────────────────────────

def create_session(
    db: Session,
    user_id: str = DEFAULT_USER_ID,
    title: str = "New conversation",
    *,
    tenant_id: Optional[str] = None,
) -> DatamartChatSession:
    """Create and persist a new chat session."""
    tid = resolve_workspace_tenant_id(tenant_id)
    session = DatamartChatSession(
        id=uuid.uuid4(),
        tenant_id=tid,
        user_id=user_id,
        title=title,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("Created session %s for user %s", session.id, user_id)
    return session


def list_sessions(
    db: Session,
    user_id: str = DEFAULT_USER_ID,
    *,
    tenant_id: Optional[str] = None,
) -> list[SessionListItem]:
    tid = resolve_workspace_tenant_id(tenant_id)
    """
    Return all active sessions for a user, newest first.
    Includes a message count per session.
    """
    # Subquery: count messages per session
    msg_count_sq = (
        select(
            DatamartChatMessage.session_id,
            sa_func.count(DatamartChatMessage.id).label("cnt"),
        )
        .group_by(DatamartChatMessage.session_id)
        .subquery()
    )

    stmt = (
        select(
            DatamartChatSession,
            sa_func.coalesce(msg_count_sq.c.cnt, 0).label("message_count"),
        )
        .outerjoin(
            msg_count_sq,
            DatamartChatSession.id == msg_count_sq.c.session_id,
        )
        .where(
            DatamartChatSession.tenant_id == tid,
            DatamartChatSession.user_id == user_id,
            DatamartChatSession.is_active.is_(True),
        )
        .order_by(DatamartChatSession.updated_at.desc())
    )

    result = db.execute(stmt)
    rows = result.all()

    return [
        SessionListItem(
            id=str(row.DatamartChatSession.id),
            title=row.DatamartChatSession.title,
            created_at=row.DatamartChatSession.created_at.isoformat(),
            updated_at=row.DatamartChatSession.updated_at.isoformat(),
            message_count=row.message_count,
            group_id=str(row.DatamartChatSession.group_id) if row.DatamartChatSession.group_id else None,
        )
        for row in rows
    ]


def get_session(
    db: Session,
    session_id: uuid.UUID,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[DatamartChatSession]:
    """Fetch a single session by ID. Returns None if not found, soft-deleted, or wrong user."""
    clauses = [
        DatamartChatSession.id == session_id,
        DatamartChatSession.is_active.is_(True),
    ]
    tid = resolve_workspace_tenant_id(tenant_id)
    clauses.append(DatamartChatSession.tenant_id == tid)
    if user_id is not None:
        clauses.append(DatamartChatSession.user_id == user_id)
    result = db.execute(select(DatamartChatSession).where(*clauses))
    return result.scalar_one_or_none()


def rename_session(
    db: Session,
    session_id: uuid.UUID,
    title: str,
    *,
    tenant_id: Optional[str] = None,
) -> None:
    """Update the title of a session."""
    tid = resolve_workspace_tenant_id(tenant_id)
    db.execute(
        update(DatamartChatSession)
        .where(
            DatamartChatSession.id == session_id,
            DatamartChatSession.tenant_id == tid,
        )
        .values(title=title)
    )
    db.commit()


def delete_session(
    db: Session,
    session_id: uuid.UUID,
    *,
    tenant_id: Optional[str] = None,
) -> None:
    """Soft-delete a session (sets is_active=False)."""
    tid = resolve_workspace_tenant_id(tenant_id)
    db.execute(
        update(DatamartChatSession)
        .where(
            DatamartChatSession.id == session_id,
            DatamartChatSession.tenant_id == tid,
        )
        .values(is_active=False)
    )
    db.commit()
    logger.info("Soft-deleted session %s", session_id)


# ── Message operations ────────────────────────────────────────────

def get_messages(
    db: Session,
    session_id: uuid.UUID,
) -> list[MessageDTO]:
    """
    Return all messages for a session ordered by turn_index then role.
    Summarised messages are included — the frontend always shows the full history.
    """
    result = db.execute(
        select(DatamartChatMessage)
        .where(DatamartChatMessage.session_id == session_id)
        .order_by(
            DatamartChatMessage.turn_index.asc(),
            DatamartChatMessage.role.asc(),  # 'assistant' < 'user' alphabetically → user first
        )
    )
    messages = result.scalars().all()

    return [
        MessageDTO(
            id=str(m.id),
            role=m.role,
            content=m.content,
            sql_script=m.sql_script,
            question_ref=m.question_ref,
            post_process_config=m.post_process_config,
            chart_configs=m.chart_configs,
            extra_result_blocks=m.extra_result_blocks,
            turn_index=m.turn_index,
            is_summarised=m.is_summarised,
            created_at=m.created_at.isoformat(),
            follow_up_mode=m.follow_up_mode,
            report_layout=m.report_layout,
            validation=m.validation if isinstance(m.validation, dict) else None,
        )
        for m in messages
    ]


@dataclass
class LastAssistantSnapshot:
    """Prior assistant turn state used when adding a scenario to the same report."""

    sql_script: Optional[str] = None
    post_process_config: Optional[list[dict]] = None
    extra_result_blocks: Optional[list[dict]] = None
    report_layout: Optional[dict] = None
    narrative: Optional[str] = None


def get_last_assistant_turn_snapshot(
    db: Session,
    session_id: uuid.UUID,
) -> LastAssistantSnapshot:
    """Load the latest unsummarised assistant message in the session."""
    result = db.execute(
        select(DatamartChatMessage)
        .where(
            DatamartChatMessage.session_id == session_id,
            DatamartChatMessage.role == "assistant",
            DatamartChatMessage.is_summarised.is_(False),
        )
        .order_by(DatamartChatMessage.turn_index.desc())
        .limit(1)
    )
    msg = result.scalar_one_or_none()
    if msg is None:
        return LastAssistantSnapshot()
    return LastAssistantSnapshot(
        sql_script=msg.sql_script,
        post_process_config=(
            list(msg.post_process_config) if msg.post_process_config else None
        ),
        extra_result_blocks=(
            list(msg.extra_result_blocks) if msg.extra_result_blocks else None
        ),
        report_layout=dict(msg.report_layout) if isinstance(msg.report_layout, dict) else None,
        narrative=msg.content,
    )


@dataclass
class PagedMessagesResult:
    """Result of a paginated message fetch."""
    messages: list[MessageDTO]
    total_turns: int       # total distinct turn_index values in the session
    page: int
    page_size: int         # number of turns per page (not raw rows)
    has_more: bool         # True if older pages exist


def get_messages_paged(
    db: Session,
    session_id: uuid.UUID,
    page: int = 1,
    page_size: int = 5,
) -> PagedMessagesResult:
    """
    Return a page of conversation turns for a session.

    Pagination is turn-based (not row-based): each "page" contains
    `page_size` turns, where each turn = 1 user row + 1 assistant row.

    page=1 returns the MOST RECENT turns (bottom of chat).
    page=2 returns the next older batch, etc.
    This matches the "infinite scroll upward" UX pattern.

    Parameters
    ----------
    page      : 1-based page number (1 = most recent)
    page_size : number of turns per page (default 5)
    """
    # Count total distinct turns
    count_result = db.execute(
        select(sa_func.count(sa_func.distinct(DatamartChatMessage.turn_index)))
        .where(DatamartChatMessage.session_id == session_id)
    )
    total_turns: int = count_result.scalar_one() or 0

    # Fetch the turn_indices for this page (newest first, then reverse for display)
    # OFFSET from the end: page=1 → last page_size turns
    offset = (page - 1) * page_size
    turn_idx_result = db.execute(
        select(sa_func.distinct(DatamartChatMessage.turn_index))
        .where(DatamartChatMessage.session_id == session_id)
        .order_by(DatamartChatMessage.turn_index.desc())
        .limit(page_size)
        .offset(offset)
    )
    turn_indices = [row[0] for row in turn_idx_result.all()]

    if not turn_indices:
        return PagedMessagesResult(
            messages=[],
            total_turns=total_turns,
            page=page,
            page_size=page_size,
            has_more=False,
        )

    # Fetch all rows for these turn_indices, ordered ascending for display
    msg_result = db.execute(
        select(DatamartChatMessage)
        .where(
            DatamartChatMessage.session_id == session_id,
            DatamartChatMessage.turn_index.in_(turn_indices),
        )
        .order_by(
            DatamartChatMessage.turn_index.asc(),
            DatamartChatMessage.role.asc(),
        )
    )
    messages = msg_result.scalars().all()

    has_more = (offset + page_size) < total_turns

    return PagedMessagesResult(
        messages=[
            MessageDTO(
                id=str(m.id),
                role=m.role,
                content=m.content,
                sql_script=m.sql_script,
                question_ref=m.question_ref,
                post_process_config=m.post_process_config,
                chart_configs=m.chart_configs,
                extra_result_blocks=m.extra_result_blocks,
                turn_index=m.turn_index,
                is_summarised=m.is_summarised,
                created_at=m.created_at.isoformat(),
                follow_up_mode=m.follow_up_mode,
                report_layout=m.report_layout,
                validation=m.validation if isinstance(m.validation, dict) else None,
            )
            for m in messages
        ],
        total_turns=total_turns,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


def get_message_by_id(
    db: Session,
    message_id: uuid.UUID,
    session_id: uuid.UUID,
) -> Optional[MessageDTO]:
    """
    Fetch a single message by ID, scoped to a session for security.
    Returns None if not found or belongs to a different session.
    """
    result = db.execute(
        select(DatamartChatMessage).where(
            DatamartChatMessage.id == message_id,
            DatamartChatMessage.session_id == session_id,
        )
    )
    m = result.scalar_one_or_none()
    if m is None:
        return None
    return MessageDTO(
        id=str(m.id),
        role=m.role,
        content=m.content,
        sql_script=m.sql_script,
        question_ref=m.question_ref,
        post_process_config=m.post_process_config,
        chart_configs=m.chart_configs,
        extra_result_blocks=m.extra_result_blocks,
        turn_index=m.turn_index,
        is_summarised=m.is_summarised,
        created_at=m.created_at.isoformat(),
        follow_up_mode=m.follow_up_mode,
        report_layout=m.report_layout,
        validation=m.validation if isinstance(m.validation, dict) else None,
    )


def _get_next_turn_index(db: Session, session_id: uuid.UUID) -> int:
    """Return the next sequential turn_index for a session (1-based)."""
    result = db.execute(
        select(sa_func.max(DatamartChatMessage.turn_index)).where(
            DatamartChatMessage.session_id == session_id
        )
    )
    max_turn = result.scalar_one_or_none()
    return (max_turn or 0) + 1


@dataclass
class AppendTurnResult:
    """Result of appending a turn to a session."""
    turn_index: int
    assistant_message_id: str


def session_has_turn(
    db: Session,
    session_id: uuid.UUID,
    turn_index: int,
) -> bool:
    """True if the session has a user message at ``turn_index``."""
    result = db.execute(
        select(DatamartChatMessage.id)
        .where(
            DatamartChatMessage.session_id == session_id,
            DatamartChatMessage.turn_index == turn_index,
            DatamartChatMessage.role == "user",
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


def delete_turns_from(
    db: Session,
    session_id: uuid.UUID,
    from_turn_index: int,
) -> int:
    """
    Remove a turn and all subsequent turns (user + assistant rows).

    Also drops rolling summaries that only covered deleted turns so LLM context
    stays consistent after edit-and-resend.
    """
    db.execute(
        delete(DatamartChatSummary).where(
            DatamartChatSummary.session_id == session_id,
            DatamartChatSummary.covers_up_to_turn >= from_turn_index,
        )
    )
    result = db.execute(
        delete(DatamartChatMessage).where(
            DatamartChatMessage.session_id == session_id,
            DatamartChatMessage.turn_index >= from_turn_index,
        )
    )
    db.execute(
        update(DatamartChatSession)
        .where(DatamartChatSession.id == session_id)
        .values(updated_at=sa_func.now())
    )
    db.commit()
    deleted = int(result.rowcount or 0)
    logger.info(
        "Deleted %d message(s) from session %s at turn_index>=%d",
        deleted,
        session_id,
        from_turn_index,
    )
    return deleted


def get_max_turn_index(
    db: Session,
    session_id: uuid.UUID,
) -> Optional[int]:
    """Highest turn_index in the session, or None if empty."""
    result = db.execute(
        select(sa_func.max(DatamartChatMessage.turn_index)).where(
            DatamartChatMessage.session_id == session_id,
        )
    )
    value = result.scalar_one_or_none()
    return int(value) if value is not None else None


def get_assistant_turn_snapshot(
    db: Session,
    session_id: uuid.UUID,
    turn_index: int,
) -> tuple[Optional[dict], Optional[str]]:
    """Return (validation_json, sql_script) for an assistant message at a turn."""
    result = db.execute(
        select(
            DatamartChatMessage.validation,
            DatamartChatMessage.sql_script,
        ).where(
            DatamartChatMessage.session_id == session_id,
            DatamartChatMessage.turn_index == turn_index,
            DatamartChatMessage.role == "assistant",
        )
    )
    row = result.one_or_none()
    if row is None:
        return None, None
    val, sql = row
    return (val if isinstance(val, dict) else None), sql


def get_clarification_anchor_question(
    db: Session,
    session_id: uuid.UUID,
) -> Optional[str]:
    """
    When the latest assistant turn is awaiting clarification, return the anchor question
    to merge with the user's reply.
    """
    from ..orchestration.clarification_flow import (
        anchor_question_from_validation,
        validation_awaiting_clarification,
    )

    max_turn = get_max_turn_index(db, session_id)
    if max_turn is None:
        return None
    validation, sql_script = get_assistant_turn_snapshot(db, session_id, max_turn)
    if sql_script:
        return None
    if not validation_awaiting_clarification(validation):
        return None
    user_q = get_user_question_at_turn(db, session_id, max_turn)
    return anchor_question_from_validation(validation, fallback_user_question=user_q)


def get_user_question_at_turn(
    db: Session,
    session_id: uuid.UUID,
    turn_index: int,
) -> Optional[str]:
    result = db.execute(
        select(DatamartChatMessage.content).where(
            DatamartChatMessage.session_id == session_id,
            DatamartChatMessage.turn_index == turn_index,
            DatamartChatMessage.role == "user",
        )
    )
    return result.scalar_one_or_none()


def get_user_follow_up_mode_at_turn(
    db: Session,
    session_id: uuid.UUID,
    turn_index: int,
) -> Optional[str]:
    result = db.execute(
        select(DatamartChatMessage.follow_up_mode).where(
            DatamartChatMessage.session_id == session_id,
            DatamartChatMessage.turn_index == turn_index,
            DatamartChatMessage.role == "user",
        )
    )
    return result.scalar_one_or_none()


def get_assistant_message_id_at_turn(
    db: Session,
    session_id: uuid.UUID,
    turn_index: int,
) -> Optional[uuid.UUID]:
    result = db.execute(
        select(DatamartChatMessage.id).where(
            DatamartChatMessage.session_id == session_id,
            DatamartChatMessage.turn_index == turn_index,
            DatamartChatMessage.role == "assistant",
        )
    )
    return result.scalar_one_or_none()


def undo_last_modification(
    db: Session,
    session_id: uuid.UUID,
) -> UndoLastModificationResult:
    """
    Remove the latest turn when it was a continue_last modification.

    Restores the prior assistant response as the latest message in the session.
    """
    max_turn = get_max_turn_index(db, session_id)
    if max_turn is None or max_turn < 2:
        raise ValueError("No modification to undo.")

    mode = get_user_follow_up_mode_at_turn(db, session_id, max_turn)
    if mode == "new_question":
        raise ValueError("The last message is a new question, not a modification to undo.")

    restored_turn = max_turn - 1
    restored_id = get_assistant_message_id_at_turn(
        db, session_id, restored_turn,
    )

    deleted = delete_turns_from(db, session_id, max_turn)
    if deleted < 1:
        raise ValueError("Could not remove the last modification.")

    return UndoLastModificationResult(
        removed_turn_index=max_turn,
        restored_turn_index=restored_turn,
        restored_assistant_message_id=str(restored_id) if restored_id else None,
    )


def append_turn(
    db: Session,
    session_id: uuid.UUID,
    question: str,
    narrative: str,
    sql_script: Optional[str] = None,
    post_process_config: Optional[list[dict]] = None,
    extra_result_blocks: Optional[list[dict]] = None,
    follow_up_mode: Optional[str] = None,
    report_layout: Optional[dict] = None,
    validation: Optional[dict] = None,
) -> AppendTurnResult:
    """
    Persist a user+assistant message pair for one conversation turn.

    Returns an AppendTurnResult with the turn_index and the assistant message UUID,
    so the caller can include the message_id in the API response (needed for
    "Move to Template" on fresh messages).
    Also auto-generates the session title from the first question.
    """
    turn_index = _get_next_turn_index(db, session_id)
    assistant_id = uuid.uuid4()

    # User message
    user_msg = DatamartChatMessage(
        id=uuid.uuid4(),
        session_id=session_id,
        role="user",
        content=question,
        turn_index=turn_index,
        follow_up_mode=follow_up_mode
        if follow_up_mode
        in ("continue_last", "new_question", "add_scenario", "clarify_reply")
        else None,
    )

    # Assistant message — includes sql_script, question_ref, and post_process_config
    assistant_msg = DatamartChatMessage(
        id=assistant_id,
        session_id=session_id,
        role="assistant",
        content=narrative,
        sql_script=sql_script,
        question_ref=question,
        post_process_config=post_process_config,
        extra_result_blocks=extra_result_blocks,
        report_layout=report_layout,
        validation=validation,
        turn_index=turn_index,
    )

    db.add(user_msg)
    db.add(assistant_msg)

    # Auto-title the session from the first question (first 60 chars)
    if turn_index == 1:
        short_title = question[:60].rstrip() + ("…" if len(question) > 60 else "")
        db.execute(
            update(DatamartChatSession)
            .where(DatamartChatSession.id == session_id)
            .values(title=short_title, updated_at=sa_func.now())
        )
    else:
        db.execute(
            update(DatamartChatSession)
            .where(DatamartChatSession.id == session_id)
            .values(updated_at=sa_func.now())
        )

    db.commit()
    logger.debug("Appended turn %d to session %s", turn_index, session_id)
    return AppendTurnResult(turn_index=turn_index, assistant_message_id=str(assistant_id))


def update_assistant_message_charts(
    db: Session,
    session_id: uuid.UUID,
    message_id: uuid.UUID,
    chart_configs: Optional[list[dict]],
) -> bool:
    """
    Replace chart JSON on an assistant message. ``chart_configs`` may be [] to clear.

    Returns False if the message is missing, belongs to another session, or is not assistant.
    """
    result = db.execute(
        select(DatamartChatMessage).where(
            DatamartChatMessage.id == message_id,
            DatamartChatMessage.session_id == session_id,
        )
    )
    msg = result.scalar_one_or_none()
    if msg is None or msg.role != "assistant":
        return False
    db.execute(
        update(DatamartChatMessage)
        .where(DatamartChatMessage.id == message_id)
        .values(chart_configs=chart_configs)
    )
    db.commit()
    logger.debug("Updated chart_configs on message %s", message_id)
    return True


def update_assistant_report_meta(
    db: Session,
    session_id: uuid.UUID,
    message_id: uuid.UUID,
    *,
    report_layout: Optional[dict] = None,
    primary_label: Optional[str] = None,
    block_labels: Optional[dict[str, str]] = None,
) -> Optional[DatamartChatMessage]:
    """
    Update scenario labels and/or report canvas layout on an assistant message.

    Returns the updated ORM row, or None if not found / not assistant.
    """
    result = db.execute(
        select(DatamartChatMessage).where(
            DatamartChatMessage.id == message_id,
            DatamartChatMessage.session_id == session_id,
        )
    )
    msg = result.scalar_one_or_none()
    if msg is None or msg.role != "assistant":
        return None

    layout: dict = {}
    if isinstance(msg.report_layout, dict):
        layout = dict(msg.report_layout)
    if report_layout is not None and isinstance(report_layout, dict):
        layout = {**layout, **report_layout}
    if primary_label is not None:
        layout["primary_label"] = primary_label.strip() or None
    if layout:
        layout.setdefault("schema_version", 1)
        msg.report_layout = layout

    if block_labels:
        blocks = list(msg.extra_result_blocks or [])
        changed = False
        for blk in blocks:
            if not isinstance(blk, dict):
                continue
            bid = str(blk.get("block_id") or "")
            if bid in block_labels:
                blk["title"] = block_labels[bid].strip() or blk.get("title")
                changed = True
        if changed:
            msg.extra_result_blocks = blocks

    db.commit()
    db.refresh(msg)
    return msg


# ── LLM context builder ───────────────────────────────────────────

def build_llm_context(
    db: Session,
    session_id: uuid.UUID,
) -> LLMContext:
    """
    Build the history text to include in the LLM prompt.

    Strategy:
      1. Count unsummarised turns.
      2. If count > CONTEXT_TURN_LIMIT, summarise the oldest turns first.
      3. Return: [latest summary if any] + [last CONTEXT_TURN_LIMIT full turns]

    SQL scripts are always included in the context so the LLM knows
    which query was generated for each question.
    """
    # Fetch all unsummarised messages ordered by turn
    result = db.execute(
        select(DatamartChatMessage)
        .where(
            DatamartChatMessage.session_id == session_id,
            DatamartChatMessage.is_summarised.is_(False),
        )
        .order_by(DatamartChatMessage.turn_index.asc())
    )
    unsummarised = result.scalars().all()

    # Group into turns: {turn_index: {user: msg, assistant: msg}}
    turns: dict[int, dict] = {}
    for msg in unsummarised:
        if msg.turn_index not in turns:
            turns[msg.turn_index] = {}
        turns[msg.turn_index][msg.role] = msg

    sorted_turn_indices = sorted(turns.keys())
    next_turn_index = (sorted_turn_indices[-1] + 1) if sorted_turn_indices else 1

    previous_post_process_config: Optional[list[dict]] = None
    previous_extra_result_blocks: Optional[list[dict]] = None
    previous_report_layout: Optional[dict] = None
    if sorted_turn_indices:
        last_turn = turns[sorted_turn_indices[-1]]
        last_asst = last_turn.get("assistant")
        if last_asst:
            if last_asst.post_process_config:
                previous_post_process_config = list(last_asst.post_process_config)
            if last_asst.extra_result_blocks:
                previous_extra_result_blocks = [
                    b for b in last_asst.extra_result_blocks if isinstance(b, dict)
                ]
            if isinstance(last_asst.report_layout, dict):
                previous_report_layout = dict(last_asst.report_layout)

    # Trigger summarisation if needed
    if len(sorted_turn_indices) > CONTEXT_TURN_LIMIT:
        turns_to_summarise = sorted_turn_indices[:-CONTEXT_TURN_LIMIT]
        _summarise_turns(db, session_id, turns, turns_to_summarise)

        # Reload after summarisation
        result = db.execute(
            select(DatamartChatMessage)
            .where(
                DatamartChatMessage.session_id == session_id,
                DatamartChatMessage.is_summarised.is_(False),
            )
            .order_by(DatamartChatMessage.turn_index.asc())
        )
        unsummarised = result.scalars().all()
        turns = {}
        for msg in unsummarised:
            if msg.turn_index not in turns:
                turns[msg.turn_index] = {}
            turns[msg.turn_index][msg.role] = msg
        sorted_turn_indices = sorted(turns.keys())
        previous_post_process_config = None
        previous_extra_result_blocks = None
        previous_report_layout = None
        if sorted_turn_indices:
            last_turn = turns[sorted_turn_indices[-1]]
            last_asst = last_turn.get("assistant")
            if last_asst:
                if last_asst.post_process_config:
                    previous_post_process_config = list(last_asst.post_process_config)
                if last_asst.extra_result_blocks:
                    previous_extra_result_blocks = [
                        b for b in last_asst.extra_result_blocks if isinstance(b, dict)
                    ]
                if isinstance(last_asst.report_layout, dict):
                    previous_report_layout = dict(last_asst.report_layout)

    # Fetch the latest summary (if any)
    summary_result = db.execute(
        select(DatamartChatSummary)
        .where(DatamartChatSummary.session_id == session_id)
        .order_by(DatamartChatSummary.covers_up_to_turn.desc())
        .limit(1)
    )
    latest_summary = summary_result.scalar_one_or_none()

    # Build the history text
    parts: list[str] = []

    if latest_summary:
        parts.append(
            f"[Summary of earlier conversation]\n{latest_summary.summary_text}\n"
        )

    for turn_idx in sorted_turn_indices:
        turn = turns[turn_idx]
        user_msg = turn.get("user")
        asst_msg = turn.get("assistant")

        if user_msg:
            parts.append(f"User: {user_msg.content}")
        if asst_msg:
            narrative = (asst_msg.content or "").strip()
            if len(narrative) > 320:
                narrative = narrative[:320].rstrip() + "…"
            parts.append(f"Assistant: {narrative}")
            if asst_msg.sql_script:
                parts.append(f"[SQL turn {turn_idx}]\n```sql\n{asst_msg.sql_script}\n```")
            if asst_msg.post_process_config:
                pp_json = json.dumps(asst_msg.post_process_config, indent=2)
                if len(pp_json) > _HISTORY_POST_PROCESS_JSON_MAX_CHARS:
                    pp_json = (
                        pp_json[:_HISTORY_POST_PROCESS_JSON_MAX_CHARS].rstrip()
                        + "\n... [POST_PROCESS JSON truncated]"
                    )
                parts.append(
                    "[POST_PROCESS steps applied to that SQL result]\n"
                    f"```json\n{pp_json}\n```"
                )
            if asst_msg.extra_result_blocks:
                for blk in asst_msg.extra_result_blocks:
                    if not isinstance(blk, dict):
                        continue
                    bid = blk.get("block_id") or "(no block_id)"
                    title = blk.get("title") or "Additional result"
                    parts.append(f"[Additional dataset: {title} | block_id={bid}]")
                    sql_b = blk.get("sql_script")
                    if sql_b:
                        parts.append(f"```sql\n{sql_b}\n```")
                    pp_b = blk.get("post_process_config")
                    if pp_b:
                        pp_json_b = json.dumps(pp_b, indent=2)
                        if len(pp_json_b) > _HISTORY_POST_PROCESS_JSON_MAX_CHARS:
                            pp_json_b = (
                                pp_json_b[:_HISTORY_POST_PROCESS_JSON_MAX_CHARS].rstrip()
                                + "\n... [POST_PROCESS JSON truncated]"
                            )
                        parts.append(
                            "[POST_PROCESS for that additional dataset]\n"
                            f"```json\n{pp_json_b}\n```"
                        )

    history_text = "\n\n".join(parts) if parts else "(No previous messages)"

    return LLMContext(
        history_text=history_text,
        next_turn_index=next_turn_index,
        previous_post_process_config=previous_post_process_config,
        previous_extra_result_blocks=previous_extra_result_blocks,
        previous_report_layout=previous_report_layout,
    )


def build_template_context(
    db: Session,
    session_id: uuid.UUID,
    template_name: str,
    template_current_sql: str,
    template_current_narrative: Optional[str] = None,
    template_post_process_config: Optional[list[dict]] = None,
) -> LLMContext:
    """
    Build LLM context specifically for template modification mode.

    This enhances the regular context with:
    1. Short template header (name + description + pointer to CURRENT TEMPLATE block)
    2. Modification history from the hidden template session (rolling summarisation
       applies the same way as regular datamart chat when turns exceed the limit)

    This allows the LLM to understand:
    - What template is being modified
    - The current state of the template
    - How it has evolved through previous modifications
    - The intent of each modification request

    Note: Full SQL and post-processing are not duplicated here; the agent user
    prompt includes a dedicated CURRENT TEMPLATE section to save LLM context.

    Parameters
    ----------
    db: Session
        Database session
    session_id: UUID
        The hidden template modification session
    template_name: str
        Name of the template being modified
    template_current_sql: str
        The template's current SQL (what user is modifying)
    template_current_narrative: Optional[str]
        Optional description of what the template does
    template_post_process_config: Optional[list[dict]]
        Current post-processing transformations (if any)

    Returns
    -------
    LLMContext with enhanced history including template state and modification history
    """
    # First, build the regular context from the template session
    base_context = build_llm_context(db, session_id)

    pp_note = (
        f"Post-processing: {len(template_post_process_config)} step(s) configured "
        "(full JSON is in the CURRENT TEMPLATE section of the user prompt)."
        if template_post_process_config
        else "Post-processing: none configured."
    )
    sql_note = f"Template SQL size: {len(template_current_sql)} characters (verbatim SQL is in the user prompt)."

    # Build the template state header (do not repeat full SQL / post_process here —
    # the agent user prompt already includes a "CURRENT TEMPLATE" block with those,
    # and duplicating them blows past small LLM context limits.)
    template_header_parts: list[str] = [
        "═" * 70,
        f"TEMPLATE CONTEXT: Modifying template '{template_name}'",
        "═" * 70,
        "",
        "The canonical SQL and post-processing config for this template appear in the",
        '"CURRENT TEMPLATE" section later in this prompt — use that as the source of truth.',
        "",
    ]

    # Add current narrative if available
    if template_current_narrative:
        template_header_parts.append(f"Description: {template_current_narrative}")
    else:
        template_header_parts.append("Description: (no description)")

    template_header_parts.extend(["", sql_note, pp_note, ""])

    template_header_parts.extend([
        "",
        "MODIFICATION HISTORY (prior modify-chat turns in this template session):",
        "─" * 70,
        "",
    ])

    template_header = "\n".join(template_header_parts)

    # Combine template header with the modification history
    enhanced_history = (
        template_header
        + "\n"
        + (base_context.history_text if base_context.history_text != "(No previous messages)" else "No modifications yet.")
    )

    return LLMContext(
        history_text=enhanced_history,
        next_turn_index=base_context.next_turn_index,
        previous_post_process_config=base_context.previous_post_process_config,
    )


# ── Summarisation ─────────────────────────────────────────────────

def _summarise_turns(
    db: Session,
    session_id: uuid.UUID,
    turns: dict[int, dict],
    turn_indices_to_summarise: list[int],
) -> None:
    """
    Generate an LLM summary of the specified turns and persist it.
    Marks the covered messages as is_summarised=True.

    SQL scripts are extracted verbatim into the summary so the LLM
    retains the question-to-SQL mapping even after summarisation.
    """
    if not turn_indices_to_summarise:
        return

    # Build the text to summarise
    lines: list[str] = []
    for turn_idx in sorted(turn_indices_to_summarise):
        turn = turns.get(turn_idx, {})
        user_msg = turn.get("user")
        asst_msg = turn.get("assistant")
        if user_msg:
            lines.append(f"User asked: {user_msg.content}")
        if asst_msg:
            lines.append(f"Assistant answered: {asst_msg.content}")
            if asst_msg.sql_script:
                lines.append(
                    f"SQL generated for '{asst_msg.question_ref}':\n"
                    f"```sql\n{asst_msg.sql_script}\n```"
                )
            if asst_msg.extra_result_blocks:
                for blk in asst_msg.extra_result_blocks:
                    if isinstance(blk, dict) and blk.get("sql_script"):
                        bid = blk.get("block_id") or ""
                        lines.append(
                            f"Additional SQL (block_id={bid}):\n"
                            f"```sql\n{blk['sql_script']}\n```"
                        )

    text_to_summarise = "\n".join(lines)
    max_turn = max(turn_indices_to_summarise)

    # Call LLM to generate summary
    summary_text = _call_llm_for_summary(text_to_summarise)

    # Persist summary
    summary = DatamartChatSummary(
        id=uuid.uuid4(),
        session_id=session_id,
        summary_text=summary_text,
        covers_up_to_turn=max_turn,
    )
    db.add(summary)

    # Mark covered messages as summarised
    msg_ids = []
    for turn_idx in turn_indices_to_summarise:
        turn = turns.get(turn_idx, {})
        for msg in turn.values():
            msg_ids.append(msg.id)

    if msg_ids:
        db.execute(
            update(DatamartChatMessage)
            .where(DatamartChatMessage.id.in_(msg_ids))
            .values(is_summarised=True)
        )

    db.commit()
    logger.info(
        "Summarised %d turns (up to turn %d) for session %s",
        len(turn_indices_to_summarise),
        max_turn,
        session_id,
    )


def _call_llm_for_summary(conversation_text: str) -> str:
    """
    Call the AI proxy to generate a concise summary of old conversation turns.
    Falls back to a truncated version of the original text on any error.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    from ..llm.llm_client import LlmRole

    system = (
        "You are a conversation summariser for an HR data assistant. "
        "Summarise the following conversation turns concisely. "
        "IMPORTANT: Preserve all SQL queries exactly as-is with their associated questions. "
        "Do not paraphrase or omit any SQL. Keep the summary under 400 words."
    )
    user = f"Summarise these conversation turns:\n\n{conversation_text}"

    def _sync_call() -> str:
        llm = get_llm(LlmRole.CHAT)
        response = llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=user),
        ])
        return response.content

    try:
        return _sync_call()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Summary LLM call failed, using truncated text: %s", exc)
        # Fallback: keep the raw text truncated to 800 chars
        return conversation_text[:800] + ("\n[truncated]" if len(conversation_text) > 800 else "")
