import api from "./api";

export type CustomReportType = "table" | "payslip";
export type CustomReportSource = "dbt" | "sync";

export interface CustomReportDefinition {
  id: number;
  tenant_id: string;
  module: string;
  report_name: string;
  view_name: string;
  view_query: string | null;
  report_type: CustomReportType;
  source: CustomReportSource;
  sort_order: number;
  is_active: boolean;
  is_system: boolean;
  period_year_column: string | null;
  period_month_column: string | null;
}

export interface CustomReportDefinitionCreate {
  module: string;
  report_name: string;
  view_name: string;
  view_query: string;
  report_type?: CustomReportType;
  sort_order?: number;
}

export interface CustomReportDefinitionUpdate {
  module?: string;
  report_name?: string;
  view_query?: string;
  report_type?: CustomReportType;
  sort_order?: number;
  is_active?: boolean;
}

export interface CustomReportSyncResponse {
  tenant_id: string;
  warehouse_schema: string;
  created: string[];
  skipped: string[];
  errors: string[];
  ok: boolean;
}

export const customReportsService = {
  listDefinitions: (params?: { module?: string; include_inactive?: boolean }) =>
    api
      .get<CustomReportDefinition[]>("/hr/custom-reports/definitions", { params })
      .then((r) => r.data),

  createDefinition: (body: CustomReportDefinitionCreate) =>
    api
      .post<CustomReportDefinition>("/hr/custom-reports/definitions", body)
      .then((r) => r.data),

  updateDefinition: (id: number, body: CustomReportDefinitionUpdate) =>
    api
      .put<CustomReportDefinition>(`/hr/custom-reports/definitions/${id}`, body)
      .then((r) => r.data),

  deleteDefinition: (id: number) =>
    api.delete(`/hr/custom-reports/definitions/${id}`),

  syncDefinitions: () =>
    api
      .post<CustomReportSyncResponse>("/hr/custom-reports/definitions/sync")
      .then((r) => r.data),
};
