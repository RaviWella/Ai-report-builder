import { describe, expect, it } from 'vitest'
import type { PipelineTrace } from '../../../services/datamartService'

/** Minimal SSE parser test (mirrors chatStream.ts). */
function parseOne(block: string) {
  let eventType = 'message'
  const dataLines: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) eventType = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  return { eventType, data: JSON.parse(dataLines.join('\n')) }
}

describe('chatStream SSE parsing', () => {
  it('parses pipeline event', () => {
    const trace: PipelineTrace = {
      steps: [
        {
          id: 'schema_grounding',
          label: 'Load schema context',
          status: 'running',
        },
      ],
      repair_attempts_used: 0,
      repair_attempts_max: 1,
    }
    const block = `event: pipeline\ndata: ${JSON.stringify(trace)}`
    const { eventType, data } = parseOne(block)
    expect(eventType).toBe('pipeline')
    expect((data as PipelineTrace).steps[0]?.status).toBe('running')
  })
})
