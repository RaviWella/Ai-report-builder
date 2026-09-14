/**
 * Compact validation hint for an extra result block scenario.
 */
import React from 'react'
import { dmColors, dmRadius } from '../lib/tokens'
import { TRUST_LABEL, trustStyles, type TrustLevel } from '../lib/validation'

export interface DatamartExtraBlockValidationProps {
  validation: Record<string, unknown>
}

const DatamartExtraBlockValidation: React.FC<DatamartExtraBlockValidationProps> = ({
  validation,
}) => {
  const overall = String(validation.overall ?? '') as TrustLevel
  if (!overall || !(overall in TRUST_LABEL)) return null
  const s = trustStyles(overall)
  const gen = validation.generation as { warnings?: string[] } | undefined
  const warnings = gen?.warnings ?? []

  return (
    <div
      style={{
        marginBottom: 8,
        padding: '8px 10px',
        borderRadius: dmRadius.sm,
        background: s.bg,
        border: `1px solid ${s.border}`,
        fontSize: 12,
      }}
    >
      <strong style={{ color: s.color }}>Scenario check: {TRUST_LABEL[overall]}</strong>
      {warnings.length > 0 && (
        <ul style={{ margin: '6px 0 0', paddingLeft: 18, color: dmColors.text }}>
          {warnings.slice(0, 3).map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default DatamartExtraBlockValidation
