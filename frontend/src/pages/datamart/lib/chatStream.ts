/**
 * SSE client for POST /datamart/chat/stream
 */
import type { DatamartChatRequest, DatamartResponse, PipelineTrace } from '../../../services/datamartService'
import { API_BASE_URL, API_KEY, USER_ID } from '../../../env'
import { getActiveTenantId, getStoredAuthToken } from '../../../lib/activeTenant'

export type ChatStreamEvent =
  | { type: 'pipeline'; trace: PipelineTrace }
  | { type: 'result'; data: DatamartResponse }
  | { type: 'error'; message: string }
  | { type: 'done' }

function parseSseChunk(buffer: string): { events: ChatStreamEvent[]; rest: string } {
  const events: ChatStreamEvent[] = []
  const parts = buffer.split('\n\n')
  const rest = parts.pop() ?? ''
  for (const part of parts) {
    if (!part.trim()) continue
    let eventType = 'message'
    const dataLines: string[] = []
    for (const line of part.split('\n')) {
      if (line.startsWith('event:')) eventType = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    }
    if (!dataLines.length) continue
    const raw = dataLines.join('\n')
    try {
      const data = JSON.parse(raw) as unknown
      if (eventType === 'pipeline') {
        events.push({ type: 'pipeline', trace: data as PipelineTrace })
      } else if (eventType === 'result') {
        events.push({ type: 'result', data: data as DatamartResponse })
      } else if (eventType === 'error') {
        const msg =
          typeof data === 'object' && data !== null && 'message' in data
            ? String((data as { message: unknown }).message)
            : raw
        events.push({ type: 'error', message: msg })
      } else if (eventType === 'done') {
        events.push({ type: 'done' })
      }
    } catch {
      /* ignore malformed chunk */
    }
  }
  return { events, rest }
}

export interface ChatStreamHandlers {
  onPipeline?: (trace: PipelineTrace) => void
  onResult?: (data: DatamartResponse) => void
  onError?: (message: string) => void
}

/**
 * Stream a chat turn; resolves with the final response or throws on error.
 */
export async function streamDatamartChat(
  req: DatamartChatRequest,
  handlers: ChatStreamHandlers = {},
  signal?: AbortSignal,
): Promise<DatamartResponse> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
    'X-Tenant-Id': getActiveTenantId(),
  }
  if (USER_ID) headers['X-User-Id'] = USER_ID
  const token = getStoredAuthToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API_BASE_URL}/datamart/chat/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify(req),
    signal,
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: unknown }
      if (body.detail) detail = String(body.detail)
    } catch {
      /* use statusText */
    }
    throw new Error(detail || `Request failed (${res.status})`)
  }

  const reader = res.body?.getReader()
  if (!reader) throw new Error('Streaming not supported in this browser')

  const decoder = new TextDecoder()
  let buffer = ''
  let finalResult: DatamartResponse | null = null

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parsed = parseSseChunk(buffer)
    buffer = parsed.rest
    for (const ev of parsed.events) {
      if (ev.type === 'pipeline') handlers.onPipeline?.(ev.trace)
      else if (ev.type === 'result') {
        finalResult = ev.data
        handlers.onResult?.(ev.data)
      } else if (ev.type === 'error') {
        handlers.onError?.(ev.message)
        throw new Error(ev.message)
      }
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseChunk(`${buffer}\n\n`)
    for (const ev of parsed.events) {
      if (ev.type === 'pipeline') handlers.onPipeline?.(ev.trace)
      else if (ev.type === 'result') {
        finalResult = ev.data
        handlers.onResult?.(ev.data)
      } else if (ev.type === 'error') throw new Error(ev.message)
    }
  }

  if (!finalResult) throw new Error('Stream ended without a result')
  return finalResult
}
