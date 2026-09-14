/**
 * Structured post-processing details for CSV / PDF export.
 */
import { splitAppendSummaryFromFinal } from '../components/datamartResultSplit'
import { describePostProcessSteps } from '../components/postProcessSummary'

export interface PostProcessConfigRow {
  step: number
  parameter: string
  value: string
}

export interface PostProcessExportBlock {
  humanSteps: string[]
  configRows: PostProcessConfigRow[]
  summaryTable: { columns: string[]; rows: unknown[][] } | null
}

function formatConfigValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function buildPostProcessExportBlock(
  postProcessConfig: Array<Record<string, unknown>> | null | undefined,
  tableColumns: string[],
  tableRows: unknown[][],
  rawRows: unknown[][] | null | undefined,
): PostProcessExportBlock | null {
  if (!postProcessConfig?.length) return null

  const humanSteps = describePostProcessSteps(postProcessConfig)
  const configRows: PostProcessConfigRow[] = []

  postProcessConfig.forEach((step, index) => {
    const stepNum = index + 1
    for (const [key, value] of Object.entries(step)) {
      configRows.push({
        step: stepNum,
        parameter: key,
        value: formatConfigValue(value),
      })
    }
  })

  const split = splitAppendSummaryFromFinal(tableRows, rawRows ?? null, postProcessConfig)
  const summaryTable =
    split && split.summaryRows.length > 0
      ? { columns: tableColumns, rows: split.summaryRows }
      : null

  return { humanSteps, configRows, summaryTable }
}
