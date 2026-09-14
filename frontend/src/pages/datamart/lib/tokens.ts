/**
 * Datamart UI tokens — aligned with MintHRM root design system (index.css).
 */
export const dmColors = {
  text: '#0f172a',
  textMuted: '#64748b',
  textSubtle: '#94a3b8',
  border: '#e2e8f0',
  borderLight: '#f1f5f9',
  surface: '#ffffff',
  surfaceMuted: '#f8fafc',
  surfaceInset: '#fafbfc',
  brand: '#0f766e',
  brandHover: '#0d9488',
  brandMuted: '#f0fdfa',
  brandBorder: '#99f6e4',
  /** Active selection, tabs, panel focus — same teal family as HR shell */
  accent: '#0f766e',
  danger: '#dc2626',
  dangerBg: '#fef2f2',
  dangerBorder: '#fecaca',
  /** Template / modify panels — teal tint, not purple */
  purple: '#0f766e',
  purpleBg: '#f0fdfa',
  purpleBorder: '#99f6e4',
  sqlBg: '#0f172a',
  sqlText: '#e2e8f0',
  userBubble: '#334155',
  userAvatar: '#475569',
} as const

export const dmRadius = {
  sm: 6,
  md: 8,
  lg: 12,
  pill: 20,
} as const

export const dmFont = {
  sans: 'inherit',
  mono: 'ui-monospace, Menlo, Monaco, "Cascadia Code", monospace',
} as const

export const dmSpace = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
} as const

/** Chart series — teal-first, no indigo */
export const dmChartPalette = [
  '#0f766e',
  '#0d9488',
  '#14b8a6',
  '#2dd4bf',
  '#0891b2',
  '#f59e0b',
  '#64748b',
  '#115e59',
] as const
