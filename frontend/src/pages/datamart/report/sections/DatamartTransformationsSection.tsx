/**
 * Post-process steps: human-readable summary + optional technical JSON.
 */
import React, { useState } from 'react'
import { Code2, Info } from 'lucide-react'
import { dmColors, dmFont, dmRadius, dmSpace } from '../../lib/tokens'

export interface DatamartTransformationsSectionProps {
  humanSteps: string[]
  rawConfig: Array<Record<string, unknown>> | null | undefined
  resultsLoaded: boolean
}

const DatamartTransformationsSection: React.FC<DatamartTransformationsSectionProps> = ({
  humanSteps,
  rawConfig,
  resultsLoaded,
}) => {
  const [showTechnical, setShowTechnical] = useState(false)
  const hasRaw = !!(rawConfig && rawConfig.length > 0)

  return (
    <div>
      {!resultsLoaded && hasRaw && (
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 10,
            marginBottom: dmSpace.md,
            padding: '10px 12px',
            borderRadius: dmRadius.md,
            background: '#fffbeb',
            border: '1px solid #fde68a',
            fontSize: 12,
            color: '#92400e',
            lineHeight: 1.55,
          }}
        >
          <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span>
            These steps run after the warehouse query. When you <strong>Run query</strong>, the
            table you see will include summary rows or extra columns from this pipeline.
          </span>
        </div>
      )}

      {humanSteps.length > 0 ? (
        <ul
          style={{
            margin: 0,
            paddingLeft: 18,
            fontSize: 13,
            color: dmColors.textMuted,
            lineHeight: 1.65,
          }}
        >
          {humanSteps.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : (
        <p style={{ margin: 0, fontSize: 13, color: dmColors.textMuted, lineHeight: 1.55 }}>
          Post-processing is configured but uses step types we do not summarize yet. Open technical
          details below.
        </p>
      )}

      {hasRaw && (
        <div style={{ marginTop: dmSpace.md }}>
          <button
            type="button"
            onClick={() => setShowTechnical((v) => !v)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              fontWeight: 600,
              color: dmColors.textMuted,
              background: dmColors.surfaceMuted,
              border: `1px solid ${dmColors.border}`,
              borderRadius: dmRadius.sm,
              padding: '6px 10px',
              cursor: 'pointer',
            }}
          >
            <Code2 size={13} aria-hidden />
            {showTechnical ? 'Hide technical JSON' : 'Show technical JSON'}
          </button>
          {showTechnical && (
            <pre
              style={{
                margin: `${dmSpace.sm}px 0 0`,
                fontSize: 11,
                lineHeight: 1.5,
                fontFamily: dmFont.mono,
                color: dmColors.sqlText,
                background: dmColors.sqlBg,
                borderRadius: dmRadius.md,
                padding: '12px 14px',
                overflowX: 'auto',
                maxHeight: 280,
              }}
            >
              {JSON.stringify(rawConfig, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

export default DatamartTransformationsSection

