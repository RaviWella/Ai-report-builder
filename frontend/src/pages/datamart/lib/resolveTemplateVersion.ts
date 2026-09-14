import type { TemplateVersionResponse } from '../../../services/datamartService'

export interface ResolveActiveTemplateVersionInput {
  templateId: string
  versions: TemplateVersionResponse[]
  activeVersionId: string | null
  latestFromTemplate: TemplateVersionResponse | null | undefined
}

/** Pick the version row that belongs to `templateId` (never reuse another template's cache). */
export function resolveActiveTemplateVersion({
  templateId,
  versions,
  activeVersionId,
  latestFromTemplate,
}: ResolveActiveTemplateVersionInput): TemplateVersionResponse | null {
  const scoped = versions.filter((v) => v.template_id === templateId)

  if (activeVersionId) {
    const selected = scoped.find((v) => v.id === activeVersionId)
    if (selected) return selected
  }

  const fromList = scoped.find((v) => v.is_latest) ?? scoped[0] ?? null
  if (fromList) return fromList

  if (latestFromTemplate && latestFromTemplate.template_id === templateId) {
    return latestFromTemplate
  }

  return null
}
