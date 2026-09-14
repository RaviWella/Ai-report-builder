"""
Datamart Chat — SQLAlchemy Models
===================================
Three tables that together implement the full session + history architecture:

  datamart_chat_sessions   — one row per conversation session per user
  datamart_chat_messages   — one row per message turn (user or assistant)
  datamart_chat_summaries  — rolling summaries of old turns for LLM context

Design decisions:
  - All tables live in the **public** schema (not per-org schema copies)
  - UUID primary keys throughout (auth-ready, no sequential ID leakage)
  - user_id is TEXT so it accepts any format (UUID, email, int string)
  - SQL scripts stored verbatim on assistant rows with question_ref for mapping
  - is_summarised flag marks turns already covered by a summary (never deleted)
  - Summaries are internal LLM context aids — original messages are never removed
"""
import uuid
from sqlalchemy import (
    Column, String, Text, Boolean, Integer,
    DateTime, ForeignKey, Index, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from app.core.database import Base


class DatamartChatSession(Base):
    """
    A named conversation session belonging to one user.

    One user can have many sessions. Each session has a UUID that is
    passed by the frontend on every chat request so the backend knows
    which session to append messages to.
    """
    __tablename__ = "datamart_chat_sessions"
    __table_args__ = (
        Index("ix_dcs_user_id", "user_id"),
        Index("ix_dcs_updated_at", "updated_at"),
        Index("ix_datamart_chat_sessions_tenant_user", "tenant_id", "user_id"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    tenant_id = Column(
        String(128),
        nullable=False,
        server_default="demo_tenant",
        index=True,
        comment="MintHRM tenant (X-Tenant-Id). Isolates sessions per customer.",
    )
    user_id = Column(
        String(255),
        nullable=False,
        index=True,
        comment="User identifier. Hardcoded to 'default-user' until auth is wired.",
    )
    title = Column(
        String(255),
        nullable=False,
        default="New conversation",
        comment="Auto-generated from first question; user-editable.",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Soft-delete flag. False = hidden from session list.",
    )
    group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datamart_session_groups.id", ondelete="SET NULL"),
        nullable=True,
        comment="Optional group. NULL = ungrouped. SET NULL on group delete.",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DatamartChatMessage(Base):
    """
    A single message turn within a session.

    User and assistant turns are stored as separate rows linked by
    turn_index so the question-to-SQL mapping is always explicit:

        turn_index=1, role='user',      content='Top 10 employees?', sql_script=NULL
        turn_index=1, role='assistant', content='Here are...', sql_script='SELECT...',
                                        question_ref='Top 10 employees?'

    The question_ref on assistant rows makes the SQL-to-question mapping
    durable and readable by both humans and the LLM.
    """
    __tablename__ = "datamart_chat_messages"
    __table_args__ = (
        Index("ix_dcm_session_id", "session_id"),
        Index("ix_dcm_session_turn", "session_id", "turn_index"),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_dcm_role"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datamart_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(
        String(20),
        nullable=False,
        comment="'user' or 'assistant'",
    )
    content = Column(
        Text,
        nullable=False,
        comment="Question text (user) or narrative response (assistant).",
    )
    sql_script = Column(
        Text,
        nullable=True,
        comment="Generated SQL query. Only set on assistant rows.",
    )
    question_ref = Column(
        Text,
        nullable=True,
        comment=(
            "Copy of the user question that triggered this SQL. "
            "Only set on assistant rows. Provides explicit SQL-to-question mapping."
        ),
    )
    turn_index = Column(
        Integer,
        nullable=False,
        comment="Sequential turn number within the session (1-based). "
                "User and assistant rows for the same exchange share the same turn_index.",
    )
    follow_up_mode = Column(
        String(32),
        nullable=True,
        comment="User rows only: continue_last (modify prior result) or new_question.",
    )
    is_summarised = Column(
        Boolean,
        nullable=False,
        default=False,
        comment=(
            "True when this turn is already covered by a datamart_chat_summaries row. "
            "Does NOT mean deleted — original content is always preserved."
        ),
    )
    post_process_config = Column(
        JSONB,
        nullable=True,
        comment=(
            "Optional JSON array of post-processing steps applied to the SQL result. "
            "Each step: {type, ...params}. "
            "Supported types: add_percentage_column, append_aggregate_row, "
            "append_per_group_aggregate_rows, add_derived_column. "
            "When present, re-applied on every 'Run Query' so results are always reproducible."
        ),
    )
    chart_configs = Column(
        JSONB,
        nullable=True,
        comment=(
            "Ordered JSON array of chart specification objects (schema_version=1). "
            "Rendered client-side from SQL/post-process tabular data; no image storage."
        ),
    )
    extra_result_blocks = Column(
        JSONB,
        nullable=True,
        comment=(
            "Optional array of extra SQL datasets in the same assistant turn. "
            "Each item: {block_id, title, sql_script, post_process_config}. "
            "Rows are not stored; re-executed via API."
        ),
    )
    report_layout = Column(
        JSONB,
        nullable=True,
        comment=(
            "Report presentation: scenario labels, canvas widget positions, "
            "visibility and export flags (schema_version=1)."
        ),
    )
    validation = Column(
        JSONB,
        nullable=True,
        comment=(
            "Retrieval and generation validation snapshot for this assistant turn "
            "(trust level, schema links, warnings)."
        ),
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class DatamartChatSummary(Base):
    """
    A rolling LLM-generated summary of old turns in a session.

    Created automatically when the number of unsummarised turns exceeds
    CONTEXT_TURN_LIMIT. Used only for building LLM prompts — never shown
    to the user as a replacement for original messages.

    SQL scripts are extracted from summarised turns before summarisation
    and preserved verbatim in datamart_chat_messages.sql_script.
    """
    __tablename__ = "datamart_chat_summaries"
    __table_args__ = (
        Index("ix_dcs_sum_session_id", "session_id"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datamart_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    summary_text = Column(
        Text,
        nullable=False,
        comment="LLM-generated summary of the covered turns' narratives.",
    )
    covers_up_to_turn = Column(
        Integer,
        nullable=False,
        comment="turn_index of the last message included in this summary.",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
