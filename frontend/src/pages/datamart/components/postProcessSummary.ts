/**
 * Human-readable lines for post_process_config steps (datamart agent).
 */
export function describePostProcessSteps(
  steps: Array<Record<string, unknown>> | null | undefined,
): string[] {
  if (!steps?.length) return []
  return steps.map((step, i) => {
    const t = String(step.type ?? 'unknown')
    const n = i + 1
    if (t === 'add_percentage_column') {
      const src = String(step.source_column ?? '?')
      const dest = String(step.new_column ?? '?')
      return `${n}. Percent of total: "${src}" → new column "${dest}"`
    }
    if (t === 'append_aggregate_row') {
      const label = String(step.label ?? 'Summary')
      return `${n}. Append summary row: "${label}"`
    }
    if (t === 'append_per_group_aggregate_rows') {
      const gc = String(step.group_column ?? '?')
      return `${n}. Append per-group summary rows (grouped by "${gc}")`
    }
    if (t === 'add_derived_column') {
      const dest = String(step.new_column ?? '?')
      return `${n}. Derived column: "${dest}"`
    }
    return `${n}. ${t}`
  })
}
