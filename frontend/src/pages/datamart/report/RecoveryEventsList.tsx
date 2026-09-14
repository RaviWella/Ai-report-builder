/**
 * Recovery loop events from the simple datamart agent (schema expand, repair, retry).
 */
import React from 'react'
import type { RecoveryEvent } from '../lib/pipelineTrace'
import { dmColors, dmSpace } from '../lib/tokens'
import { dmCopy } from '../lib/copy'

export interface RecoveryEventsListProps {
  events: RecoveryEvent[] | undefined | null
  compact?: boolean
}

const RecoveryEventsList: React.FC<RecoveryEventsListProps> = ({
  events,
  compact = false,
}) => {
  if (!events?.length) return null

  return (
    <div
      data-testid="datamart-recovery-events"
      style={{
        marginTop: compact ? dmSpace.sm : dmSpace.md,
        padding: compact ? '8px 10px' : '10px 14px',
        borderRadius: 8,
        background: '#fffbeb',
        border: '1px solid #fde68a',
      }}
    >
      <div
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: '#92400e',
          marginBottom: 6,
        }}
      >
        {dmCopy.pipeline.recoveryTitle}
        {events.length > 0 && (
          <span style={{ fontWeight: 400, color: dmColors.textMuted, marginLeft: 8 }}>
            {dmCopy.pipeline.recoveryAttempt(
              events[events.length - 1]?.attempt ?? events.length,
              events.length,
            )}
          </span>
        )}
      </div>
      <ul
        style={{
          margin: 0,
          paddingLeft: 18,
          fontSize: 12,
          color: dmColors.text,
          lineHeight: 1.45,
        }}
      >
        {events.map((e, i) => (
          <li key={`${e.attempt}-${e.action}-${i}`} style={{ marginBottom: 4 }}>
            {e.user_message}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default RecoveryEventsList
