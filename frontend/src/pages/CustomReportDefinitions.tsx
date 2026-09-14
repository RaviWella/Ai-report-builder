import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileSpreadsheet,
  Plus,
  RefreshCw,
  Trash2,
  Pencil,
  X,
  Check,
  Loader2,
} from "lucide-react";
import clsx from "clsx";
import { useToast } from "../components/ui/Toast";
import ReportPageHeader from "../components/ReportPageHeader";
import ReportQueryError from "../components/ReportQueryError";
import ReportEmptyState from "../components/ReportEmptyState";
import { ReportCardListSkeleton } from "../components/ReportLoadingSkeleton";
import {
  customReportsService,
  type CustomReportDefinition,
  type CustomReportDefinitionCreate,
} from "../services/customReportsService";
import { getErrorMessage } from "../services/api";
import {
  CUSTOM_REPORT_DISPLAY_MODULES,
  moduleLabel,
  REPORT_SQL_HELP,
} from "../lib/customReportModules";
import { CUSTOM_REPORTS_QUERY_KEY } from "../lib/customReportsQuery";

const MODULES = [...CUSTOM_REPORT_DISPLAY_MODULES] as string[];

const SQL_PLACEHOLDER = `SELECT emp_no, emp_name
FROM {mart_schema}.dim_employee
WHERE tenant_id = '{tenant_id}'`;

type FormState = {
  module: string;
  report_name: string;
  view_name: string;
  view_query: string;
  report_type: "table" | "payslip";
  sort_order: string;
};

const EMPTY_FORM: FormState = {
  module: "payroll",
  report_name: "",
  view_name: "vw_",
  view_query: "",
  report_type: "table",
  sort_order: "100",
};

function inputClass() {
  return "w-full mt-1.5 px-3 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500";
}

function labelClass() {
  return "block text-sm font-medium text-slate-700";
}

function DefinitionCard({
  row,
  onDelete,
  onSave,
  isDeleting,
  isSaving,
}: {
  row: CustomReportDefinition;
  onDelete: () => void;
  onSave: (
    patch: {
      report_name: string;
      module: string;
      sort_order: number;
      view_query: string;
    },
    onSuccess: () => void,
  ) => void;
  isDeleting: boolean;
  isSaving: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [reportName, setReportName] = useState(row.report_name);
  const [module, setModule] = useState(row.module);
  const [sortOrder, setSortOrder] = useState(String(row.sort_order));
  const [viewQuery, setViewQuery] = useState(row.view_query ?? "");

  function resetDraft() {
    setReportName(row.report_name);
    setModule(row.module);
    setSortOrder(String(row.sort_order));
    setViewQuery(row.view_query ?? "");
  }

  useEffect(() => {
    if (!editing) {
      resetDraft();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sync draft when server row changes
  }, [row.id, row.report_name, row.module, row.sort_order, row.view_query, editing]);

  function handleSave() {
    const name = reportName.trim();
    const sql = viewQuery.trim();
    if (!name || !sql) {
      return;
    }
    const order = Number.parseInt(sortOrder, 10);
    onSave(
      {
        report_name: name,
        module: module.trim(),
        sort_order: Number.isFinite(order) ? order : row.sort_order,
        view_query: sql,
      },
      () => setEditing(false),
    );
  }

  function handleCancelEdit() {
    resetDraft();
    setEditing(false);
  }

  function handleDeleteClick() {
    const ok = window.confirm(
      `Delete "${row.report_name}"? This removes the report from Report Studio and deletes its analytics view. This cannot be undone.`,
    );
    if (ok) {
      onDelete();
    }
  }

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <FileSpreadsheet className="h-4 w-4 shrink-0 text-slate-500" aria-hidden />
            {editing ? (
              <input
                className={clsx(inputClass(), "mt-0 font-medium")}
                value={reportName}
                onChange={(e) => setReportName(e.target.value)}
                aria-label="Report display name"
              />
            ) : (
              <h3 className="font-semibold text-slate-900 truncate">{row.report_name}</h3>
            )}
            <span className="text-xs font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full">
              {moduleLabel(row.module)}
            </span>
            {row.report_type === "payslip" && (
              <span className="text-xs font-medium text-violet-800 bg-violet-100 px-2 py-0.5 rounded-full">
                Payslip layout
              </span>
            )}
          </div>
          <p className="mt-2 text-sm text-slate-600 break-words">
            Report ID: <span className="font-mono text-slate-700 break-all">{row.view_name}</span>
          </p>
          {editing ? (
            <div className="mt-3 space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className={labelClass()}>
                  Area
                  <select
                    className={inputClass()}
                    value={module}
                    onChange={(e) => setModule(e.target.value)}
                  >
                    {MODULES.map((m) => (
                      <option key={m} value={m}>
                        {moduleLabel(m)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className={labelClass()}>
                  List order
                  <input
                    className={inputClass()}
                    value={sortOrder}
                    onChange={(e) => setSortOrder(e.target.value)}
                    inputMode="numeric"
                    aria-describedby={`sort-help-${row.id}`}
                  />
                  <span id={`sort-help-${row.id}`} className="mt-1 block text-xs font-normal text-slate-500">
                    Lower numbers appear first in Report Studio.
                  </span>
                </label>
              </div>
              <label className={labelClass()}>
                Report SQL
                <textarea
                  className={clsx(inputClass(), "font-mono text-xs min-h-[12rem]")}
                  value={viewQuery}
                  onChange={(e) => setViewQuery(e.target.value)}
                  spellCheck={false}
                  aria-describedby={`sql-help-${row.id}`}
                  required
                />
                <span id={`sql-help-${row.id}`} className="mt-1 block text-xs font-normal text-slate-500">
                  {REPORT_SQL_HELP} Tokens: {"{mart_schema}"}, {"{raw_schema}"}, {"{tenant_id}"}.
                </span>
              </label>
            </div>
          ) : (
            <p className="mt-1 text-xs text-slate-500">List order: {row.sort_order}</p>
          )}
        </div>

        <div className="inline-flex shrink-0 flex-wrap gap-2">
          {editing ? (
            <>
              <button
                type="button"
                onClick={handleSave}
                disabled={isSaving || !reportName.trim() || !viewQuery.trim()}
                className="hrm-report-action hrm-report-action--primary"
                aria-busy={isSaving}
              >
                {isSaving ? (
                  <>
                    <Loader2 size={14} className="hrm-table-toolbar__spin" aria-hidden />
                    Saving…
                  </>
                ) : (
                  <>
                    <Check size={14} aria-hidden />
                    Save changes
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={handleCancelEdit}
                disabled={isSaving}
                className="hrm-report-action hrm-report-action--secondary"
              >
                <X size={14} aria-hidden />
                Cancel edit
              </button>
            </>
          ) : (
            <>
              <Link
                to={`/hr/custom-reports/${encodeURIComponent(row.view_name)}`}
                className="hrm-report-action hrm-report-action--secondary"
              >
                Open preview
              </Link>
              <button
                type="button"
                onClick={() => setEditing(true)}
                disabled={isDeleting || isSaving}
                className="hrm-report-action hrm-report-action--secondary"
              >
                <Pencil size={14} aria-hidden />
                Edit
              </button>
              <button
                type="button"
                onClick={handleDeleteClick}
                disabled={isDeleting}
                className="hrm-report-action hrm-report-action--muted"
                aria-busy={isDeleting}
              >
                {isDeleting ? (
                  <>
                    <Loader2 size={14} className="hrm-table-toolbar__spin" aria-hidden />
                    Deleting…
                  </>
                ) : (
                  <>
                    <Trash2 size={14} aria-hidden />
                    Delete report
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </div>
    </article>
  );
}

export default function CustomReportDefinitions() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [moduleFilter, setModuleFilter] = useState<string>("");
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  const { data: rows = [], isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["custom-report-definitions", moduleFilter || "all"],
    queryFn: () =>
      customReportsService.listDefinitions(
        moduleFilter ? { module: moduleFilter } : undefined,
      ),
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["custom-report-definitions"] });
    void queryClient.invalidateQueries({ queryKey: CUSTOM_REPORTS_QUERY_KEY });
  };

  const createMutation = useMutation({
    mutationFn: (body: CustomReportDefinitionCreate) =>
      customReportsService.createDefinition(body),
    onSuccess: () => {
      toast.success("Report saved. It will appear in Report Studio.");
      setShowForm(false);
      setForm(EMPTY_FORM);
      invalidate();
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      patch,
    }: {
      id: number;
      patch: {
        report_name: string;
        module: string;
        sort_order: number;
        view_query: string;
      };
    }) => customReportsService.updateDefinition(id, patch),
    onSuccess: () => {
      toast.success("Report updated and published to analytics.");
      invalidate();
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => customReportsService.deleteDefinition(id),
    onSuccess: () => {
      toast.success("Report removed from Report Studio.");
      invalidate();
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  });

  const syncMutation = useMutation({
    mutationFn: () => customReportsService.syncDefinitions(),
    onSuccess: (result) => {
      if (result.ok) {
        toast.success(
          result.created.length
            ? `Published ${result.created.length} report view(s) to analytics.`
            : "All app-managed reports are already published.",
        );
      } else {
        toast.error(result.errors.join("; ") || "Some reports could not be published. Check SQL and retry.");
      }
      invalidate();
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  });

  function handleCreate(e: FormEvent) {
    e.preventDefault();
    const reportName = form.report_name.trim();
    const viewName = form.view_name.trim();
    const viewQuery = form.view_query.trim();
    if (!reportName || !viewName || !viewQuery) {
      toast.error("Display name, report ID, and report SQL are required.");
      return;
    }
    const order = Number.parseInt(form.sort_order, 10);
    createMutation.mutate({
      module: form.module.trim(),
      report_name: reportName,
      view_name: viewName,
      view_query: viewQuery,
      report_type: form.report_type,
      sort_order: Number.isFinite(order) ? order : 100,
    });
  }

  return (
    <div className="hrm-report-page hrm-report-page--spaced max-w-4xl">
      <ReportPageHeader
        title="Report Studio Config"
        description="Register tenant reports with SQL, set list order, and publish app-managed definitions. Published reports appear in Report Studio."
      >
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="hrm-report-action hrm-report-action--secondary"
            title="Publish app-managed report SQL as analytics views"
            aria-busy={syncMutation.isPending}
          >
            <RefreshCw
              size={14}
              className={clsx(syncMutation.isPending && "hrm-table-toolbar__spin")}
              aria-hidden
            />
            {syncMutation.isPending ? "Publishing…" : "Publish reports"}
          </button>
          <button
            type="button"
            onClick={() => setShowForm((v) => !v)}
            className="hrm-report-action hrm-report-action--primary"
            aria-expanded={showForm}
          >
            <Plus size={14} aria-hidden />
            {showForm ? "Close form" : "Add report"}
          </button>
        </div>
      </ReportPageHeader>

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-slate-700">
          Filter by area
          <select
            className={clsx(inputClass(), "ml-2 mt-0 inline-block w-auto min-w-[10rem]")}
            value={moduleFilter}
            onChange={(e) => setModuleFilter(e.target.value)}
          >
            <option value="">All areas</option>
            {MODULES.map((m) => (
              <option key={m} value={m}>
                {moduleLabel(m)}
              </option>
            ))}
          </select>
        </label>
        <Link to="/hr/custom-reports" className="text-sm text-teal-700 hover:underline">
          Open Report Studio
        </Link>
      </div>

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="rounded-xl border border-teal-200 bg-teal-50/30 p-4 sm:p-5 space-y-4"
        >
          <h2 className="font-medium text-slate-900">Add report</h2>
          <p className="text-sm text-slate-600">
            After you save, the report appears in Report Studio for this tenant.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className={labelClass()}>
              Display name
              <input
                className={inputClass()}
                value={form.report_name}
                onChange={(e) => setForm((f) => ({ ...f, report_name: e.target.value }))}
                placeholder="Payroll costing summary"
                required
              />
            </label>
            <label className={labelClass()}>
              Report ID
              <input
                className={inputClass()}
                value={form.view_name}
                onChange={(e) => setForm((f) => ({ ...f, view_name: e.target.value }))}
                required
                pattern="[a-z][a-z0-9_]*"
                title="Lowercase letters, numbers, and underscores. Must start with a letter."
                placeholder="vw_my_payroll_report"
                aria-describedby="report-id-help"
              />
              <span id="report-id-help" className="mt-1 block text-xs font-normal text-slate-500">
                Internal name used in analytics. Cannot be changed after save.
              </span>
            </label>
            <label className={labelClass()}>
              Area
              <select
                className={inputClass()}
                value={form.module}
                onChange={(e) => setForm((f) => ({ ...f, module: e.target.value }))}
              >
                {MODULES.map((m) => (
                  <option key={m} value={m}>
                    {moduleLabel(m)}
                  </option>
                ))}
              </select>
            </label>
            <label className={labelClass()}>
              Layout
              <select
                className={inputClass()}
                value={form.report_type}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    report_type: e.target.value as "table" | "payslip",
                  }))
                }
              >
                <option value="table">Table (rows and columns)</option>
                <option value="payslip">Payslip (employee and period filters)</option>
              </select>
            </label>
            <label className={labelClass()}>
              List order
              <input
                className={inputClass()}
                value={form.sort_order}
                onChange={(e) => setForm((f) => ({ ...f, sort_order: e.target.value }))}
                inputMode="numeric"
                aria-describedby="create-sort-help"
              />
              <span id="create-sort-help" className="mt-1 block text-xs font-normal text-slate-500">
                Lower numbers appear first.
              </span>
            </label>
          </div>
          <label className={labelClass()}>
            Report SQL
            <textarea
              id="report-sql-input"
              className={clsx(inputClass(), "font-mono text-xs min-h-[8rem]")}
              value={form.view_query}
              onChange={(e) => setForm((f) => ({ ...f, view_query: e.target.value }))}
              required
              spellCheck={false}
              placeholder={SQL_PLACEHOLDER}
              aria-describedby="report-sql-help report-sql-tokens"
            />
          </label>
          <p id="report-sql-help" className="text-sm text-slate-600">
            {REPORT_SQL_HELP}
          </p>
          <details className="text-sm text-slate-600">
            <summary className="cursor-pointer font-medium text-slate-700">SQL tokens (advanced)</summary>
            <p id="report-sql-tokens" className="mt-2 font-mono text-xs text-slate-700">
              {"{mart_schema}"}, {"{semantic_schema}"}, {"{tenant_id}"}
            </p>
          </details>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="hrm-report-action hrm-report-action--primary"
              aria-busy={createMutation.isPending}
            >
              {createMutation.isPending ? (
                <>
                  <Loader2 size={14} className="hrm-table-toolbar__spin" aria-hidden />
                  Saving…
                </>
              ) : (
                "Save report"
              )}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowForm(false);
                setForm(EMPTY_FORM);
              }}
              disabled={createMutation.isPending}
              className="hrm-report-action hrm-report-action--secondary"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {isError && (
        <ReportQueryError
          title="Could not load report definitions"
          message={getErrorMessage(error)}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      )}

      {isLoading ? (
        <ReportCardListSkeleton count={3} />
      ) : !isError && rows.length === 0 ? (
        moduleFilter ? (
          <ReportEmptyState
            title={`No reports in ${moduleLabel(moduleFilter)}`}
            hint="Try another area, or clear the filter above to see all reports."
          />
        ) : (
          <div className="hrm-report-empty" role="status">
            <p className="hrm-report-empty__title">No reports configured yet</p>
            <p className="hrm-report-empty__hint">
              Run ETL for standard payroll reports, or add a tenant-specific report.
            </p>
            <button
              type="button"
              onClick={() => setShowForm(true)}
              className="hrm-report-empty__action border-0 bg-transparent cursor-pointer p-0"
            >
              Add report
            </button>
          </div>
        )
      ) : !isError ? (
        <ul className="space-y-3">
          {rows.map((row) => (
            <li key={row.id}>
              <DefinitionCard
                row={row}
                onDelete={() => {
                  setDeletingId(row.id);
                  deleteMutation.mutate(row.id, {
                    onSettled: () => setDeletingId(null),
                  });
                }}
                onSave={(patch, onSuccess) => {
                  setUpdatingId(row.id);
                  updateMutation.mutate(
                    { id: row.id, patch },
                    {
                      onSuccess: () => onSuccess(),
                      onSettled: () => setUpdatingId(null),
                    },
                  );
                }}
                isDeleting={deletingId === row.id}
                isSaving={updatingId === row.id}
              />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
