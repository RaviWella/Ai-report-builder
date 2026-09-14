/**
 * Derives composer context from the latest assistant turn in the thread.
 */
import type {
  DatamartResponse,
  TemplateVersionResponse,
} from '../../../services/datamartService'
import { templateVersionToReport } from '../templates/versionToReport'
import { truncateContextLabel } from './quickActionPrompts'
import {
  buildScenarioList,
  type ScenarioDescriptor,
  type DatamartReportLayoutV1,
} from './reportLayout'
import { isMultiScenarioReport } from './modifyScenarioTargets'

export interface LatestTurnContext {
  messageId?: string
  sessionId?: string
  question: string
  sql: string | null
  columns: string[]
  hasLoadedResults: boolean
  canGenerateChart: boolean
  scenarios: ScenarioDescriptor[]
  multiScenario: boolean
}

export interface ChatTurnLike {
  role: 'user' | 'assistant'
  data?: DatamartResponse
  messageId?: string
  sessionId?: string
}

export function findLatestAssistantTurn<T extends ChatTurnLike>(messages: T[]): T | null {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const m = messages[i]
    if (m.role === 'assistant' && m.data) return m
  }
  return null
}

export function buildLatestTurnContext(
  turn: ChatTurnLike | null,
  snapshot?: {
    columns: string[]
    hasLoadedResults: boolean
    canGenerateChart: boolean
  } | null,
): LatestTurnContext | null {
  if (!turn?.data) return null
  const data = turn.data
  const columns =
    snapshot?.columns?.length
      ? snapshot.columns
      : data.columns.length > 0
        ? data.columns
        : []
  const hasLoadedResults =
    snapshot?.hasLoadedResults ?? (data.columns.length > 0 && data.rows.length > 0)
  const canGenerateChart =
    snapshot?.canGenerateChart ?? (hasLoadedResults && !!turn.messageId && !!turn.sessionId)

  const layout = data.report_layout as DatamartReportLayoutV1 | null | undefined
  const scenarios = buildScenarioList(
    layout?.primary_label,
    data.question,
    data.extra_result_blocks?.map((b) => ({
      block_id: b.block_id,
      title: b.title,
    })),
  )

  return {
    messageId: turn.messageId,
    sessionId: turn.sessionId,
    question: data.question?.trim() || 'Last report',
    sql: data.sql,
    columns,
    hasLoadedResults,
    canGenerateChart,
    scenarios,
    multiScenario: isMultiScenarioReport(scenarios),
  }
}

export function formatEditingPillLabel(question: string): string {
  return `Editing: ${truncateContextLabel(question)}`
}

function buildContextFromReportData(
  data: DatamartResponse,
  label: string,
  snapshot?: {
    columns: string[]
    hasLoadedResults: boolean
    canGenerateChart: boolean
  } | null,
): LatestTurnContext | null {
  if (!data.sql?.trim()) return null
  const columns =
    snapshot?.columns?.length
      ? snapshot.columns
      : data.columns.length > 0
        ? data.columns
        : []
  const hasLoadedResults =
    snapshot?.hasLoadedResults ?? (data.columns.length > 0 && data.rows.length > 0)
  const canGenerateChart = snapshot?.canGenerateChart ?? hasLoadedResults

  const layout = data.report_layout as DatamartReportLayoutV1 | null | undefined
  const scenarios = buildScenarioList(
    layout?.primary_label,
    data.question,
    data.extra_result_blocks?.map((b) => ({
      block_id: b.block_id,
      title: b.title,
    })),
  )

  return {
    question: data.question?.trim() || label,
    sql: data.sql,
    columns,
    hasLoadedResults,
    canGenerateChart,
    scenarios,
    multiScenario: isMultiScenarioReport(scenarios),
  }
}

/** Composer context for template modify (saved version + optional run snapshot). */
export function buildTemplateEditingContext(
  version: TemplateVersionResponse,
  templateName?: string,
  snapshot?: {
    columns: string[]
    hasLoadedResults: boolean
    canGenerateChart: boolean
  } | null,
): LatestTurnContext | null {
  const data = templateVersionToReport(version, templateName)
  return buildContextFromReportData(
    data,
    templateName || `Version ${version.version_num}`,
    snapshot,
  )
}

/** Composer context from unsaved draft preview (after a modify-chat turn). */
export function buildDraftEditingContext(
  draft: DatamartResponse,
  snapshot?: {
    columns: string[]
    hasLoadedResults: boolean
    canGenerateChart: boolean
  } | null,
): LatestTurnContext | null {
  return buildContextFromReportData(draft, draft.question?.trim() || 'Draft preview', snapshot)
}
