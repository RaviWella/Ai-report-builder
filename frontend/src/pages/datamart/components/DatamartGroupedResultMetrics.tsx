/**
 * Key-value cards for compact GROUP BY results (no append post-process rows).
 */
import React from 'react'
import { LayoutGrid } from 'lucide-react'
import { dmColors } from '../lib/tokens'
import type { GroupedResultMetricsView } from '../lib/groupedResultMetrics'

export interface DatamartGroupedResultMetricsProps {
  view: GroupedResultMetricsView
}

const DatamartGroupedResultMetrics: React.FC<DatamartGroupedResultMetricsProps> = ({ view }) => (
  <section className="dm-grouped-metrics">
    <div className="dm-grouped-metrics__header">
      <LayoutGrid size={16} color={dmColors.brand} aria-hidden />
      <span className="dm-grouped-metrics__title">{view.sectionTitle}</span>
      <span className="dm-grouped-metrics__badge">
        {view.rows.length} {view.rows.length === 1 ? 'group' : 'groups'}
      </span>
    </div>
    <p className="dm-grouped-metrics__desc">
      Formatted breakdown from your query. The detail table below shows the same values.
    </p>
    <div className="dm-grouped-metrics__grid">
      {view.rows.map((row, idx) => (
        <div key={`${row.title}-${idx}`} className="dm-grouped-metrics__card">
          <div
            className={
              row.metrics.length > 0
                ? 'dm-grouped-metrics__card-title dm-grouped-metrics__card-title--bordered'
                : 'dm-grouped-metrics__card-title'
            }
          >
            {row.title}
          </div>
          {row.metrics.length === 1 ? (
            <div className="dm-grouped-metrics__value">{row.metrics[0].value}</div>
          ) : (
            <dl className="dm-grouped-metrics__metrics">
              {row.metrics.map((m) => (
                <div key={m.label} className="dm-grouped-metrics__metric-row">
                  <dt className="dm-grouped-metrics__metric-label">{m.label}</dt>
                  <dd className="dm-grouped-metrics__metric-value">{m.value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      ))}
    </div>
  </section>
)

export default DatamartGroupedResultMetrics
