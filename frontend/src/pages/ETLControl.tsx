/**
 * ETL Control — trigger and monitor HR ETL runs.
 */
import { Link } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { etlApi, getErrorMessage } from "../services/api";
import { etlSourcesService } from "../services/etlSourcesService";
import { useToast } from "../components/ui/Toast";
import ReportPageHeader from "../components/ReportPageHeader";
import ReportSection from "../components/ReportSection";
import { ReportTableSkeleton } from "../components/ReportLoadingSkeleton";
import { Play, RefreshCw, Zap, AlertCircle } from "lucide-react";
import clsx from "clsx";

function isTerminalRunStatus(status: unknown): boolean {
  return status === "completed" || status === "failed";
}

function runFailureMessage(run: Record<string, unknown>): string {
  const structured = run.error as { detail?: string; title?: string } | undefined;
  if (structured?.detail?.trim()) return structured.detail.trim();
  const raw = String(run.error_message ?? "").trim();
  if (raw) return raw;
  return "ETL failed with no error message recorded. Check API server logs.";
}

function formatTimestamp(value: unknown): string {
  if (value == null || value === "") return "—";
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString();
}

function formatRowCount(value: unknown): string {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  return n.toLocaleString();
}

function QueryErrorPanel({
  title,
  message,
  onRetry,
  retrying,
}: {
  title: string;
  message: string;
  onRetry: () => void;
  retrying?: boolean;
}) {
  return (
    <div
      className="flex flex-col gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 sm:flex-row sm:items-start"
      role="alert"
    >
      <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-600" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{title}</p>
        <p className="mt-1 break-words whitespace-pre-wrap text-red-800">{message}</p>
        <button
          type="button"
          onClick={onRetry}
          disabled={retrying}
          className="mt-3 rounded-lg border border-red-300 bg-white px-3 py-1.5 text-xs font-medium text-red-800 hover:bg-red-100 disabled:opacity-50"
        >
          {retrying ? "Retrying…" : "Try again"}
        </button>
      </div>
    </div>
  );
}

export default function ETLControl() {
  const qc = useQueryClient();
  const toast = useToast();
  const [runType, setRunType] = useState<"incremental" | "full_load">("incremental");
  const [pollFast, setPollFast] = useState(false);

  const {
    data: status,
    isLoading: statusLoading,
    isError: statusError,
    error: statusQueryError,
    isFetching: statusFetching,
    refetch: refetchStatus,
  } = useQuery({
    queryKey: ["etl-status"],
    queryFn: () => etlApi.getStatus(),
    refetchInterval: (query) => {
      const data = query.state.data as { runs?: { status?: string }[] } | undefined;
      const running =
        Array.isArray(data?.runs) && data.runs.some((r) => r.status === "running");
      return pollFast || running ? 3_000 : 10_000;
    },
  });

  const runs: Record<string, unknown>[] = Array.isArray(status?.runs)
    ? status.runs
    : status?.run_id
      ? [status as Record<string, unknown>]
      : [];

  const {
    data: watermarks,
    isLoading: watermarksLoading,
    isError: watermarksError,
    error: watermarksQueryError,
    refetch: refetchWatermarks,
  } = useQuery({
    queryKey: ["etl-watermarks"],
    queryFn: () => etlApi.getWatermarks(),
  });

  const {
    data: etlSources = [],
    isLoading: sourcesLoading,
    isError: sourcesError,
    error: sourcesQueryError,
    refetch: refetchSources,
  } = useQuery({
    queryKey: ["etl-sources"],
    queryFn: etlSourcesService.list,
  });

  const [lastQueuedRunId, setLastQueuedRunId] = useState<number | null>(null);
  const notifiedFailRef = useRef<number | null>(null);

  const clearStuck = useMutation({
    mutationFn: () => etlApi.clearStuckRuns(2),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["etl-status"] });
      if (data.count > 0) {
        setLastQueuedRunId(null);
        toast.success(
          `Cleared ${data.count} stuck run${data.count === 1 ? "" : "s"}`,
          data.cleared_run_ids.map((id) => `#${id}`).join(", ")
        );
      } else {
        toast.info("No stuck runs found", "No runs older than 2 hours were marked failed.");
      }
    },
    onError: (e: unknown) => {
      toast.error("Could not clear stuck runs", getErrorMessage(e));
    },
  });

  const trigger = useMutation({
    mutationFn: () => etlApi.triggerRun(runType),
    onSuccess: async (data) => {
      if (typeof data?.run_id === "number") {
        setLastQueuedRunId(data.run_id);
      }
      setPollFast(true);
      await qc.refetchQueries({ queryKey: ["etl-status"] });
      qc.invalidateQueries({ queryKey: ["etl-watermarks"] });
      setTimeout(() => setPollFast(false), 120_000);
    },
    onError: (e: unknown) => {
      setLastQueuedRunId(null);
      toast.error("ETL could not start", getErrorMessage(e));
    },
  });

  const trackedRun =
    lastQueuedRunId != null
      ? runs.find((r) => Number(r.run_id) === lastQueuedRunId)
      : undefined;

  useEffect(() => {
    if (!trackedRun || trackedRun.status !== "failed" || lastQueuedRunId == null) return;
    const id = Number(trackedRun.run_id);
    if (id !== lastQueuedRunId || notifiedFailRef.current === id) return;
    notifiedFailRef.current = id;
    toast.error(`ETL run #${id} failed`, runFailureMessage(trackedRun));
  }, [trackedRun, lastQueuedRunId, toast]);

  const hasRunning =
    runs.some((r) => r.status === "running") ||
    trigger.isPending ||
    (lastQueuedRunId != null &&
      (!trackedRun || !isTerminalRunStatus(trackedRun.status)));

  const hasSources = !sourcesError && etlSources.length > 0;
  const sourceNames = etlSources.map((s) => s.display_name).join(", ");

  const handleRunEtl = () => {
    if (!hasSources || hasRunning || trigger.isPending) return;
    if (runType === "full_load") {
      const ok = window.confirm(
        "Full load truncates staging tables and reloads all data from every configured source. " +
          "This can take a long time and may affect downstream reports until it completes.\n\n" +
          "Continue with full load?"
      );
      if (!ok) return;
    }
    trigger.mutate();
  };

  const handleClearStuck = () => {
    const ok = window.confirm(
      "Mark ETL runs stuck in \"running\" for more than 2 hours as failed? " +
        "Use this only when a run is blocking new extractions."
    );
    if (!ok) return;
    clearStuck.mutate();
  };

  const refreshAll = () => {
    void refetchStatus();
    void refetchWatermarks();
    void refetchSources();
  };

  return (
    <div className="hrm-report-page hrm-report-page--spaced-lg">
      <ReportPageHeader
        title="ETL Control"
        description="Trigger and monitor HR data extraction from all configured ETL source databases."
      />

      {sourcesError ? (
        <QueryErrorPanel
          title="Could not load ETL sources"
          message={getErrorMessage(sourcesQueryError)}
          onRetry={() => void refetchSources()}
        />
      ) : (
        <div
          className={clsx(
            "flex flex-wrap items-center gap-3 px-4 py-3 rounded-xl border text-sm",
            sourcesLoading
              ? "bg-slate-50 border-slate-200 text-slate-600"
              : hasSources
                ? "bg-teal-50 border-teal-200 text-teal-800"
                : "bg-amber-50 border-amber-200 text-amber-800"
          )}
        >
          {sourcesLoading ? (
            <>
              <Zap className="w-4 h-4 text-slate-400 shrink-0 hrm-skeleton" aria-hidden />
              <span>Loading ETL sources…</span>
            </>
          ) : hasSources ? (
            <>
              <Zap className="w-4 h-4 text-teal-600 shrink-0" aria-hidden />
              <span className="min-w-0 flex-1">
                <strong>{etlSources.length}</strong> source database
                {etlSources.length === 1 ? "" : "s"}:{" "}
                <span className="break-words" title={sourceNames}>
                  {sourceNames}
                </span>
              </span>
              <Link
                to="/settings/etl-sources"
                className="ml-auto shrink-0 text-xs text-teal-600 hover:text-teal-800 underline"
              >
                Manage sources
              </Link>
            </>
          ) : (
            <>
              <AlertCircle className="w-4 h-4 text-amber-500 shrink-0" aria-hidden />
              <span className="min-w-0">
                No source database configured.{" "}
                <Link to="/settings/etl-sources" className="underline font-medium">
                  Configure ETL sources
                </Link>{" "}
                before running ETL.
              </span>
            </>
          )}
        </div>
      )}

      {statusError && (
        <QueryErrorPanel
          title="Could not load ETL status"
          message={getErrorMessage(statusQueryError)}
          onRetry={() => void refetchStatus()}
          retrying={statusFetching}
        />
      )}

      {trackedRun?.status === "failed" && lastQueuedRunId != null && (
        <div className="flex gap-3 px-4 py-3 rounded-xl border border-red-200 bg-red-50 text-sm text-red-900">
          <AlertCircle className="w-5 h-5 shrink-0 text-red-600 mt-0.5" aria-hidden />
          <div className="min-w-0">
            <p className="font-medium">Run #{String(trackedRun.run_id)} failed</p>
            <p className="mt-1 whitespace-pre-wrap break-words text-red-800">
              {runFailureMessage(trackedRun)}
            </p>
          </div>
        </div>
      )}

      <ReportSection title="Trigger ETL run">
        <div className="rounded-xl border border-[var(--color-border)] bg-white p-5 space-y-4">
        <div className="flex gap-3 items-center flex-wrap">
          <label htmlFor="etl-run-type" className="sr-only">
            ETL run type
          </label>
          <select
            id="etl-run-type"
            value={runType}
            onChange={(e) => setRunType(e.target.value as "incremental" | "full_load")}
            disabled={hasRunning || trigger.isPending}
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 disabled:opacity-50"
          >
            <option value="incremental">Incremental (watermark-based)</option>
            <option value="full_load">Full load (truncate + reload)</option>
          </select>
          <button
            type="button"
            onClick={handleRunEtl}
            disabled={trigger.isPending || !hasSources || hasRunning || sourcesLoading}
            aria-busy={trigger.isPending || hasRunning}
            className="bg-teal-600 hover:bg-teal-700 disabled:opacity-40 text-white rounded-lg px-4 py-2 flex items-center gap-2 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600"
          >
            <Play size={14} aria-hidden />
            {trigger.isPending
              ? "Queuing…"
              : hasRunning
                ? "Run in progress…"
                : "Run ETL"}
          </button>
          {trigger.isSuccess && !trigger.isPending && !hasRunning && (
            <span className="text-green-600 text-sm" role="status">
              Queued{lastQueuedRunId != null ? ` (run #${lastQueuedRunId})` : ""}
            </span>
          )}
          <button
            type="button"
            onClick={handleClearStuck}
            disabled={clearStuck.isPending || hasRunning}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40"
          >
            {clearStuck.isPending ? "Clearing…" : "Clear stuck runs"}
          </button>
        </div>
        {runType === "full_load" && (
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            Full load replaces all staged data. Confirm before starting if reports depend on current staging tables.
          </p>
        )}
        </div>
      </ReportSection>

      <ReportSection title="Recent runs">
        <div className="rounded-xl border border-[var(--color-border)] bg-white p-5 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-slate-600 min-w-0">
            {hasRunning ? (
              <span className="text-amber-700 etl-run-pulse">Run in progress. Status refreshes every few seconds.</span>
            ) : (
              <span>Latest extraction jobs for this tenant.</span>
            )}
          </p>
          <button
            type="button"
            onClick={refreshAll}
            disabled={statusFetching}
            className="shrink-0 rounded-lg p-2 text-slate-400 hover:bg-slate-50 hover:text-slate-600 transition-colors disabled:opacity-50"
            aria-label="Refresh runs and watermarks"
          >
            <RefreshCw
              size={14}
              className={clsx(statusFetching || hasRunning ? "etl-refresh-spin" : undefined)}
              aria-hidden
            />
          </button>
        </div>
        {statusLoading && !statusError ? (
          <ReportTableSkeleton rows={5} />
        ) : !statusError && runs.length === 0 ? (
          <p className="text-slate-500 text-sm">
            No ETL runs yet. Configure sources, then click Run ETL to start.
          </p>
        ) : !statusError ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-slate-600" aria-label="Recent ETL runs">
              <thead>
                <tr className="border-b border-slate-100 text-slate-500">
                  <th className="text-left py-2 pr-4 font-medium">Run ID</th>
                  <th className="text-left py-2 pr-4 font-medium">Type</th>
                  <th className="text-left py-2 pr-4 font-medium">Status</th>
                  <th className="text-left py-2 pr-4 font-medium">Rows</th>
                  <th className="text-left py-2 pr-4 font-medium">Started</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run: Record<string, unknown>) => (
                  <tr key={String(run.run_id)} className="border-b border-slate-50">
                    <td className="py-2 pr-4 font-mono">{String(run.run_id ?? "—")}</td>
                    <td className="py-2 pr-4 break-words">{String(run.run_type ?? "—")}</td>
                    <td className="py-2 pr-4 min-w-0">
                      <span
                        className={clsx(
                          "inline-block px-2 py-0.5 rounded-full text-xs font-medium",
                          run.status === "completed"
                            ? "bg-green-100 text-green-700"
                            : run.status === "failed"
                              ? "bg-red-100 text-red-700"
                              : "bg-yellow-100 text-yellow-700"
                        )}
                      >
                        {String(run.status ?? "unknown")}
                      </span>
                      {run.status === "failed" ? (
                        <p
                          className="text-red-600 mt-1 max-w-xl whitespace-pre-wrap break-words line-clamp-3"
                          title={runFailureMessage(run)}
                        >
                          {runFailureMessage(run)}
                        </p>
                      ) : null}
                    </td>
                    <td className="py-2 pr-4 tabular-nums">{formatRowCount(run.rows_extracted)}</td>
                    <td className="py-2 pr-4 text-slate-400 whitespace-nowrap">
                      {formatTimestamp(run.started_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        </div>
      </ReportSection>

      <ReportSection title="ETL watermarks">
        <div className="rounded-xl border border-[var(--color-border)] bg-white p-5 space-y-3">
          <p className="text-sm text-slate-600">
            Per staging table. Updated after each extract when rows load. Incremental runs use these values to pull only newer records.
          </p>
        {watermarksError ? (
          <QueryErrorPanel
            title="Could not load watermarks"
            message={getErrorMessage(watermarksQueryError)}
            onRetry={() => void refetchWatermarks()}
          />
        ) : watermarksLoading ? (
          <ReportTableSkeleton rows={4} />
        ) : (watermarks?.watermarks || []).length === 0 ? (
          <p className="text-sm text-slate-500 py-4 text-center border border-dashed border-slate-200 rounded-lg">
            No watermarks yet. Run a successful <strong>full load</strong> or{" "}
            <strong>incremental</strong> extract (with rows extracted) to populate this table.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-slate-600" aria-label="ETL watermarks">
              <thead>
                <tr className="border-b border-slate-100 text-slate-500">
                  <th className="text-left py-2 pr-4 font-medium">Table</th>
                  <th className="text-left py-2 pr-4 font-medium">Last value</th>
                  <th className="text-left py-2 pr-4 font-medium">Rows at mark</th>
                  <th className="text-left py-2 font-medium">Updated</th>
                </tr>
              </thead>
              <tbody>
                {(watermarks?.watermarks || []).map((w: Record<string, unknown>) => (
                  <tr key={String(w.table_name)} className="border-b border-slate-50">
                    <td className="py-2 pr-4 font-mono break-all">{String(w.table_name ?? "—")}</td>
                    <td className="py-2 pr-4 text-slate-600 whitespace-nowrap">
                      {formatTimestamp(w.last_value)}
                    </td>
                    <td className="py-2 pr-4 tabular-nums">{formatRowCount(w.rows_at_mark)}</td>
                    <td className="py-2 text-slate-400 whitespace-nowrap">
                      {formatTimestamp(w.updated_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        </div>
      </ReportSection>
    </div>
  );
}
