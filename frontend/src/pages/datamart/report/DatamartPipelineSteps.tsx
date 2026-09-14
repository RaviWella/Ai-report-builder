/**
 * Ordered agent pathway for one datamart turn (mirrors backend pipeline_trace).
 */
import React, { useState } from 'react'
import { Check, ChevronDown, ChevronRight, Circle, Loader2, Minus, X } from 'lucide-react'
import type { PipelineStep, PipelineStepStatus, PipelineTrace } from '../lib/pipelineTrace'
import { dmColors, dmRadius, dmSpace } from '../lib/tokens'
import { dmCopy } from '../lib/copy'

export interface DatamartPipelineStepsProps {
  trace: PipelineTrace
  /** When true, show a compact single-line summary only. */
  compact?: boolean
}

function statusIcon(status: PipelineStepStatus) {
  switch (status) {
    case 'completed':
      return <Check size={14} color={dmColors.brand} aria-hidden />
    case 'running':
      return (
        <Loader2
          size={14}
          color={dmColors.brand}
          style={{ animation: 'spin 1s linear infinite' }}
          aria-hidden
        />
      )
    case 'warning':
      return <Circle size={14} color="#d97706" fill="#fcd34d" aria-hidden />
    case 'failed':
    case 'blocked':
      return <X size={14} color="#b91c1c" aria-hidden />
    case 'skipped':
      return <Minus size={14} color={dmColors.textSubtle} aria-hidden />
    default:
      return (
        <span
          style={{
            width: 14,
            height: 14,
            borderRadius: '50%',
            border: `2px solid ${dmColors.border}`,
            flexShrink: 0,
          }}
          aria-hidden
        />
      )
  }
}

const DatamartPipelineSteps: React.FC<DatamartPipelineStepsProps> = ({
  trace,
  compact = false,
}) => {
  const [open, setOpen] = useState(!compact)
  const completed = trace.steps.filter((s) => s.status === 'completed').length
  const failed = trace.steps.some((s) =>
    ['failed', 'blocked'].includes(s.status),
  )

  if (compact && !open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-testid="datamart-pipeline-steps-compact"
        style={{
          margin: `0 ${dmSpace.lg} ${dmSpace.sm}`,
          padding: '6px 10px',
          fontSize: 12,
          color: dmColors.textMuted,
          background: 'transparent',
          border: `1px dashed ${dmColors.border}`,
          borderRadius: dmRadius.sm,
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        {dmCopy.pipeline.compactSummary(completed, trace.steps.length, failed)}
      </button>
    )
  }

  return (
    <div
      data-testid="datamart-pipeline-steps"
      className="dm-pipeline-steps"
      style={{
        margin: `${dmSpace.md} ${dmSpace.lg}`,
        marginBottom: dmSpace.sm,
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '10px 14px',
          border: 'none',
          background: dmColors.surface,
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        <span style={{ fontSize: 13, fontWeight: 600, color: dmColors.text }}>
          {dmCopy.pipeline.panelTitle}
        </span>
        <span style={{ fontSize: 12, color: dmColors.textMuted, marginLeft: 'auto' }}>
          {completed}/{trace.steps.length} steps
          {trace.repair_attempts_used > 0 &&
            ` · ${trace.repair_attempts_used}/${trace.repair_attempts_max} repair`}
        </span>
      </button>

      {open && (
        <ol
          style={{
            margin: 0,
            padding: '10px 14px 14px 14px',
            listStyle: 'none',
          }}
        >
          {trace.steps.map((step: PipelineStep) => (
            <li
              key={step.id}
              data-testid={`pipeline-step-${step.id}`}
              data-status={step.status}
              className="dm-pipeline-steps__item"
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                padding: '5px 0',
                fontSize: 13,
                color:
                  step.status === 'pending' || step.status === 'skipped'
                    ? dmColors.textSubtle
                    : dmColors.text,
              }}
            >
              <span style={{ marginTop: 2, flexShrink: 0 }}>
                {statusIcon(step.status)}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: step.status === 'running' ? 600 : 500 }}>
                  {step.label}
                  {step.duration_ms != null && (
                    <span
                      style={{
                        marginLeft: 8,
                        fontWeight: 400,
                        fontSize: 11,
                        color: dmColors.textMuted,
                      }}
                    >
                      {step.duration_ms} ms
                    </span>
                  )}
                </div>
                {step.detail && (
                  <div
                    style={{
                      marginTop: 2,
                      fontSize: 12,
                      color: dmColors.textMuted,
                      lineHeight: 1.45,
                      wordBreak: 'break-word',
                    }}
                  >
                    {step.detail}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

export default DatamartPipelineSteps
