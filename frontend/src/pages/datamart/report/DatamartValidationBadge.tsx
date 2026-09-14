/**
 * Trust badge for datamart validation overall level.
 */
import React from 'react'
import { ShieldCheck, ShieldQuestion, ShieldX } from 'lucide-react'
import {
  TRUST_HINT,
  TRUST_LABEL,
  trustStyles,
  type TrustLevel,
} from '../lib/validation'
import { dmRadius, dmSpace } from '../lib/tokens'

export interface DatamartValidationBadgeProps {
  overall: TrustLevel
  compact?: boolean
}

const ICON: Record<TrustLevel, React.ReactNode> = {
  verified: <ShieldCheck size={14} aria-hidden />,
  plausible: <ShieldCheck size={14} aria-hidden />,
  needs_review: <ShieldQuestion size={14} aria-hidden />,
  blocked: <ShieldX size={14} aria-hidden />,
}

const DatamartValidationBadge: React.FC<DatamartValidationBadgeProps> = ({
  overall,
  compact = false,
}) => {
  const s = trustStyles(overall)
  return (
    <span
      title={TRUST_HINT[overall]}
      data-testid="datamart-validation-badge"
      data-trust={overall}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        fontSize: compact ? 11 : 12,
        fontWeight: 600,
        padding: compact ? '2px 8px' : '4px 10px',
        borderRadius: dmRadius.pill,
        background: s.bg,
        border: `1px solid ${s.border}`,
        color: s.color,
        marginRight: dmSpace.sm,
      }}
    >
      {ICON[overall]}
      {TRUST_LABEL[overall]}
    </span>
  )
}

export default DatamartValidationBadge
