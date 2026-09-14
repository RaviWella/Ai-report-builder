"""
Datamart Workspace Service
==========================
All database operations for session groups, templates, and template versions.

Public API (all async):
  # Session groups
  list_session_groups(db, user_id)                -> list[SessionGroupDTO]
  create_session_group(db, user_id, name)         -> SessionGroupDTO
  rename_session_group(db, group_id, name)
  delete_session_group(db, group_id)
  move_session_to_group(db, session_id, group_id)

  # Templates
  list_templates(db, user_id)                     -> list[TemplateDTO]
  get_template(db, template_id)                   -> TemplateDTO | None
  rename_template(db, template_id, name)
  delete_template(db, template_id)
  move_template_to_group(db, template_id, group_id)
  toggle_pin_template(db, template_id)
  get_or_create_template_session(db, template_id, user_id) -> uuid.UUID

  # Template versions
  promote_to_template(db, user_id, name, session_id, message_id,
                      sql_script, post_process_config, narrative, ...) -> TemplateDTO
  save_template_version(db, template_id, sql_script, post_process_config,
                        narrative, label, ...)       -> TemplateVersionDTO
  patch_template_version_report_meta(db, version_id, ...) -> TemplateVersionDTO | None
  list_template_versions(db, template_id)         -> list[TemplateVersionDTO]
  get_template_version(db, version_id)            -> TemplateVersionDTO | None
  get_latest_version(db, template_id)             -> TemplateVersionDTO | None

  # Template groups
  list_template_groups(db, user_id)               -> list[TemplateGroupDTO]
  create_template_group(db, user_id, name)        -> TemplateGroupDTO
  rename_template_group(db, group_id, name)
  delete_template_group(db, group_id)
  get_template_group(db, group_id)                -> TemplateGroupDTO | None
"""
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select, update, func as sa_func, insert as sa_insert
from sqlalchemy.orm import Session

from app.models.datamart_chat import DatamartChatSession
from .workspace_scope import resolve_workspace_tenant_id
from app.models.datamart_workspace import (
    DatamartSessionGroup,
    DatamartTemplate,
    DatamartTemplateGroup,
    DatamartTemplateVersion,
)

logger = logging.getLogger("ai_services.datamart")


# ── Data transfer objects ─────────────────────────────────────────

@dataclass
class SessionGroupDTO:
    id: str
    name: str
    position: int
    created_at: str
    updated_at: str


@dataclass
class TemplateGroupDTO:
    id: str
    name: str
    position: int
    created_at: str
    updated_at: str


@dataclass
class TemplateVersionDTO:
    id: str
    template_id: str
    version_num: int
    label: Optional[str]
    sql_script: str
    post_process_config: Optional[list[dict]]
    chart_configs: Optional[list[dict]]
    extra_result_blocks: Optional[list[dict]]
    report_layout: Optional[dict]
    narrative: Optional[str]
    source_session_id: Optional[str]
    source_message_id: Optional[str]
    is_latest: bool
    created_at: str


@dataclass
class TemplateDTO:
    id: str
    name: str
    group_id: Optional[str]
    is_pinned: bool
    created_at: str
    updated_at: str
    latest_version: Optional[TemplateVersionDTO]


# ── Helpers ───────────────────────────────────────────────────────

def _session_group_dto(g: DatamartSessionGroup) -> SessionGroupDTO:
    return SessionGroupDTO(
        id=str(g.id),
        name=g.name,
        position=g.position,
        created_at=g.created_at.isoformat(),
        updated_at=g.updated_at.isoformat(),
    )


def _template_group_dto(g: DatamartTemplateGroup) -> TemplateGroupDTO:
    return TemplateGroupDTO(
        id=str(g.id),
        name=g.name,
        position=g.position,
        created_at=g.created_at.isoformat(),
        updated_at=g.updated_at.isoformat(),
    )


def _version_dto(v: DatamartTemplateVersion) -> TemplateVersionDTO:
    return TemplateVersionDTO(
        id=str(v.id),
        template_id=str(v.template_id),
        version_num=v.version_num,
        label=v.label,
        sql_script=v.sql_script,
        post_process_config=v.post_process_config,
        chart_configs=v.chart_configs,
        extra_result_blocks=v.extra_result_blocks,
        report_layout=v.report_layout,
        narrative=v.narrative,
        source_session_id=str(v.source_session_id) if v.source_session_id else None,
        source_message_id=str(v.source_message_id) if v.source_message_id else None,
        is_latest=v.is_latest,
        created_at=v.created_at.isoformat(),
    )


def _template_dto(t: DatamartTemplate, latest: Optional[DatamartTemplateVersion]) -> TemplateDTO:
    return TemplateDTO(
        id=str(t.id),
        name=t.name,
        group_id=str(t.group_id) if t.group_id else None,
        is_pinned=t.is_pinned,
        created_at=t.created_at.isoformat(),
        updated_at=t.updated_at.isoformat(),
        latest_version=_version_dto(latest) if latest else None,
    )


def _workspace_tenant(tenant_id: Optional[str] = None) -> str:
    return resolve_workspace_tenant_id(tenant_id)


def _get_template_row(
    db: Session,
    template_id: uuid.UUID,
    *,
    tenant_id: Optional[str] = None,
    active_only: bool = True,
) -> Optional[DatamartTemplate]:
    tid = _workspace_tenant(tenant_id)
    clauses = [
        DatamartTemplate.id == template_id,
        DatamartTemplate.tenant_id == tid,
    ]
    if active_only:
        clauses.append(DatamartTemplate.is_active.is_(True))
    result = db.execute(select(DatamartTemplate).where(*clauses))
    return result.scalar_one_or_none()


# ── Session groups ────────────────────────────────────────────────

def list_session_groups(
    db: Session,
    user_id: str,
    *,
    tenant_id: Optional[str] = None,
) -> list[SessionGroupDTO]:
    """Return all session groups for a user, ordered by position then name."""
    tid = resolve_workspace_tenant_id(tenant_id)
    result = db.execute(
        select(DatamartSessionGroup)
        .where(
            DatamartSessionGroup.tenant_id == tid,
            DatamartSessionGroup.user_id == user_id,
        )
        .order_by(DatamartSessionGroup.position.asc(), DatamartSessionGroup.name.asc())
    )
    return [_session_group_dto(g) for g in result.scalars().all()]


def create_session_group(
    db: Session,
    user_id: str,
    name: str,
    *,
    tenant_id: Optional[str] = None,
) -> SessionGroupDTO:
    """Create a new session group and return its DTO."""
    tid = resolve_workspace_tenant_id(tenant_id)
    # Position = current max + 1
    pos_result = db.execute(
        select(sa_func.coalesce(sa_func.max(DatamartSessionGroup.position), -1))
        .where(
            DatamartSessionGroup.tenant_id == tid,
            DatamartSessionGroup.user_id == user_id,
        )
    )
    next_pos = (pos_result.scalar_one() or 0) + 1

    group = DatamartSessionGroup(
        id=uuid.uuid4(),
        tenant_id=tid,
        user_id=user_id,
        name=name,
        position=next_pos,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    logger.info("Created session group %s (%r) for user %s", group.id, name, user_id)
    return _session_group_dto(group)


def rename_session_group(
    db: Session,
    group_id: uuid.UUID,
    name: str,
    *,
    tenant_id: Optional[str] = None,
) -> None:
    tid = _workspace_tenant(tenant_id)
    db.execute(
        update(DatamartSessionGroup)
        .where(
            DatamartSessionGroup.id == group_id,
            DatamartSessionGroup.tenant_id == tid,
        )
        .values(name=name, updated_at=sa_func.now())
    )
    db.commit()


def delete_session_group(
    db: Session,
    group_id: uuid.UUID,
    *,
    tenant_id: Optional[str] = None,
) -> None:
    """
    Delete a session group. Sessions in the group have their group_id set to NULL
    (SET NULL cascade) so they are not lost.
    """
    tid = _workspace_tenant(tenant_id)
    result = db.execute(
        select(DatamartSessionGroup).where(
            DatamartSessionGroup.id == group_id,
            DatamartSessionGroup.tenant_id == tid,
        )
    )
    group = result.scalar_one_or_none()
    if group:
        db.delete(group)
        db.commit()
        logger.info("Deleted session group %s", group_id)


def move_session_to_group(
    db: Session,
    session_id: uuid.UUID,
    group_id: Optional[uuid.UUID],
    *,
    tenant_id: Optional[str] = None,
) -> None:
    """Move a session to a group (or ungroup it by passing group_id=None)."""
    tid = _workspace_tenant(tenant_id)
    db.execute(
        update(DatamartChatSession)
        .where(
            DatamartChatSession.id == session_id,
            DatamartChatSession.tenant_id == tid,
        )
        .values(group_id=group_id)
    )
    db.commit()


# ── Template groups ───────────────────────────────────────────────

def list_template_groups(
    db: Session,
    user_id: str,
    *,
    tenant_id: Optional[str] = None,
) -> list[TemplateGroupDTO]:
    tid = resolve_workspace_tenant_id(tenant_id)
    result = db.execute(
        select(DatamartTemplateGroup)
        .where(
            DatamartTemplateGroup.tenant_id == tid,
            DatamartTemplateGroup.user_id == user_id,
        )
        .order_by(DatamartTemplateGroup.position.asc(), DatamartTemplateGroup.name.asc())
    )
    return [_template_group_dto(g) for g in result.scalars().all()]


def create_template_group(
    db: Session,
    user_id: str,
    name: str,
    *,
    tenant_id: Optional[str] = None,
) -> TemplateGroupDTO:
    tid = resolve_workspace_tenant_id(tenant_id)
    pos_result = db.execute(
        select(sa_func.coalesce(sa_func.max(DatamartTemplateGroup.position), -1))
        .where(
            DatamartTemplateGroup.tenant_id == tid,
            DatamartTemplateGroup.user_id == user_id,
        )
    )
    next_pos = (pos_result.scalar_one() or 0) + 1

    group = DatamartTemplateGroup(
        id=uuid.uuid4(),
        tenant_id=tid,
        user_id=user_id,
        name=name,
        position=next_pos,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return _template_group_dto(group)


def rename_template_group(
    db: Session,
    group_id: uuid.UUID,
    name: str,
    *,
    tenant_id: Optional[str] = None,
) -> None:
    tid = _workspace_tenant(tenant_id)
    db.execute(
        update(DatamartTemplateGroup)
        .where(
            DatamartTemplateGroup.id == group_id,
            DatamartTemplateGroup.tenant_id == tid,
        )
        .values(name=name, updated_at=sa_func.now())
    )
    db.commit()


def delete_template_group(
    db: Session,
    group_id: uuid.UUID,
    *,
    tenant_id: Optional[str] = None,
) -> None:
    tid = _workspace_tenant(tenant_id)
    result = db.execute(
        select(DatamartTemplateGroup).where(
            DatamartTemplateGroup.id == group_id,
            DatamartTemplateGroup.tenant_id == tid,
        )
    )
    group = result.scalar_one_or_none()
    if group:
        db.delete(group)
        db.commit()


def get_template_group(
    db: Session,
    group_id: uuid.UUID,
    *,
    tenant_id: Optional[str] = None,
) -> Optional[TemplateGroupDTO]:
    """Get a template group by ID."""
    tid = _workspace_tenant(tenant_id)
    result = db.execute(
        select(DatamartTemplateGroup).where(
            DatamartTemplateGroup.id == group_id,
            DatamartTemplateGroup.tenant_id == tid,
        )
    )
    row = result.scalar_one_or_none()
    return _template_group_dto(row) if row else None


# ── Templates ─────────────────────────────────────────────────────

def _get_latest_version(
    db: Session,
    template_id: uuid.UUID,
) -> Optional[DatamartTemplateVersion]:
    result = db.execute(
        select(DatamartTemplateVersion)
        .where(
            DatamartTemplateVersion.template_id == template_id,
            DatamartTemplateVersion.is_latest.is_(True),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


def list_templates(
    db: Session,
    user_id: str,
    *,
    tenant_id: Optional[str] = None,
) -> list[TemplateDTO]:
    tid = resolve_workspace_tenant_id(tenant_id)
    """
    Return all active templates for a user, pinned first then by updated_at desc.
    Includes the latest version for each template.
    """
    result = db.execute(
        select(DatamartTemplate)
        .where(
            DatamartTemplate.tenant_id == tid,
            DatamartTemplate.user_id == user_id,
            DatamartTemplate.is_active.is_(True),
        )
        .order_by(
            DatamartTemplate.is_pinned.desc(),
            DatamartTemplate.updated_at.desc(),
        )
    )
    templates = result.scalars().all()

    dtos = []
    for t in templates:
        latest = _get_latest_version(db, t.id)
        dtos.append(_template_dto(t, latest))
    return dtos


def get_template(
    db: Session,
    template_id: uuid.UUID,
    *,
    tenant_id: Optional[str] = None,
) -> Optional[TemplateDTO]:
    tid = resolve_workspace_tenant_id(tenant_id)
    result = db.execute(
        select(DatamartTemplate).where(
            DatamartTemplate.id == template_id,
            DatamartTemplate.tenant_id == tid,
            DatamartTemplate.is_active.is_(True),
        )
    )
    t = result.scalar_one_or_none()
    if t is None:
        return None
    latest = _get_latest_version(db, t.id)
    return _template_dto(t, latest)


def rename_template(
    db: Session,
    template_id: uuid.UUID,
    name: str,
    *,
    tenant_id: Optional[str] = None,
) -> None:
    tid = _workspace_tenant(tenant_id)
    db.execute(
        update(DatamartTemplate)
        .where(
            DatamartTemplate.id == template_id,
            DatamartTemplate.tenant_id == tid,
        )
        .values(name=name, updated_at=sa_func.now())
    )
    db.commit()


def delete_template(
    db: Session,
    template_id: uuid.UUID,
    *,
    tenant_id: Optional[str] = None,
) -> None:
    """Soft-delete a template (is_active=False). Versions are preserved."""
    tid = _workspace_tenant(tenant_id)
    db.execute(
        update(DatamartTemplate)
        .where(
            DatamartTemplate.id == template_id,
            DatamartTemplate.tenant_id == tid,
        )
        .values(is_active=False, updated_at=sa_func.now())
    )
    db.commit()
    logger.info("Soft-deleted template %s", template_id)


def move_template_to_group(
    db: Session,
    template_id: uuid.UUID,
    group_id: Optional[uuid.UUID],
    *,
    tenant_id: Optional[str] = None,
) -> None:
    tid = _workspace_tenant(tenant_id)
    db.execute(
        update(DatamartTemplate)
        .where(
            DatamartTemplate.id == template_id,
            DatamartTemplate.tenant_id == tid,
        )
        .values(group_id=group_id, updated_at=sa_func.now())
    )
    db.commit()


def toggle_pin_template(
    db: Session,
    template_id: uuid.UUID,
    *,
    tenant_id: Optional[str] = None,
) -> bool:
    """Toggle the is_pinned flag. Returns the new pinned state."""
    t = _get_template_row(db, template_id, tenant_id=tenant_id)
    if t is None:
        return False
    new_state = not t.is_pinned
    tid = _workspace_tenant(tenant_id)
    db.execute(
        update(DatamartTemplate)
        .where(
            DatamartTemplate.id == template_id,
            DatamartTemplate.tenant_id == tid,
        )
        .values(is_pinned=new_state, updated_at=sa_func.now())
    )
    db.commit()
    return new_state


# ── Template versions ─────────────────────────────────────────────

def promote_to_template(
    db: Session,
    user_id: str,
    name: str,
    sql_script: str,
    post_process_config: Optional[list[dict]],
    narrative: Optional[str],
    chart_configs: Optional[list[dict]] = None,
    extra_result_blocks: Optional[list[dict]] = None,
    report_layout: Optional[dict] = None,
    source_session_id: Optional[uuid.UUID] = None,
    source_message_id: Optional[uuid.UUID] = None,
    tenant_id: Optional[str] = None,
) -> TemplateDTO:
    """
    Promote a chat response to a new template with version 1.

    Creates both the template record and its first version atomically.
    Uses explicit column INSERT to avoid issues with columns added by
    later migrations (e.g. template_session_id) that may not exist yet.
    """
    template_id = uuid.uuid4()
    tid = resolve_workspace_tenant_id(tenant_id)

    # Explicit INSERT — only the columns that exist in the base migration
    db.execute(
        sa_insert(DatamartTemplate).values(
            id=template_id,
            tenant_id=tid,
            user_id=user_id,
            name=name,
            is_pinned=False,
            is_active=True,
        )
    )

    version_id = uuid.uuid4()
    version = DatamartTemplateVersion(
        id=version_id,
        template_id=template_id,
        version_num=1,
        label="Initial version",
        sql_script=sql_script,
        post_process_config=post_process_config,
        chart_configs=chart_configs,
        extra_result_blocks=extra_result_blocks,
        report_layout=report_layout,
        narrative=narrative,
        source_session_id=source_session_id,
        source_message_id=source_message_id,
        is_latest=True,
    )
    db.add(version)
    db.commit()

    # Reload both objects
    t_result = db.execute(
        select(DatamartTemplate).where(DatamartTemplate.id == template_id)
    )
    template = t_result.scalar_one()
    v_result = db.execute(
        select(DatamartTemplateVersion).where(DatamartTemplateVersion.id == version_id)
    )
    version = v_result.scalar_one()

    logger.info(
        "Promoted message %s to template %s (%r) for user %s",
        source_message_id, template_id, name, user_id,
    )
    return _template_dto(template, version)


def save_template_version(
    db: Session,
    template_id: uuid.UUID,
    sql_script: str,
    post_process_config: Optional[list[dict]],
    narrative: Optional[str],
    label: Optional[str] = None,
    chart_configs: Optional[list[dict]] = None,
    extra_result_blocks: Optional[list[dict]] = None,
    report_layout: Optional[dict] = None,
    *,
    tenant_id: Optional[str] = None,
) -> TemplateVersionDTO:
    """
    Save a new version of a template.

    Steps:
      1. Clear is_latest on all existing versions for this template.
      2. Compute next version_num.
      3. Insert new version with is_latest=True.
      4. Update template.updated_at.
    """
    owned = _get_template_row(db, template_id, tenant_id=tenant_id)
    if owned is None:
        raise ValueError(f"Template {template_id} not found for tenant")

    # Step 1: clear is_latest on existing versions
    db.execute(
        update(DatamartTemplateVersion)
        .where(DatamartTemplateVersion.template_id == template_id)
        .values(is_latest=False)
    )

    # Step 2: compute next version_num
    num_result = db.execute(
        select(sa_func.coalesce(sa_func.max(DatamartTemplateVersion.version_num), 0))
        .where(DatamartTemplateVersion.template_id == template_id)
    )
    next_num = (num_result.scalar_one() or 0) + 1

    # Step 3: insert new version
    version = DatamartTemplateVersion(
        id=uuid.uuid4(),
        template_id=template_id,
        version_num=next_num,
        label=label,
        sql_script=sql_script,
        post_process_config=post_process_config,
        chart_configs=chart_configs,
        extra_result_blocks=extra_result_blocks,
        report_layout=report_layout,
        narrative=narrative,
        is_latest=True,
    )
    db.add(version)

    # Step 4: update template timestamp
    tid = _workspace_tenant(tenant_id)
    db.execute(
        update(DatamartTemplate)
        .where(
            DatamartTemplate.id == template_id,
            DatamartTemplate.tenant_id == tid,
        )
        .values(updated_at=sa_func.now())
    )

    db.commit()
    db.refresh(version)
    logger.info("Saved version %d for template %s", next_num, template_id)
    return _version_dto(version)


def list_template_versions(
    db: Session,
    template_id: uuid.UUID,
    *,
    tenant_id: Optional[str] = None,
) -> list[TemplateVersionDTO]:
    """Return all versions for a template, newest first."""
    if _get_template_row(db, template_id, tenant_id=tenant_id) is None:
        return []
    result = db.execute(
        select(DatamartTemplateVersion)
        .where(DatamartTemplateVersion.template_id == template_id)
        .order_by(DatamartTemplateVersion.version_num.desc())
    )
    return [_version_dto(v) for v in result.scalars().all()]


def get_template_version(
    db: Session,
    version_id: uuid.UUID,
    *,
    tenant_id: Optional[str] = None,
) -> Optional[TemplateVersionDTO]:
    tid = _workspace_tenant(tenant_id)
    result = db.execute(
        select(DatamartTemplateVersion)
        .join(
            DatamartTemplate,
            DatamartTemplateVersion.template_id == DatamartTemplate.id,
        )
        .where(
            DatamartTemplateVersion.id == version_id,
            DatamartTemplate.tenant_id == tid,
            DatamartTemplate.is_active.is_(True),
        )
    )
    v = result.scalar_one_or_none()
    return _version_dto(v) if v else None


def patch_template_version_report_meta(
    db: Session,
    version_id: uuid.UUID,
    *,
    report_layout: Optional[dict] = None,
    primary_label: Optional[str] = None,
    block_labels: Optional[dict[str, str]] = None,
    tenant_id: Optional[str] = None,
) -> Optional[TemplateVersionDTO]:
    """
    Update scenario labels and/or report canvas layout on a template version.

    Mirrors ``update_assistant_report_meta`` for chat messages.
    """
    tid = _workspace_tenant(tenant_id)
    result = db.execute(
        select(DatamartTemplateVersion)
        .join(
            DatamartTemplate,
            DatamartTemplateVersion.template_id == DatamartTemplate.id,
        )
        .where(
            DatamartTemplateVersion.id == version_id,
            DatamartTemplate.tenant_id == tid,
            DatamartTemplate.is_active.is_(True),
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        return None

    layout: dict = {}
    if isinstance(version.report_layout, dict):
        layout = dict(version.report_layout)
    if report_layout is not None and isinstance(report_layout, dict):
        layout = {**layout, **report_layout}
    if primary_label is not None:
        layout["primary_label"] = primary_label.strip() or None
    if layout:
        layout.setdefault("schema_version", 1)
        version.report_layout = layout

    if block_labels:
        blocks = list(version.extra_result_blocks or [])
        changed = False
        for blk in blocks:
            if not isinstance(blk, dict):
                continue
            bid = str(blk.get("block_id") or "")
            if bid in block_labels:
                blk["title"] = block_labels[bid].strip() or blk.get("title")
                changed = True
        if changed:
            version.extra_result_blocks = blocks

    db.execute(
        update(DatamartTemplate)
        .where(
            DatamartTemplate.id == version.template_id,
            DatamartTemplate.tenant_id == tid,
        )
        .values(updated_at=sa_func.now())
    )
    db.commit()
    db.refresh(version)
    logger.debug("Updated report meta on template version %s", version_id)
    return _version_dto(version)


def get_latest_version(
    db: Session,
    template_id: uuid.UUID,
    *,
    tenant_id: Optional[str] = None,
) -> Optional[TemplateVersionDTO]:
    """Latest version for a tenant-owned template."""
    if _get_template_row(db, template_id, tenant_id=tenant_id) is None:
        return None
    row = _get_latest_version(db, template_id)
    return _version_dto(row) if row else None


# ── Template session (hidden per-template chat session) ───────────

def get_or_create_template_session(
    db: Session,
    template_id: uuid.UUID,
    user_id: str,
    *,
    tenant_id: Optional[str] = None,
) -> uuid.UUID:
    tid = resolve_workspace_tenant_id(tenant_id)
    """
    Return the UUID of the hidden chat session used for this template's
    modify-chat history. Creates one lazily on first call.

    The session is stored with is_active=False so it never appears in the
    chat sidebar's list_sessions query (which filters is_active=True).

    Uses raw SQL for template_session_id access so this works both before
    and after the add_template_session_id_001 migration is applied.
    Before migration: always creates a new in-memory session (no persistence).
    After migration: persists the session link on the template row.
    """
    from sqlalchemy import text as sa_text

    # Check if template_session_id exists on datamart_templates in the *current* schema.
    # Must filter by table_schema: without it, every tenant schema matches and
    # scalar_one_or_none() raises MultipleResultsFound → HTTP 500 on template chat.
    col_check = db.execute(sa_text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = current_schema() "
        "AND table_name = 'datamart_templates' "
        "AND column_name = 'template_session_id' "
        "LIMIT 1"
    ))
    column_exists = col_check.scalar_one_or_none() is not None

    if column_exists:
        # Read existing session_id via raw SQL
        row = db.execute(sa_text(
            "SELECT template_session_id FROM datamart_templates WHERE id = :tid"
        ).bindparams(tid=template_id))
        existing_session_id = row.scalar_one_or_none()
        if existing_session_id is not None:
            return existing_session_id

    # Verify template exists
    t_check = db.execute(
        select(DatamartTemplate.id).where(
            DatamartTemplate.id == template_id,
            DatamartTemplate.tenant_id == tid,
        )
    )
    if t_check.scalar_one_or_none() is None:
        raise ValueError(f"Template {template_id} not found")

    # Create a hidden session (is_active=False keeps it off the sidebar)
    session_id = uuid.uuid4()
    hidden_session = DatamartChatSession(
        id=session_id,
        tenant_id=tid,
        user_id=user_id,
        title=f"[template:{template_id}]",
        is_active=False,  # hidden from chat sidebar
    )
    db.add(hidden_session)
    db.flush()

    if column_exists:
        # Persist the link via raw SQL
        db.execute(sa_text(
            "UPDATE datamart_templates SET template_session_id = :sid WHERE id = :tid"
        ).bindparams(sid=session_id, tid=template_id))
    db.commit()

    logger.info(
        "Created hidden template session %s for template %s",
        session_id,
        template_id,
    )
    return session_id
