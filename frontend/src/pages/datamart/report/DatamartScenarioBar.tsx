/**
 * Layout mode toggle (Sections vs Canvas) and scenario tabs for canvas-only selection.
 */
import React, { useState } from 'react'
import { LayoutGrid, List, Pencil, Check, X } from 'lucide-react'
import type { ScenarioDescriptor } from '../lib/reportLayout'
import { panelHeaderColor } from './DatamartReportCanvas'
import { dmColors, dmRadius, dmSpace } from '../lib/tokens'
import { dmCopy } from '../lib/copy'

export interface DatamartScenarioBarProps {
  scenarios: ScenarioDescriptor[]
  activePanelId: string
  canvasMode: boolean
  onSelectPanel: (panelId: string) => void
  onRename: (panelId: string, label: string) => void
  onViewModeChange: (mode: 'stacked' | 'canvas') => void
}

const DatamartScenarioBar: React.FC<DatamartScenarioBarProps> = ({
  scenarios,
  activePanelId,
  canvasMode,
  onSelectPanel,
  onRename,
  onViewModeChange,
}) => {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')

  if (scenarios.length === 0) return null

  const showScenarioTabs = canvasMode && scenarios.length > 1

  const startEdit = (s: ScenarioDescriptor) => {
    setEditingId(s.panelId)
    setDraft(s.label)
  }

  const commitEdit = (panelId: string) => {
    onRename(panelId, draft)
    setEditingId(null)
    setDraft('')
  }

  return (
    <div
      data-testid="datamart-scenario-bar"
      style={{
        margin: `0 ${dmSpace.lg}px ${dmSpace.md}px`,
        padding: `${dmSpace.sm}px ${dmSpace.md}px`,
        background: dmColors.surfaceMuted,
        borderRadius: dmRadius.md,
        border: `1px solid ${dmColors.border}`,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: dmSpace.sm,
          flexWrap: 'wrap',
          marginBottom: canvasMode ? dmSpace.sm : 0,
        }}
      >
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: dmColors.textMuted,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}
        >
          {dmCopy.scenarios.barTitle}
        </span>
        <div style={{ display: 'flex', gap: 4 }} role="group" aria-label="Report layout mode">
          <button
            type="button"
            title="Show every scenario in Summary, Query, Results, and Charts"
            aria-pressed={!canvasMode}
            data-testid="datamart-view-mode-sections"
            onClick={() => onViewModeChange('stacked')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 11,
              fontWeight: 600,
              padding: '4px 8px',
              borderRadius: dmRadius.sm,
              border: `1px solid ${!canvasMode ? dmColors.accent : dmColors.border}`,
              background: !canvasMode ? '#ecfdf5' : dmColors.surface,
              color: !canvasMode ? dmColors.accent : dmColors.textMuted,
              cursor: 'pointer',
            }}
          >
            <List size={12} />
            {dmCopy.scenarios.sectionsMode}
          </button>
          <button
            type="button"
            title="Pick one scenario and customize the drag-and-drop canvas"
            aria-pressed={canvasMode}
            data-testid="datamart-view-mode-canvas"
            onClick={() => onViewModeChange('canvas')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 11,
              fontWeight: 600,
              padding: '4px 8px',
              borderRadius: dmRadius.sm,
              border: `1px solid ${canvasMode ? dmColors.accent : dmColors.border}`,
              background: canvasMode ? '#ecfdf5' : dmColors.surface,
              color: canvasMode ? dmColors.accent : dmColors.textMuted,
              cursor: 'pointer',
            }}
          >
            <LayoutGrid size={12} />
            {dmCopy.scenarios.canvasMode}
          </button>
        </div>
      </div>

      {showScenarioTabs ? (
        <div
          data-testid="datamart-scenario-tabs"
          style={{
            display: 'flex',
            gap: 8,
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
        >
          {scenarios.map((s) => {
            const active = s.panelId === activePanelId
            const editing = editingId === s.panelId
            const accent = panelHeaderColor(s.panelId, active)
            return (
              <div
                key={s.panelId}
                data-testid={`datamart-scenario-tab-${s.panelId}`}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: editing ? '4px 6px' : '6px 10px',
                  borderRadius: dmRadius.pill,
                  border: `1px solid ${active ? accent : dmColors.border}`,
                  background: active ? '#fff' : dmColors.surface,
                  boxShadow: active ? `0 0 0 1px ${accent}22` : 'none',
                }}
              >
                {editing ? (
                  <>
                    <input
                      autoFocus
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') commitEdit(s.panelId)
                        if (e.key === 'Escape') setEditingId(null)
                      }}
                      style={{
                        fontSize: 12,
                        border: `1px solid ${dmColors.border}`,
                        borderRadius: dmRadius.sm,
                        padding: '2px 6px',
                        width: 140,
                      }}
                    />
                    <button
                      type="button"
                      aria-label="Save name"
                      onClick={() => commitEdit(s.panelId)}
                      style={{ border: 'none', background: 'none', cursor: 'pointer', padding: 0 }}
                    >
                      <Check size={14} color={dmColors.accent} />
                    </button>
                    <button
                      type="button"
                      aria-label="Cancel"
                      onClick={() => setEditingId(null)}
                      style={{ border: 'none', background: 'none', cursor: 'pointer', padding: 0 }}
                    >
                      <X size={14} color={dmColors.textSubtle} />
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => onSelectPanel(s.panelId)}
                      style={{
                        border: 'none',
                        background: 'none',
                        cursor: 'pointer',
                        fontSize: 13,
                        fontWeight: active ? 600 : 500,
                        color: active ? dmColors.text : dmColors.textMuted,
                        padding: 0,
                      }}
                    >
                      {s.label}
                    </button>
                    <button
                      type="button"
                      aria-label={`Rename ${s.label}`}
                      onClick={() => startEdit(s)}
                      style={{
                        border: 'none',
                        background: 'none',
                        cursor: 'pointer',
                        padding: 0,
                        display: 'flex',
                      }}
                    >
                      <Pencil size={12} color={dmColors.textSubtle} />
                    </button>
                  </>
                )}
              </div>
            )
          })}
        </div>
      ) : (
        <p
          data-testid="datamart-scenario-sections-hint"
          style={{
            margin: `${dmSpace.sm}px 0 0`,
            fontSize: 12,
            color: dmColors.textMuted,
            lineHeight: 1.5,
          }}
        >
          {dmCopy.scenarios.sectionsHint}
        </p>
      )}
    </div>
  )
}

export default DatamartScenarioBar
