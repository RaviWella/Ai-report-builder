import type { ReportWidgetKind } from './reportLayout'

export const EXPORT_WIDGET_KIND_META: Record<
  ReportWidgetKind,
  { icon: string; short: string }
> = {
  summary: { icon: '📝', short: 'Summary' },
  sql: { icon: '⌘', short: 'SQL' },
  transformations: { icon: '⚙', short: 'Transform' },
  table: { icon: '▦', short: 'Table' },
  charts: { icon: '📊', short: 'Charts' },
}
