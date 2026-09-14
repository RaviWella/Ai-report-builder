/**
 * Loading card — live pipeline trace from SSE when available, staged fallback otherwise.
 */
import React, { useMemo } from 'react'
import { Check, Loader2, Minus, Sparkles, X } from 'lucide-react'
import {
  CHAT_LOADING_STAGES,
  getChatLoadingProgress,
  getChatLoadingStageIndex,
  type ChatLoadingStage,
} from '../hooks/useChatLoadingStage'
import type { PipelineStep, PipelineStepStatus, PipelineTrace } from '../lib/pipelineTrace'
import { dmColors } from '../lib/tokens'
import { dmCopy } from '../lib/copy'
import RecoveryEventsList from '../report/RecoveryEventsList'

export interface DatamartLoadingTurnProps {
  stage: ChatLoadingStage
  finishing?: boolean
  /** Real-time trace from ``/datamart/chat/stream``. */
  liveTrace?: PipelineTrace | null
}

function liveProgress(trace: PipelineTrace, finishing: boolean): number {
  const steps = trace.steps
  if (!steps.length) return finishing ? 100 : 8
  const weights: Record<PipelineStepStatus, number> = {
    completed: 1,
    warning: 1,
    running: 0.55,
    failed: 1,
    blocked: 1,
    skipped: 0.4,
    pending: 0,
  }
  let sum = 0
  for (const s of steps) sum += weights[s.status] ?? 0
  const pct = (sum / steps.length) * 100
  return finishing ? 100 : Math.min(96, Math.round(pct))
}

function liveStepIcon(status: PipelineStepStatus) {
  switch (status) {
    case 'completed':
      return <Check size={15} color={dmColors.brand} />
    case 'running':
      return <Loader2 size={15} color={dmColors.brand} className="dm-spin" />
    case 'warning':
      return <Minus size={15} color="#d97706" />
    case 'failed':
    case 'blocked':
      return <X size={15} color="#b91c1c" />
    case 'skipped':
      return <Minus size={15} color={dmColors.textSubtle} />
    default:
      return <span className="dm-loading-turn__step-dot" />
  }
}

function LiveStepRow({ step, index }: { step: PipelineStep; index: number }) {
  const done = step.status === 'completed' || step.status === 'warning'
  const failed = step.status === 'failed' || step.status === 'blocked'
  const current = step.status === 'running'
  return (
    <li
      key={step.id}
      className={[
        'dm-loading-turn__step',
        'dm-loading-turn__step--live',
        done ? 'dm-loading-turn__step--done' : '',
        current ? 'dm-loading-turn__step--active' : '',
        failed ? 'dm-loading-turn__step--failed' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      style={{ animationDelay: `${index * 0.03}s` }}
    >
      <span className="dm-loading-turn__step-icon" aria-hidden>
        {liveStepIcon(step.status)}
      </span>
      <div className="dm-loading-turn__step-body">
        <span className="dm-loading-turn__step-label">
          {step.label}
          {step.duration_ms != null && (
            <span className="dm-loading-turn__step-ms">{step.duration_ms} ms</span>
          )}
        </span>
        {step.detail && (
          <span className="dm-loading-turn__step-detail">{step.detail}</span>
        )}
      </div>
    </li>
  )
}

const DatamartLoadingTurn: React.FC<DatamartLoadingTurnProps> = ({
  stage,
  finishing = false,
  liveTrace = null,
}) => {
  const useLive = (liveTrace?.steps?.length ?? 0) > 0
  const currentIndex = finishing
    ? CHAT_LOADING_STAGES.length
    : getChatLoadingStageIndex(stage)
  const progress = useLive && liveTrace
    ? liveProgress(liveTrace, finishing)
    : getChatLoadingProgress(finishing, stage)

  const runningStep = useMemo(
    () => liveTrace?.steps.find((s) => s.status === 'running'),
    [liveTrace],
  )

  const subtitle = useLive
    ? runningStep?.detail ??
      (finishing
        ? dmCopy.pipeline.loadingCompleteSubtitle
        : runningStep?.label ?? dmCopy.pipeline.loadingLiveSubtitle)
    : finishing
      ? dmCopy.pipeline.loadingCompleteSubtitle
      : dmCopy.pipeline.loadingSubtitle

  return (
    <div
      className={`dm-loading-turn${finishing ? ' dm-loading-turn--success' : ''}${useLive ? ' dm-loading-turn--live' : ''}`}
      role="status"
      aria-live="polite"
      aria-busy={!finishing}
    >
      <div
        className="dm-loading-turn__progress"
        role="progressbar"
        aria-valuenow={progress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Pipeline progress"
      >
        <div
          className="dm-loading-turn__progress-fill"
          style={{ transform: `scaleX(${progress / 100})` }}
        />
      </div>

      <div className="dm-loading-turn__header">
        <span className="dm-loading-turn__icon" aria-hidden>
          {finishing ? (
            <Check size={18} color={dmColors.brand} />
          ) : (
            <Sparkles size={18} color={dmColors.brand} />
          )}
        </span>
        <div>
          <p className="dm-loading-turn__title">
            {finishing
              ? dmCopy.pipeline.loadingCompleteTitle
              : dmCopy.pipeline.loadingTitle}
          </p>
          <p className="dm-loading-turn__subtitle">{subtitle}</p>
        </div>
      </div>

      <ul className="dm-loading-turn__steps">
        {useLive && liveTrace
          ? liveTrace.steps.map((step, i) => (
              <LiveStepRow key={step.id} step={step} index={i} />
            ))
          : CHAT_LOADING_STAGES.map((s, i) => {
              const done = finishing || i < currentIndex
              const current = !finishing && i === currentIndex
              return (
                <li
                  key={s.id}
                  className={[
                    'dm-loading-turn__step',
                    done ? 'dm-loading-turn__step--done' : '',
                    current ? 'dm-loading-turn__step--active' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  style={{ animationDelay: `${i * 0.04}s` }}
                >
                  <span className="dm-loading-turn__step-icon" aria-hidden>
                    {done ? (
                      <Check size={15} color={dmColors.brand} />
                    ) : current ? (
                      <Loader2
                        size={15}
                        color={dmColors.brand}
                        className="dm-spin"
                      />
                    ) : (
                      <span className="dm-loading-turn__step-dot" />
                    )}
                  </span>
                  <span className="dm-loading-turn__step-label">{s.label}</span>
                </li>
              )
            })}
      </ul>
      {useLive && liveTrace?.recovery_events?.length ? (
        <RecoveryEventsList events={liveTrace.recovery_events} compact />
      ) : null}
    </div>
  )
}

export default DatamartLoadingTurn
