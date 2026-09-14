import type { CustomReportView } from "../services/api";

/**
 * Payroll-area period filter registry lives in the backend:
 * `backend/app/services/hr_etl/payroll_report_period_config.py`
 *
 * The API exposes `supports_period_filter` on each custom report view.
 */
export function viewSupportsPayrollPeriodFilter(view: CustomReportView): boolean {
  return view.supports_period_filter === true;
}
