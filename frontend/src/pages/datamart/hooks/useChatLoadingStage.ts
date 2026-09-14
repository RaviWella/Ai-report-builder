/**
 * Progressive pipeline loading for datamart chat (until SSE/streaming exists).
 * Labels match backend trace step ids in `pipelineStepCatalog.ts`.
 */
import { useEffect, useState } from 'react'
import {
  CHAT_LOADING_PIPELINE_STEPS,
  type PipelineStepId,
} from '../lib/pipelineStepCatalog'

export type ChatLoadingStageId = PipelineStepId

export interface ChatLoadingStage {
  id: ChatLoadingStageId
  label: string
}

const STAGES: ChatLoadingStage[] = CHAT_LOADING_PIPELINE_STEPS

/** Advance timers (ms from start) — progressive feel without a long stall on the last step. */
const ADVANCE_AT_MS = [0, 1_200, 3_500]

export interface UseChatLoadingStageOptions {
  /** When true, mark every step complete (brief success before reply mounts). */
  finishing?: boolean
}

export function useChatLoadingStage(
  active: boolean,
  options?: UseChatLoadingStageOptions,
): ChatLoadingStage {
  const finishing = options?.finishing ?? false
  const [index, setIndex] = useState(0)

  useEffect(() => {
    if (!active && !finishing) {
      setIndex(0)
      return undefined
    }

    if (finishing) {
      setIndex(STAGES.length - 1)
      return undefined
    }

    setIndex(0)
    const timers = ADVANCE_AT_MS.slice(1).map((ms, i) =>
      window.setTimeout(() => setIndex(i + 1), ms),
    )

    return () => {
      for (const t of timers) window.clearTimeout(t)
    }
  }, [active, finishing])

  if (finishing) {
    return STAGES[STAGES.length - 1] ?? STAGES[0]
  }

  return STAGES[Math.min(index, STAGES.length - 1)] ?? STAGES[0]
}

export function getChatLoadingStageIndex(stage: ChatLoadingStage): number {
  return STAGES.findIndex((s) => s.id === stage.id)
}

export function getChatLoadingProgress(finishing: boolean, stage: ChatLoadingStage): number {
  const idx = getChatLoadingStageIndex(stage)
  if (finishing) return 100
  return Math.round(((idx + 0.35) / STAGES.length) * 100)
}

export { STAGES as CHAT_LOADING_STAGES }
