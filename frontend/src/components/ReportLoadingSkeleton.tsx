interface ReportMetricsSkeletonProps {

  count?: number;

  lead?: boolean;

}



export function ReportMetricsSkeleton({ count = 4, lead = false }: ReportMetricsSkeletonProps) {

  return (

    <div

      className={`grid grid-cols-2 gap-4 ${

        count >= 5 ? "md:grid-cols-3 lg:grid-cols-5" : count === 3 ? "md:grid-cols-3" : "md:grid-cols-4"

      }`}

      aria-busy="true"

      aria-label="Loading metrics"

    >

      {Array.from({ length: count }).map((_, i) => (

        <div

          key={i}

          className={`hrm-skeleton rounded-xl border ${

            lead ? "h-[7.5rem] border-teal-100 bg-teal-50/30" : "h-[5.5rem] border-slate-200 bg-white"

          }`}

        />

      ))}

    </div>

  );

}



export function ReportListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <ul
      className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white"
      aria-busy="true"
      aria-label="Loading report list"
    >
      {Array.from({ length: rows }).map((_, i) => (
        <li key={i} className="px-5 py-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div
              className="hrm-skeleton h-5 w-48 max-w-full rounded"
              style={{ opacity: 1 - i * 0.1 }}
            />
            <div className="flex flex-wrap gap-2">
              <div className="hrm-skeleton h-9 w-[5.5rem] rounded-md" />
              <div className="hrm-skeleton h-9 w-16 rounded-md" />
              <div className="hrm-skeleton h-9 w-14 rounded-md" />
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Card-style rows for settings/config lists (custom report definitions, ETL sources). */
export function ReportCardListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <ul className="space-y-3" aria-busy="true" aria-label="Loading report definitions">
      {Array.from({ length: count }).map((_, i) => (
        <li key={i}>
          <div className="rounded-xl border border-slate-200 bg-white p-4 sm:p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0 flex-1 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <div
                    className="hrm-skeleton h-5 w-52 max-w-full rounded"
                    style={{ opacity: 1 - i * 0.08 }}
                  />
                  <div className="hrm-skeleton h-5 w-16 rounded-full" />
                  <div className="hrm-skeleton h-5 w-24 rounded-full" />
                </div>
                <div className="hrm-skeleton h-4 w-44 max-w-full rounded" />
              </div>
              <div className="flex flex-wrap gap-2">
                <div className="hrm-skeleton h-9 w-[6.5rem] rounded-md" />
                <div className="hrm-skeleton h-9 w-[6.5rem] rounded-md" />
                <div className="hrm-skeleton h-9 w-[6.5rem] rounded-md" />
              </div>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function ReportTableSkeleton({ rows = 6 }: { rows?: number }) {

  return (

    <div

      className="overflow-hidden rounded-xl border border-slate-200 bg-white"

      aria-busy="true"

      aria-label="Loading table"

    >

      <div className="hrm-skeleton h-10 border-b border-slate-200 bg-slate-50" />

      {Array.from({ length: rows }).map((_, i) => (

        <div

          key={i}

          className="hrm-skeleton h-9 border-b border-slate-100 last:border-b-0"

          style={{ opacity: 1 - i * 0.08 }}

        />

      ))}

    </div>

  );

}


