/**
 * User-visible pipeline steps — aligned with backend `PIPELINE_STEP_DEFS`.
 * Loading UI shows the main path; repair/adequacy are folded into verify at runtime.
 */
export type PipelineStepId =
  | 'schema_grounding'
  | 'generate_sql'
  | 'execute_query'

export interface PipelineStepDef {
  id: PipelineStepId
  label: string
}

/** Fallback loading steps when SSE trace is not yet available. */
export const CHAT_LOADING_PIPELINE_STEPS: PipelineStepDef[] = [
  { id: 'schema_grounding', label: 'Load context (catalog + DataHub + warehouse)' },
  { id: 'generate_sql', label: 'Generate SQL' },
  { id: 'execute_query', label: 'Run query on warehouse' },
]

export const CHAT_LOADING_PIPELINE_LABELS = CHAT_LOADING_PIPELINE_STEPS.map(
  (s) => s.label,
)
