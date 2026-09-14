/**
 * Merge chart_configs from API history with in-memory message state (never drop user charts).
 */
import type { MessageResponse } from '../../../services/datamartService'

export interface MessageWithCharts {
  messageId?: string
  role: string
  data?: { chart_configs?: unknown[] | null } | null
}

function chartList(v: unknown[] | null | undefined): unknown[] {
  return Array.isArray(v) ? v : []
}

function pickCharts(api: unknown[] | null | undefined, memory: unknown[] | null | undefined): unknown[] {
  const apiList = chartList(api)
  const memList = chartList(memory)
  if (apiList.length > 0) return apiList
  if (memList.length > 0) return memList
  return []
}

export function mergeChartConfigsFromHistory<T extends MessageWithCharts>(
  messages: T[],
  apiMessages: MessageResponse[],
): T[] {
  const apiById = new Map<string, unknown[] | null>()
  for (const m of apiMessages) {
    if (m.role === 'assistant') {
      apiById.set(m.id, m.chart_configs ?? null)
    }
  }

  return messages.map((msg) => {
    if (msg.role !== 'assistant' || !msg.messageId || !msg.data) return msg
    const merged = pickCharts(apiById.get(msg.messageId), msg.data.chart_configs)
    const current = chartList(msg.data.chart_configs)
    const unchanged =
      merged.length === current.length &&
      merged.every((c, i) => c === current[i])
    if (unchanged) return msg
    if (merged.length === 0 && current.length === 0) return msg
    return {
      ...msg,
      data: {
        ...msg.data,
        chart_configs: merged.length > 0 ? merged : null,
      },
    }
  })
}
