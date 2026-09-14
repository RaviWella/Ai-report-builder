/**
 * MintHRM API client — mirrors mint-analytics api service pattern.
 * All requests carry X-API-Key and X-Tenant-Id headers.
 */
import axios from "axios";
import { getActiveTenantId, getActiveUserId, getStoredAuthToken } from "../lib/activeTenant";
import { buildCustomReportExportFilename } from "../lib/exportHrTableCsv";
import { API_BASE_URL, API_KEY } from "../env";

const api = axios.create({
  baseURL: API_BASE_URL,
  // Remote warehouse (minchy) can take 15–30s on cold connect for HR mart reads.
  timeout: 120_000,
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
  },
});

api.interceptors.request.use((config) => {
  config.headers["X-Tenant-Id"] = getActiveTenantId();
  const userId = getActiveUserId();
  if (userId) {
    config.headers["X-User-Id"] = userId;
  } else if (config.headers["X-User-Id"]) {
    delete config.headers["X-User-Id"];
  }
  const token = getStoredAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  } else if (config.headers.Authorization) {
    delete config.headers.Authorization;
  }
  return config;
});

if (process.env.NODE_ENV === "development" && typeof globalThis !== "undefined") {
  globalThis.console.info("[hrm-api] Base URL:", API_BASE_URL);
}

api.interceptors.request.use((config) => {
  if (
    process.env.NODE_ENV === "development" &&
    typeof config.url === "string" &&
    config.url.includes("datamart") &&
    (config.url.includes("/chat") ||
      config.url.includes("/execute") ||
      config.url.includes("/templates") ||
      config.url.includes("/sessions"))
  ) {
    globalThis.console.debug(
      "[hrm-api] request",
      (config.method ?? "get").toUpperCase(),
      `${config.baseURL ?? ""}${config.url}`,
    );
  }
  return config;
});

// ── HR Metrics ────────────────────────────────────────────────────

export interface MetricValue {
  name: string;
  display_name: string;
  unit: string;
  value: number | null;
  period_label?: string;
  department_id?: number;
  branch_id?: number;
  derivation: string;
  components: Record<string, number>;
}

export interface HeadcountSummary {
  tenant_id: string;
  period_label?: string;
  total_headcount?: number;
  new_hires?: number;
  separations?: number;
  turnover_rate?: number;
}

export interface PayrollSummary {
  tenant_id: string;
  period_label?: string;
  payroll_employee_count?: number;
  total_payroll_cost?: number;
  average_salary?: number;
  total_gross?: number;
  total_additions?: number;
  total_tax?: number;
  total_statutory?: number;
  total_deductions?: number;
  total_overtime_cost?: number;
}

export interface PayrollRegisterRow {
  employee_sk?: string;
  employee_id?: number;
  emp_no?: string;
  emp_fullname?: string;
  designation?: string;
  legal_entity?: string;
  branch?: string;
  payroll_group_name?: string;
  basic_salary?: number;
  gross_salary?: number;
  total_additions?: number;
  total_deductions?: number;
  net_salary?: number;
  tax_amount?: number;
  epf_employee_amount?: number;
  epf_employer_amount?: number;
  etf_amount?: number;
  pay_cut_amount?: number;
  increment_amount?: number;
  run_status?: string;
}

export interface PayrollComplianceRow {
  compliance_domain: string;
  total_amount: number;
  employee_count: number;
}

export interface PayrollComponentRow {
  component_name: string;
  add_ded_type: string;
  total_amount: number;
  line_count: number;
}

export interface AttendanceSummary {
  tenant_id: string;
  period_label?: string;
  attendance_rate?: number;
  late_arrivals?: number;
  total_overtime_hours?: number;
}

export interface LeaveSummary {
  tenant_id: string;
  period_label?: string;
  leave_days_taken?: number;
  leave_days_entitled?: number;
  leave_utilization_rate?: number;
  sick_leave_days?: number;
}

export interface PerformanceSummary {
  tenant_id: string;
  period_label?: string;
  average_performance_score?: number;
  high_performers?: number;
}

export interface CustomReportView {
  view_name: string;
  label: string;
  schema: string;
  module?: string;
  source?: string;
  is_payslip?: boolean;
  /** Payroll table reports with a global year/month filter in preview (see payroll_report_period_config.py). */
  supports_period_filter?: boolean;
}

export interface CustomReportsListResponse {
  tenant_id: string;
  schema: string;
  module?: string | null;
  views: CustomReportView[];
}

export interface LaunchBranding {
  company_name?: string | null;
  logo_url?: string | null;
}

export interface VerifyLaunchPayloadResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  tenant_id: string;
  user_id: string;
  branding: LaunchBranding;
}

export type ColumnFilterState = Record<string, string[]>;

export interface ColumnFilterOption {
  column: string;
  values: string[];
}

export interface ColumnFiltersResponse {
  view_name: string;
  columns: ColumnFilterOption[];
}

export interface CustomReportPreviewResponse {
  view_name: string;
  label: string;
  schema: string;
  columns: string[];
  rows: Record<string, unknown>[];
  total: number;
  limit: number;
  offset: number;
  applied_filters?: ColumnFilterState;
}

export type CustomReportExportFilters = {
  proc_year?: number;
  proc_month?: number;
  emp_no?: string;
  column_filters?: ColumnFilterState;
};

export interface PayslipFilterEntry {
  proc_year: number;
  proc_month: number;
  emp_no: string;
  emp_name?: string | null;
  emp_full_name?: string | null;
  designation_name?: string | null;
}

export interface PayslipFiltersResponse {
  view_name: string;
  entries: PayslipFilterEntry[];
}

export interface PayslipPreviewResponse {
  mode: "payslip";
  view_name: string;
  label: string;
  schema: string;
  employee: {
    emp_no: string;
    emp_name?: string | null;
    emp_full_name?: string | null;
    designation_name?: string | null;
  };
  period: { proc_year: number; proc_month: number };
  columns: string[];
  rows: Record<string, unknown>[];
  total: number;
}

export const PAYSLIP_REPORT_VIEW = "vw_employee_payslip_vertical";

export interface EmploymentSummary {
  tenant_id: string;
  period_label?: string;
  active_headcount: number;
  employees_with_salary: number;
  average_basic_salary?: number;
  total_basic_salary_cost?: number;
  new_hires: number;
  separations: number;
  turnover_rate?: number;
  latest_month_active_headcount?: number;
  mom_active_change?: number;
  monthly_salary_cost_active?: number;
  salary_band_count: number;
}

export interface HeadcountMonthlyRow {
  period_label: string;
  snapshot_month: string;
  active_headcount: number;
  resigned_headcount_eom?: number;
  terminated_headcount_eom?: number;
  net_active_headcount_change_mom?: number;
  monthly_salary_cost_active?: number;
}

export interface SalaryBandRow {
  legal_entity_name: string;
  designation_name: string;
  grade_name: string;
  headcount: number;
  min_salary?: number;
  max_salary?: number;
  avg_salary?: number;
  median_salary?: number;
  payroll_cost?: number;
}

export interface EmployeeRow {
  source_emp_id: number;
  emp_no?: string;
  emp_fullname?: string;
  designation?: string;
  grade?: string;
  legal_entity?: string;
  location_name?: string;
  employment_type?: string;
  join_date?: string;
  tenure_years?: number;
  tenure_bucket?: string;
  basic_salary?: number;
  is_on_probation?: boolean;
  superior_fullname?: string;
}

export interface LifecycleCategoryRow {
  period_label: string;
  event_category: string;
  event_count: number;
}

export interface AttendanceMonthlySummary {
  period_label?: string;
  scheduled_days?: number;
  present_days?: number;
  late_arrivals?: number;
  total_overtime_hours?: number;
  attendance_rate?: number;
}

// ── API functions ─────────────────────────────────────────────────

export const hrApi = {
  getHeadcount: (params?: { period_label?: string; department_id?: number; branch_id?: number }) =>
    api.get<HeadcountSummary>("/hr/headcount", { params }).then((r) => r.data),

  getPayroll: (params?: { period_label?: string; department_id?: number; branch_id?: number }) =>
    api.get<PayrollSummary>("/hr/payroll", { params }).then((r) => r.data),

  getPayrollSummary: (period_label?: string) =>
    api
      .get<PayrollSummary>("/hr/payroll/summary", { params: { period_label } })
      .then((r) => r.data),

  getPayrollRegister: (params?: {
    limit?: number;
    offset?: number;
    period_label?: string;
  }) =>
    api
      .get<{
        tenant_id: string;
        period_label?: string;
        total: number;
        limit: number;
        offset: number;
        items: PayrollRegisterRow[];
      }>("/hr/payroll/register", { params })
      .then((r) => r.data),

  getPayrollCompliance: (period_label?: string) =>
    api
      .get<{
        tenant_id: string;
        period_label?: string;
        items: PayrollComplianceRow[];
      }>("/hr/payroll/compliance", { params: { period_label } })
      .then((r) => r.data),

  getPayrollComponents: (params?: { period_label?: string; limit?: number }) =>
    api
      .get<{
        tenant_id: string;
        period_label?: string;
        items: PayrollComponentRow[];
      }>("/hr/payroll/components", { params })
      .then((r) => r.data),

  getAttendance: (params?: { period_label?: string; department_id?: number; branch_id?: number }) =>
    api.get<AttendanceSummary>("/hr/attendance", { params }).then((r) => r.data),

  getLeave: (params?: { period_label?: string; department_id?: number; branch_id?: number }) =>
    api.get<LeaveSummary>("/hr/leave", { params }).then((r) => r.data),

  getPerformance: (params?: { period_label?: string; department_id?: number; branch_id?: number }) =>
    api.get<PerformanceSummary>("/hr/performance", { params }).then((r) => r.data),

  listMetrics: () =>
    api.get<MetricValue[]>("/hr/metrics").then((r) => r.data),

  getAvailablePeriods: () =>
    api
      .get<{ tenant_id: string; default_period?: string; periods: string[] }>(
        "/hr/employment/periods"
      )
      .then((r) => r.data),

  getEmploymentSummary: (period_label?: string) =>
    api
      .get<EmploymentSummary>("/hr/employment/summary", {
        params: { period_label },
      })
      .then((r) => r.data),

  getHeadcountMonthly: (params?: { limit?: number; period_label?: string }) =>
    api
      .get<{ tenant_id: string; items: HeadcountMonthlyRow[] }>(
        "/hr/employment/headcount-monthly",
        { params }
      )
      .then((r) => r.data),

  getSalaryBands: (params?: { limit?: number; period_label?: string }) =>
    api
      .get<{ tenant_id: string; items: SalaryBandRow[] }>(
        "/hr/employment/salary-bands",
        { params }
      )
      .then((r) => r.data),

  getEmployees: (params?: {
    limit?: number;
    offset?: number;
    period_label?: string;
  }) =>
    api
      .get<{
        tenant_id: string;
        total: number;
        limit: number;
        offset: number;
        items: EmployeeRow[];
      }>("/hr/employment/employees", { params })
      .then((r) => r.data),

  getLifecycleSummary: (period_label?: string) =>
    api
      .get<{ tenant_id: string; period_label?: string; items: LifecycleCategoryRow[] }>(
        "/hr/employment/lifecycle",
        { params: { period_label } }
      )
      .then((r) => r.data),

  getAttendanceMonthly: (period_label?: string) =>
    api
      .get<AttendanceMonthlySummary>("/hr/employment/attendance-monthly", {
        params: { period_label },
      })
      .then((r) => r.data),

  verifyLaunchPayload: (body: {
    payload: string;
    subdomain?: string;
    employee_id?: string;
  }) =>
    api
      .post<VerifyLaunchPayloadResponse>("/auth/verify-payload", body)
      .then((r) => r.data),

  listCustomReports: (params?: { module?: string }) =>
    api
      .get<CustomReportsListResponse>("/hr/custom-reports", { params })
      .then((r) => r.data),

  previewCustomReport: (
    viewName: string,
    params?: {
      limit?: number;
      offset?: number;
      proc_year?: number;
      proc_month?: number;
      column_filters?: string;
    },
  ) =>
    api
      .get<CustomReportPreviewResponse>(
        `/hr/custom-reports/${encodeURIComponent(viewName)}/preview`,
        { params },
      )
      .then((r) => r.data),

  listColumnFilters: (viewName: string, column?: string) =>
    api
      .get<ColumnFiltersResponse>(
        `/hr/custom-reports/${encodeURIComponent(viewName)}/column-filters`,
        { params: column ? { column } : undefined },
      )
      .then((r) => r.data),

  listPayslipFilters: (viewName: string) =>
    api
      .get<PayslipFiltersResponse>(
        `/hr/custom-reports/${encodeURIComponent(viewName)}/payslip-filters`,
      )
      .then((r) => r.data),

  previewPayslip: (
    viewName: string,
    params: { emp_no: string; proc_year: number; proc_month: number },
  ) =>
    api
      .get<PayslipPreviewResponse>(
        `/hr/custom-reports/${encodeURIComponent(viewName)}/preview`,
        { params },
      )
      .then((r) => r.data),

  downloadCustomReport: async (
    viewName: string,
    exportFormat: "xlsx" | "pdf" = "xlsx",
    filters?: CustomReportExportFilters,
    downloadLabel?: string,
  ) => {
    try {
      const columnFiltersJson =
        filters?.column_filters &&
        Object.keys(filters.column_filters).some((k) => filters.column_filters![k]?.length)
          ? JSON.stringify(
              Object.fromEntries(
                Object.entries(filters.column_filters).filter(([, v]) => v.length > 0),
              ),
            )
          : undefined;

      const response = await api.get<Blob>(
        `/hr/custom-reports/${encodeURIComponent(viewName)}/export`,
        {
          params: {
            export_format: exportFormat,
            ...(filters?.proc_year != null ? { proc_year: filters.proc_year } : {}),
            ...(filters?.proc_month != null ? { proc_month: filters.proc_month } : {}),
            ...(filters?.emp_no ? { emp_no: filters.emp_no } : {}),
            ...(columnFiltersJson ? { column_filters: columnFiltersJson } : {}),
          },
          responseType: "blob",
        },
      );
      const defaultExt = exportFormat === "pdf" ? "pdf" : "xlsx";
      const filename = downloadLabel
        ? buildCustomReportExportFilename(downloadLabel, defaultExt, filters)
        : (() => {
            const disposition = response.headers["content-disposition"] as string | undefined;
            const match = disposition?.match(/filename="([^"]+)"/);
            return match?.[1] ?? `${viewName}.${defaultExt}`;
          })();
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
        const blob = error.response.data;
        if (blob.type.includes("json")) {
          const text = await blob.text();
          try {
            const body = JSON.parse(text) as { detail?: string };
            throw new Error(body.detail ?? text);
          } catch {
            throw new Error(text || "Export failed");
          }
        }
      }
      throw error;
    }
  },
};

export const etlApi = {
  triggerRun: (run_type: "full_load" | "incremental" = "incremental") =>
    api
      .post<{ status: string; run_id?: number; message?: string }>("/hr-etl/run", {
        run_type,
        triggered_by: "ui",
      })
      .then((r) => r.data),

  getStatus: () =>
    api.get("/hr-etl/status").then((r) => r.data),

  getWatermarks: () =>
    api.get("/hr-etl/watermarks").then((r) => r.data),

  clearStuckRuns: (max_age_hours = 2) =>
    api
      .post<{ cleared_run_ids: number[]; count: number }>(
        "/hr-etl/runs/clear-stuck",
        null,
        { params: { max_age_hours } }
      )
      .then((r) => r.data),
};

/** Normalize FastAPI/axios errors for UI display. */
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (detail != null) {
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        return detail
          .map((item) =>
            typeof item === "object" && item !== null && "msg" in item
              ? String((item as { msg: string }).msg)
              : JSON.stringify(item)
          )
          .join("; ");
      }
      if (typeof detail === "object" && detail !== null) {
        const d = detail as {
          message?: string;
          errors?: Array<{ source_key?: string; display_name?: string; error?: string }>;
        };
        if (d.message && Array.isArray(d.errors) && d.errors.length > 0) {
          const lines = d.errors.map(
            (e) =>
              `${e.display_name || e.source_key || "source"}: ${e.error || "unknown error"}`
          );
          return `${d.message}\n${lines.join("\n")}`;
        }
        if (d.message) return d.message;
        if ("detail" in detail && typeof (detail as { detail: string }).detail === "string") {
          return (detail as { detail: string }).detail;
        }
      }
    }
    return error.message || "An error occurred";
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

export default api;
