/**
 * User-facing copy for the datamart workspace (i18n-ready).
 * Import from here instead of hard-coding HR/analytics strings in components.
 */
export const dmCopy = {
  report: {
    ariaLabel: 'Analytics report',
    toolbarAriaLabel: 'Report actions',
    exportSuccessTitle: 'Exported',
    exportPreparingTitle: 'Preparing export',
    exportPreparingBody: 'Rendering chart images…',
    exportFailedTitle: 'Export failed',
    exportSuccessBody: 'Results saved as CSV.',
    exportSuccessBodyWithCharts:
      'Report saved as ZIP (CSV + chart PNGs in charts/).',
    exportPdfSuccessBody: 'Report saved as PDF.',
    exportPdfSuccessBodyFull:
      'Report saved as PDF with chart images.',
  },
  exportComposer: {
    title: 'Customize export',
    subtitle:
      'Choose which parts of your report to include and drag blocks to set the order in the exported file.',
    canvasHint: 'Drag handles to reorder. Top-to-bottom order matches CSV and PDF sections.',
    exportCsv: 'Export CSV',
    exportPdf: 'Export PDF',
    customizeExport: 'Customize & export…',
    quickCsv: 'Quick CSV',
    quickPdf: 'Quick PDF',
  },
  toolbar: {
    runQuery: 'Run query',
    rerun: 'Re-run',
    running: 'Running…',
    export: 'Export',
    exportCsv: 'Export CSV',
    exportCsvOption: 'Download CSV (ZIP if charts)',
    exporting: 'Exporting…',
    exportPdfOption: 'Download PDF',
    addChart: 'Add chart',
    savingChart: 'Saving…',
    saveAsTemplate: 'Save as template',
    savedToTemplates: 'Saved to templates',
    undoModification: 'Undo change',
    undoing: 'Undoing…',
    tryAgain: 'Try again',
    regenerate: 'Regenerate',
  },
  statusBadge: {
    no_sql: 'No query',
    text_only: 'No data query',
    ready: 'Results loaded',
    not_loaded: 'Not loaded',
    running: 'Running…',
    error: 'Run failed',
    pipeline_error: 'Error',
  },
  pipeline: {
    panelTitle: 'How this answer was built',
    loadingTitle: 'Building your answer',
    loadingSubtitle: 'Linking schema, generating SQL, and running checks',
    loadingLiveSubtitle: 'Working through each step — details update live below',
    loadingCompleteTitle: 'Answer ready',
    loadingCompleteSubtitle: 'Opening your report…',
    compactSummary: (done: number, total: number, failed: boolean) =>
      failed
        ? `Agent pathway: ${done}/${total} steps (stopped early)`
        : `Agent pathway: ${done}/${total} steps — show details`,
    recoveryTitle: 'Adjustments while building your answer',
    recoveryAttempt: (n: number, max: number) => `Attempt ${n} of ${max}`,
  },
  validation: {
    panelTitle: 'Sources & validation',
    sourcesTitle: 'Retrieval sources',
    warningsTitle: 'Checks & warnings',
    groundingSource: 'Grounding',
    tablesLabel: 'Tables',
    columnsLabel: 'Columns in context',
    columnsJoinHint: 'Columns marked * are join keys only (not for SELECT).',
    topicsLabel: 'Topics',
    metricsLabel: 'Metrics',
    missingTables: 'Missing expected tables',
    bindingLabel: 'SQL binding',
    pipelineTitle: 'SQL pipeline',
    pipelineDomain: 'Domain',
    pipelineTier: 'Tier',
    pipelineSource: 'Source',
    pipelineLinkedTables: 'Linked tables',
    truncatedHint: 'Results may be truncated (row cap)',
    expandedHint: 'Schema context was expanded after SQL was generated',
    disclaimer:
      'Validation improves transparency; always confirm figures against your HR policies and source systems.',
  },
  scenarios: {
    barTitle: 'Scenarios in this report',
    sectionsHint: 'All scenarios are listed in the sections below.',
    sectionsMode: 'Sections',
    canvasMode: 'Canvas',
  },
  sections: {
    summary: 'Summary',
    query: 'Query',
    transformations: 'Transformations',
    results: 'Results',
    charts: 'Charts',
    sqlBadge: 'SQL',
  },
  results: {
    notLoadedTitle: 'Results are not loaded yet',
    notLoadedBody:
      'Use Run query above to load up to 500 rows from the warehouse.',
    running: 'Running query…',
    rowsBadge: (count: number) => `${count} rows`,
    notLoadedBadge: 'Not loaded',
  },
  textOnly: {
    body:
      'This answer does not include a query you can run. Try rephrasing or ask for a report with specific columns (e.g. employee name, branch, leave days).',
    learnMore: 'Why no data?',
    hideDetails: 'Hide details',
    helpBody:
      'The assistant must return SQL in the response. For totals under the detail table, it should use post-processing steps rather than only text. Start a new question if the thread is long.',
  },
  table: {
    noResults: 'No results found',
    rowLabel: (count: number) => `${count.toLocaleString()} ${count === 1 ? 'row' : 'rows'}`,
    capWarning: 'Results limited to 500 detail rows',
    appendWarning:
      'Includes appended rows (detail may be below the SQL row cap)',
    virtualizedHint: 'Large result set — scroll to browse rows',
  },
  template: {
    promotePlaceholder: 'Template name…',
    save: 'Save',
    draftPreviewTitle: 'Draft preview',
    draftPreviewBody:
      'Review SQL and transformations below. Run query and edit charts before saving a new version.',
    dismissDraft: 'Dismiss draft preview',
    modifyPanelHint: 'SQL change request — edit and send in the modify panel on the left.',
  },
} as const

export type DmCopyStatusBadgeKey = keyof typeof dmCopy.statusBadge
