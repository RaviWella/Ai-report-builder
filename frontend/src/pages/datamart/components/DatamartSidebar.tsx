/**
 * DatamartSidebar
 * ===============
 * Unified right-side panel with two sections:
 *
 *  TEMPLATES  — saved query templates (pinned first, then by updated_at)
 *  WORKSPACES — chat sessions, optionally grouped into named folders
 *
 * Layout matches the reference image:
 *  ┌─────────────────────────────────────────┐
 *  │  TEMPLATES                  Browse all  │
 *  │  ☆ Employee Salary Report               │
 *  │  ☆ Attendance Summary                   │
 *  ├─────────────────────────────────────────┤
 *  │  WORKSPACES                         +   │
 *  │  ▼ 📁 HR Reports                    3   │
 *  │    • Q4 Salary Analysis                 │
 *  │    • Leave Balance Report               │
 *  │  (ungrouped)                            │
 *  │    • New conversation                   │
 *  └─────────────────────────────────────────┘
 */
import React, { useState, useRef, useEffect, useMemo } from 'react'
import clsx from 'clsx'
import { Link, useLocation } from 'react-router-dom'
import { chatPathWithSession, templatePathWithId } from '../lib/workspaceRoute'
import {
  Plus, Trash2, Check, X,
  Star, FolderOpen, Folder, ChevronDown, ChevronRight,
  FileText, Pin, MoveHorizontal, Search, Loader2,
} from 'lucide-react'
import type {
  SessionListItem,
  SessionGroupResponse,
  TemplateResponse,
  TemplateGroupResponse,
} from '../../../services/datamartService'

// ── Types ─────────────────────────────────────────────────────────

export interface DatamartSidebarProps {
  // Sessions
  sessions: SessionListItem[]
  activeSessionId: string | null
  sessionsLoading: boolean
  onWarmSession: (id: string) => void
  onNewSession: () => void
  onRenameSession: (id: string, title: string) => void
  onDeleteSession: (id: string) => void
  onMoveSessionToGroup: (_sessionId: string, _groupId: string | null) => void

  // Session groups
  sessionGroups: SessionGroupResponse[]
  onCreateSessionGroup: (name: string) => void
  onRenameSessionGroup: (id: string, name: string) => void
  onDeleteSessionGroup: (id: string) => void

  // Templates
  templates: TemplateResponse[]
  activeTemplateId: string | null
  templatesLoading: boolean
  onWarmTemplate: (id: string) => void
  onDeleteTemplate: (id: string) => void
  onPinTemplate: (id: string) => void
  onMoveTemplateToGroup: (_templateId: string, _groupId: string | null) => void

  // Template groups
  templateGroups: TemplateGroupResponse[]
  onCreateTemplateGroup: (name: string) => void
  onRenameTemplateGroup: (id: string, name: string) => void
  onDeleteTemplateGroup: (id: string) => void

  deletingSessionId?: string | null
  deletingTemplateId?: string | null
  deletingSessionGroupId?: string | null
  deletingTemplateGroupId?: string | null
}

function RowDeletingIndicator({ label = 'Deleting…' }: { label?: string }) {
  return (
    <span className="dm-row-deleting" aria-live="polite" aria-busy="true">
      <Loader2 size={12} className="dm-spin" color="#0d9488" aria-hidden />
      <span>{label}</span>
    </span>
  )
}

function SidebarIconButton({
  label,
  onClick,
  variant = 'neutral',
  children,
}: {
  label: string
  onClick: (e: React.MouseEvent) => void
  variant?: 'move' | 'danger' | 'neutral'
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      className={clsx(
        'dm-icon-btn',
        variant === 'move' && 'dm-icon-btn--move',
        variant === 'danger' && 'dm-icon-btn--danger',
      )}
      aria-label={label}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

// ── Inline editable label ─────────────────────────────────────────

interface EditableLabelProps {
  value: string
  onCommit: (v: string) => void
  onCancel: () => void
  style?: React.CSSProperties
}

function EditableLabel({ value, onCommit, onCancel, style }: EditableLabelProps) {
  const [v, setV] = useState(value)
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => { ref.current?.focus(); ref.current?.select() }, [])

  const commit = () => {
    const t = v.trim()
    if (t && t !== value) onCommit(t)
    else onCancel()
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}>
      <input
        ref={ref}
        value={v}
        onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') onCancel() }}
        onBlur={commit}
        onClick={(e) => e.stopPropagation()}
        className="dm-editable-input"
        aria-label="Rename"
        style={style}
      />
      <SidebarIconButton label="Save name" onClick={(e) => { e.stopPropagation(); commit() }}>
        <Check size={11} color="#0d9488" aria-hidden />
      </SidebarIconButton>
      <SidebarIconButton label="Cancel rename" onClick={(e) => { e.stopPropagation(); onCancel() }}>
        <X size={11} color="#94a3b8" aria-hidden />
      </SidebarIconButton>
    </div>
  )
}

// ── Move-to-group dropdown ─────────────────────────────────────────

interface MoveToGroupDropdownProps {
  currentGroupId: string | null
  groups: Array<{ id: string; name: string }>
  onMoveToGroup: (groupId: string | null) => void
  triggerRef: React.RefObject<HTMLDivElement | null>
  onClose: () => void
}

function MoveToGroupDropdown({ currentGroupId, groups, onMoveToGroup, triggerRef, onClose }: MoveToGroupDropdownProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        ref.current && !ref.current.contains(e.target as Node) &&
        triggerRef.current && !triggerRef.current.contains(e.target as Node)
      ) {
        onClose()
      }
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', handleClick)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleKey)
    }
  }, [onClose, triggerRef])

  const otherGroups = groups.filter((g) => g.id !== currentGroupId)

  return (
    <div
      ref={ref}
      role="menu"
      className="dm-move-dropdown"
      onClick={(e) => e.stopPropagation()}
    >
      {currentGroupId && (
        <button
          type="button"
          role="menuitem"
          className="dm-move-dropdown__item dm-move-dropdown__item--danger"
          onClick={() => { onMoveToGroup(null); onClose() }}
        >
          Ungroup
        </button>
      )}
      {otherGroups.length === 0 && !currentGroupId && (
        <div style={{ padding: '6px 12px', fontSize: 11, color: '#94a3b8' }}>
          No other groups
        </div>
      )}
      {otherGroups.map((g) => (
        <button
          key={g.id}
          type="button"
          role="menuitem"
          className="dm-move-dropdown__item"
          onClick={() => { onMoveToGroup(g.id); onClose() }}
        >
          <Folder size={11} color="#64748b" style={{ marginRight: 6 }} aria-hidden />
          {g.name}
        </button>
      ))}
    </div>
  )
}

interface SessionRowProps {
  session: SessionListItem
  isActive: boolean
  isDeleting?: boolean
  onWarmSession: () => void
  onRename: (title: string) => void
  onDelete: () => void
  onMoveToGroup: (groupId: string | null) => void
  groups: Array<{ id: string; name: string }>
  indent?: boolean
}

function SessionRow({
  session, isActive, isDeleting = false, onWarmSession, onRename, onDelete, onMoveToGroup, groups, indent,
}: SessionRowProps) {
  const location = useLocation()
  const [editing, setEditing] = useState(false)
  const [showMoveDropdown, setShowMoveDropdown] = useState(false)
  const moveBtnRef = useRef<HTMLDivElement>(null)

  return (
    <div
      data-testid={`datamart-session-row-${session.id}`}
      className={clsx(
        'dm-nav-row',
        isActive && 'dm-nav-row--active',
        isDeleting && 'dm-nav-row--deleting',
      )}
      style={{ paddingLeft: indent ? 22 : 10 }}
    >
      {editing ? (
        <>
          <div style={{
            width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
            background: isActive ? '#0d9488' : '#cbd5e1',
          }} />
          <EditableLabel
            value={session.title}
            onCommit={(v) => { onRename(v); setEditing(false) }}
            onCancel={() => setEditing(false)}
          />
        </>
      ) : (
        <Link
          to={chatPathWithSession(session.id, location.search)}
          onClick={() => onWarmSession()}
          className="dm-nav-row__link"
        >
          <span className="dm-nav-row__dot" aria-hidden />
          <span
            className="dm-nav-row__title"
            onDoubleClick={(e) => { e.stopPropagation(); setEditing(true) }}
            title={session.title}
          >
            {session.title}
          </span>
        </Link>
      )}

      {!editing && (
        <>
          {isDeleting ? (
            <RowDeletingIndicator />
          ) : !isActive ? (
            <div className="dm-row-actions">
              <div ref={moveBtnRef}>
                <SidebarIconButton
                  label={`Move ${session.title} to group`}
                  variant="move"
                  onClick={(e) => { e.stopPropagation(); setShowMoveDropdown((v) => !v) }}
                >
                  <MoveHorizontal size={11} color="#0f766e" aria-hidden />
                </SidebarIconButton>
              </div>
              {showMoveDropdown && (
                <MoveToGroupDropdown
                  currentGroupId={session.group_id}
                  groups={groups}
                  onMoveToGroup={onMoveToGroup}
                  triggerRef={moveBtnRef}
                  onClose={() => setShowMoveDropdown(false)}
                />
              )}
              <SidebarIconButton
                label={`Delete ${session.title}`}
                variant="danger"
                onClick={(e) => { e.stopPropagation(); onDelete() }}
              >
                <Trash2 size={11} color="#dc2626" aria-hidden />
              </SidebarIconButton>
            </div>
          ) : null}
        </>
      )}
    </div>
  )
}

// ── Session group row ─────────────────────────────────────────────

interface GroupRowProps {
  group: SessionGroupResponse
  sessions: SessionListItem[]
  activeSessionId: string | null
  isDeletingGroup?: boolean
  deletingSessionId?: string | null
  onWarmSession: (id: string) => void
  onRenameSession: (id: string, title: string) => void
  onDeleteSession: (id: string) => void
  onMoveSessionToGroup: (sessionId: string, groupId: string | null) => void
  allSessionGroups: Array<{ id: string; name: string }>
  onRenameGroup: (name: string) => void
  onDeleteGroup: () => void
}

function GroupRow({
  group, sessions, activeSessionId, isDeletingGroup = false, deletingSessionId = null,
  onWarmSession, onRenameSession, onDeleteSession,
  onMoveSessionToGroup, allSessionGroups,
  onRenameGroup, onDeleteGroup,
}: GroupRowProps) {
  const [expanded, setExpanded] = useState(true)
  const [editing, setEditing] = useState(false)

  return (
    <div style={{ marginBottom: 2 }}>
      <div
        className={clsx('dm-group-row', isDeletingGroup && 'dm-row--deleting')}
        onClick={() => !editing && !isDeletingGroup && setExpanded((v) => !v)}
        style={{ cursor: isDeletingGroup ? 'default' : 'pointer' }}
      >
        {expanded
          ? <ChevronDown size={12} color="#94a3b8" style={{ flexShrink: 0 }} aria-hidden />
          : <ChevronRight size={12} color="#94a3b8" style={{ flexShrink: 0 }} aria-hidden />
        }
        <FolderOpen size={13} color="#64748b" style={{ flexShrink: 0 }} aria-hidden />

        {editing ? (
          <EditableLabel
            value={group.name}
            onCommit={(v) => { onRenameGroup(v); setEditing(false) }}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <>
            <span
              className="dm-group-row__name"
              onDoubleClick={(e) => { e.stopPropagation(); setEditing(true) }}
            >
              {group.name}
            </span>
            <span className="dm-group-row__count">
              {sessions.length}
            </span>
            {isDeletingGroup ? (
              <RowDeletingIndicator />
            ) : (
              <div className="dm-row-actions dm-group-row__actions">
                <SidebarIconButton
                  label={`Delete group ${group.name}`}
                  variant="danger"
                  onClick={(e) => { e.stopPropagation(); onDeleteGroup() }}
                >
                  <Trash2 size={11} color="#dc2626" aria-hidden />
                </SidebarIconButton>
              </div>
            )}
          </>
        )}
      </div>

      {expanded && sessions.map((s) => (
        <SessionRow
          key={s.id}
          session={s}
          isActive={s.id === activeSessionId}
          isDeleting={deletingSessionId === s.id}
          onWarmSession={() => onWarmSession(s.id)}
          onRename={(title) => onRenameSession(s.id, title)}
          onDelete={() => onDeleteSession(s.id)}
          onMoveToGroup={(groupId) => onMoveSessionToGroup(s.id, groupId)}
          groups={allSessionGroups}
          indent
        />
      ))}
    </div>
  )
}

// ── Template row ──────────────────────────────────────────────────

interface TemplateRowProps {
  template: TemplateResponse
  isActive: boolean
  isDeleting?: boolean
  onWarmTemplate: () => void
  onDelete: () => void
  onPin: () => void
  onMoveToGroup: (groupId: string | null) => void
  groups: Array<{ id: string; name: string }>
  indent?: boolean
}

function TemplateRow({
  template, isActive, isDeleting = false, onWarmTemplate, onDelete, onPin, onMoveToGroup, groups, indent,
}: TemplateRowProps) {
  const location = useLocation()
  const [showMoveDropdown, setShowMoveDropdown] = useState(false)
  const moveBtnRef = useRef<HTMLDivElement>(null)
  const versionNum = template.latest_version?.version_num ?? 1

  return (
    <div
      data-testid={`datamart-template-row-${template.id}`}
      className={clsx(
        'dm-template-row',
        isActive && 'dm-template-row--active',
        indent && 'dm-template-row--indent',
        isDeleting && 'dm-row--deleting',
      )}
    >
      <Link
        to={templatePathWithId(template.id, location.search)}
        onClick={() => onWarmTemplate()}
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          textDecoration: 'none',
          color: 'inherit',
          cursor: 'pointer',
        }}
      >
        {template.is_pinned
          ? <Star size={13} color="#f59e0b" fill="#f59e0b" style={{ flexShrink: 0 }} />
          : <FileText size={13} color="#94a3b8" style={{ flexShrink: 0 }} />
        }
        <span
          title={template.name}
          style={{
            flex: 1, fontSize: 12, lineHeight: 1.4,
            color: isActive ? '#0f766e' : '#475569',
            fontWeight: isActive ? 600 : 400,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}
        >
          {template.name}
        </span>
      </Link>
      {isDeleting ? (
        <RowDeletingIndicator />
      ) : (
        <>
          <div className="dm-row-actions">
            <div ref={moveBtnRef}>
              <SidebarIconButton
                label={`Move ${template.name} to group`}
                variant="move"
                onClick={(e) => { e.stopPropagation(); setShowMoveDropdown((v) => !v) }}
              >
                <MoveHorizontal size={11} color="#0f766e" aria-hidden />
              </SidebarIconButton>
            </div>
            {showMoveDropdown && (
              <MoveToGroupDropdown
                currentGroupId={template.group_id}
                groups={groups}
                onMoveToGroup={onMoveToGroup}
                triggerRef={moveBtnRef}
                onClose={() => setShowMoveDropdown(false)}
              />
            )}
            <SidebarIconButton
              label={template.is_pinned ? `Unpin ${template.name}` : `Pin ${template.name}`}
              onClick={(e) => { e.stopPropagation(); onPin() }}
            >
              <Pin size={11} color={template.is_pinned ? '#f59e0b' : '#94a3b8'} aria-hidden />
            </SidebarIconButton>
            <SidebarIconButton
              label={`Delete ${template.name}`}
              variant="danger"
              onClick={(e) => { e.stopPropagation(); onDelete() }}
            >
              <Trash2 size={11} color="#dc2626" aria-hidden />
            </SidebarIconButton>
          </div>
          <span className="dm-template-row__version">
            v{versionNum}
          </span>
        </>
      )}
    </div>
  )
}

// ── Template group row ─────────────────────────────────────────────

interface TemplateGroupRowProps {
  group: TemplateGroupResponse
  templates: TemplateResponse[]
  activeTemplateId: string | null
  isDeletingGroup?: boolean
  deletingTemplateId?: string | null
  onWarmTemplate: (id: string) => void
  onDeleteTemplate: (id: string) => void
  onPinTemplate: (id: string) => void
  onMoveTemplateToGroup: (templateId: string, groupId: string | null) => void
  allTemplateGroups: Array<{ id: string; name: string }>
  onRenameGroup: (name: string) => void
  onDeleteGroup: () => void
}

function TemplateGroupRow({
  group, templates, activeTemplateId, isDeletingGroup = false, deletingTemplateId = null,
  onWarmTemplate, onDeleteTemplate, onPinTemplate,
  onMoveTemplateToGroup, allTemplateGroups,
  onRenameGroup, onDeleteGroup,
}: TemplateGroupRowProps) {
  const [expanded, setExpanded] = useState(true)
  const [editing, setEditing] = useState(false)

  return (
    <div style={{ marginBottom: 2 }}>
      <div
        className={clsx('dm-group-row', isDeletingGroup && 'dm-row--deleting')}
        onClick={() => !editing && !isDeletingGroup && setExpanded((v) => !v)}
        style={{ cursor: isDeletingGroup ? 'default' : 'pointer' }}
      >
        {expanded
          ? <ChevronDown size={12} color="#94a3b8" style={{ flexShrink: 0 }} aria-hidden />
          : <ChevronRight size={12} color="#94a3b8" style={{ flexShrink: 0 }} aria-hidden />
        }
        <FolderOpen size={13} color="#64748b" style={{ flexShrink: 0 }} aria-hidden />

        {editing ? (
          <EditableLabel
            value={group.name}
            onCommit={(v) => { onRenameGroup(v); setEditing(false) }}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <>
            <span
              className="dm-group-row__name"
              onDoubleClick={(e) => { e.stopPropagation(); setEditing(true) }}
            >
              {group.name}
            </span>
            <span className="dm-group-row__count">
              {templates.length}
            </span>
            {isDeletingGroup ? (
              <RowDeletingIndicator />
            ) : (
              <div className="dm-row-actions dm-group-row__actions">
                <SidebarIconButton
                  label={`Delete group ${group.name}`}
                  variant="danger"
                  onClick={(e) => { e.stopPropagation(); onDeleteGroup() }}
                >
                  <Trash2 size={11} color="#dc2626" aria-hidden />
                </SidebarIconButton>
              </div>
            )}
          </>
        )}
      </div>

      {expanded && templates.map((t) => (
        <TemplateRow
          key={t.id}
          template={t}
          isActive={t.id === activeTemplateId}
          isDeleting={deletingTemplateId === t.id}
          onWarmTemplate={() => onWarmTemplate(t.id)}
          onDelete={() => onDeleteTemplate(t.id)}
          onPin={() => onPinTemplate(t.id)}
          onMoveToGroup={(groupId) => onMoveTemplateToGroup(t.id, groupId)}
          groups={allTemplateGroups}
          indent
        />
      ))}
    </div>
  )
}

// ── Section header ────────────────────────────────────────────────

function SectionHeader({ label, action }: { label: string; action?: React.ReactNode }) {
  return (
    <div className="dm-sidebar-section">
      <span className="dm-sidebar-section__label">{label}</span>
      {action && <div className="dm-sidebar-section__actions">{action}</div>}
    </div>
  )
}

// ── Main sidebar ──────────────────────────────────────────────────

const DatamartSidebar: React.FC<DatamartSidebarProps> = ({
  sessions, activeSessionId, sessionsLoading,
  onWarmSession, onNewSession, onRenameSession, onDeleteSession,
  onMoveSessionToGroup,
  sessionGroups, onCreateSessionGroup, onRenameSessionGroup, onDeleteSessionGroup,
  templates, activeTemplateId, templatesLoading,
  onWarmTemplate, onDeleteTemplate, onPinTemplate,
  onMoveTemplateToGroup,
  templateGroups, onCreateTemplateGroup, onRenameTemplateGroup, onDeleteTemplateGroup,
  deletingSessionId = null,
  deletingTemplateId = null,
  deletingSessionGroupId = null,
  deletingTemplateGroupId = null,
}) => {
  const [creatingGroup, setCreatingGroup] = useState(false)
  const [newGroupName, setNewGroupName] = useState('')
  const newGroupRef = useRef<HTMLInputElement>(null)

  const [creatingTemplateGroup, setCreatingTemplateGroup] = useState(false)
  const [newTemplateGroupName, setNewTemplateGroupName] = useState('')
  const newTemplateGroupRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (creatingGroup) setTimeout(() => newGroupRef.current?.focus(), 50)
  }, [creatingGroup])

  useEffect(() => {
    if (creatingTemplateGroup) setTimeout(() => newTemplateGroupRef.current?.focus(), 50)
  }, [creatingTemplateGroup])

  const submitNewGroup = () => {
    const name = newGroupName.trim()
    if (name) onCreateSessionGroup(name)
    setNewGroupName('')
    setCreatingGroup(false)
  }

  const submitNewTemplateGroup = () => {
    const name = newTemplateGroupName.trim()
    if (name) onCreateTemplateGroup(name)
    setNewTemplateGroupName('')
    setCreatingTemplateGroup(false)
  }

  const [searchQuery, setSearchQuery] = useState('')
  const searchLower = searchQuery.trim().toLowerCase()

  const filteredSessions = useMemo(() => {
    if (!searchLower) return sessions
    return sessions.filter((s) => s.title.toLowerCase().includes(searchLower))
  }, [sessions, searchLower])

  const filteredTemplates = useMemo(() => {
    if (!searchLower) return templates
    return templates.filter((t) => t.name.toLowerCase().includes(searchLower))
  }, [templates, searchLower])

  // Partition sessions into grouped and ungrouped
  const groupedSessions: Record<string, SessionListItem[]> = {}
  const ungroupedSessions: SessionListItem[] = []
  for (const s of filteredSessions) {
    if (s.group_id) {
      if (!groupedSessions[s.group_id]) groupedSessions[s.group_id] = []
      groupedSessions[s.group_id].push(s)
    } else {
      ungroupedSessions.push(s)
    }
  }

  // Partition templates into grouped and ungrouped
  const groupedTemplates: Record<string, TemplateResponse[]> = {}
  const ungroupedTemplates: TemplateResponse[] = []
  for (const t of filteredTemplates) {
    if (t.group_id) {
      if (!groupedTemplates[t.group_id]) groupedTemplates[t.group_id] = []
      groupedTemplates[t.group_id].push(t)
    } else {
      ungroupedTemplates.push(t)
    }
  }

  const allSessionGroups = sessionGroups.map((g) => ({ id: g.id, name: g.name }))
  const allTemplateGroups = templateGroups.map((g) => ({ id: g.id, name: g.name }))

  return (
    <div className="datamart-workspace-sidebar">
      <div className="dm-sidebar-head">
        <p className="dm-sidebar-head__title">Workspaces</p>
        <label className="dm-sidebar-search">
          <Search size={15} color="#94a3b8" aria-hidden />
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search chats & templates…"
            aria-label="Search workspaces"
          />
        </label>
      </div>

      <div className="dm-sidebar-body">
      {/* ── TEMPLATES section ──────────────────────────────── */}
      <SectionHeader
        label="Templates"
        action={
          <button
            type="button"
            className="dm-sidebar-icon-btn"
            onClick={() => setCreatingTemplateGroup(true)}
            aria-label="New template group"
          >
            <FolderOpen size={13} aria-hidden />
          </button>
        }
      />

      {/* New template group input */}
      {creatingTemplateGroup && (
        <div className="dm-inline-create">
          <div className="dm-inline-create__box">
            <Folder size={13} color="#0d9488" aria-hidden />
            <label htmlFor="dm-new-template-group" className="dm-sr-only">Template group name</label>
            <input
              id="dm-new-template-group"
              ref={newTemplateGroupRef}
              className="dm-inline-create__input"
              value={newTemplateGroupName}
              onChange={(e) => setNewTemplateGroupName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') submitNewTemplateGroup()
                if (e.key === 'Escape') { setCreatingTemplateGroup(false); setNewTemplateGroupName('') }
              }}
              placeholder="Group name..."
            />
            <SidebarIconButton label="Create template group" onClick={submitNewTemplateGroup}>
              <Check size={11} color="#0d9488" aria-hidden />
            </SidebarIconButton>
            <SidebarIconButton
              label="Cancel"
              onClick={() => { setCreatingTemplateGroup(false); setNewTemplateGroupName('') }}
            >
              <X size={11} color="#94a3b8" aria-hidden />
            </SidebarIconButton>
          </div>
        </div>
      )}

      <div className="dm-sidebar-list">
        {templatesLoading ? (
          [0, 1, 2].map((i) => (
            <div key={i} className="dm-sidebar-skeleton" style={{ opacity: 1 - i * 0.2 }} />
          ))
        ) : filteredTemplates.length === 0 && templateGroups.length === 0 ? (
          <p className="dm-sidebar-empty">
            {searchLower ? 'No templates match your search.' : 'No templates yet. Use "Move to Template" on a result.'}
          </p>
        ) : (
          <>
            {/* Grouped templates */}
            {templateGroups.map((group) => (
              <TemplateGroupRow
                key={group.id}
                group={group}
                templates={groupedTemplates[group.id] ?? []}
                activeTemplateId={activeTemplateId}
                isDeletingGroup={deletingTemplateGroupId === group.id}
                deletingTemplateId={deletingTemplateId}
                onWarmTemplate={onWarmTemplate}
                onDeleteTemplate={onDeleteTemplate}
                onPinTemplate={onPinTemplate}
                onMoveTemplateToGroup={onMoveTemplateToGroup}
                allTemplateGroups={allTemplateGroups}
                onRenameGroup={(name) => onRenameTemplateGroup(group.id, name)}
                onDeleteGroup={() => onDeleteTemplateGroup(group.id)}
              />
            ))}
            {ungroupedTemplates.map((t) => (
              <TemplateRow
                key={t.id}
                template={t}
                isActive={t.id === activeTemplateId}
                isDeleting={deletingTemplateId === t.id}
                onWarmTemplate={() => onWarmTemplate(t.id)}
                onDelete={() => onDeleteTemplate(t.id)}
                onPin={() => onPinTemplate(t.id)}
                onMoveToGroup={(groupId) => onMoveTemplateToGroup(t.id, groupId)}
                groups={allTemplateGroups}
              />
            ))}
          </>
        )}
      </div>

      <div className="dm-sidebar-divider" />

      {/* ── WORKSPACES section ─────────────────────────────── */}
      <SectionHeader
        label="Chats"
        action={
          <div className="dm-sidebar-section__actions">
            <button
              type="button"
              className="dm-sidebar-icon-btn"
              onClick={() => setCreatingGroup(true)}
              aria-label="New chat group"
            >
              <FolderOpen size={13} aria-hidden />
            </button>
            <button
              type="button"
              className="dm-sidebar-icon-btn"
              onClick={onNewSession}
              aria-label="New chat"
            >
              <Plus size={13} aria-hidden />
            </button>
          </div>
        }
      />

      {/* New group input */}
      {creatingGroup && (
        <div className="dm-inline-create">
          <div className="dm-inline-create__box">
            <Folder size={13} color="#0d9488" aria-hidden />
            <label htmlFor="dm-new-chat-group" className="dm-sr-only">Chat group name</label>
            <input
              id="dm-new-chat-group"
              ref={newGroupRef}
              className="dm-inline-create__input"
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') submitNewGroup()
                if (e.key === 'Escape') { setCreatingGroup(false); setNewGroupName('') }
              }}
              placeholder="Group name..."
            />
            <SidebarIconButton label="Create chat group" onClick={submitNewGroup}>
              <Check size={11} color="#0d9488" aria-hidden />
            </SidebarIconButton>
            <SidebarIconButton
              label="Cancel"
              onClick={() => { setCreatingGroup(false); setNewGroupName('') }}
            >
              <X size={11} color="#94a3b8" aria-hidden />
            </SidebarIconButton>
          </div>
        </div>
      )}

      <div className="dm-sidebar-list">
        {sessionsLoading ? (
          [0, 1, 2, 3].map((i) => (
            <div key={i} className="dm-sidebar-skeleton" style={{ opacity: 1 - i * 0.15 }} />
          ))
        ) : (
          <>
            {/* Grouped sessions */}
            {sessionGroups.map((group) => (
              <GroupRow
                key={group.id}
                group={group}
                sessions={groupedSessions[group.id] ?? []}
                activeSessionId={activeSessionId}
                isDeletingGroup={deletingSessionGroupId === group.id}
                deletingSessionId={deletingSessionId}
                onWarmSession={onWarmSession}
                onRenameSession={onRenameSession}
                onDeleteSession={onDeleteSession}
                onMoveSessionToGroup={onMoveSessionToGroup}
                allSessionGroups={allSessionGroups}
                onRenameGroup={(name) => onRenameSessionGroup(group.id, name)}
                onDeleteGroup={() => onDeleteSessionGroup(group.id)}
              />
            ))}
            {ungroupedSessions.map((s) => (
              <SessionRow
                key={s.id}
                session={s}
                isActive={s.id === activeSessionId}
                isDeleting={deletingSessionId === s.id}
                onWarmSession={() => onWarmSession(s.id)}
                onRename={(title) => onRenameSession(s.id, title)}
                onDelete={() => onDeleteSession(s.id)}
                onMoveToGroup={(groupId) => onMoveSessionToGroup(s.id, groupId)}
                groups={allSessionGroups}
              />
            ))}

            {filteredSessions.length === 0 && (
              <p className="dm-sidebar-empty">
                {searchLower ? 'No chats match your search.' : 'No chats yet. Start a new conversation.'}
              </p>
            )}
          </>
        )}
      </div>
      </div>
    </div>
  )
}

export default DatamartSidebar
