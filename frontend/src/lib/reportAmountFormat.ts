const NON_AMOUNT_COLUMNS = new Set([
  "proc_year",
  "proc_month",
  "proc_half",
  "reporting_year",
  "reporting_month",
  "year",
  "month",
  "month_number",
  "emp_no",
  "employee_number",
  "sort_order",
  "headcount",
  "count_of_emp_no",
  "nopay_days",
  "line_count",
  "event_count",
  "active_headcount",
  "net_active_headcount_change_mom",
]);

const AMOUNT_COLUMN_PATTERN =
  /(?:^|_)(amount|salary|cost|rate|pay|tax|deduction|allowance|premium|balance|remittance|contribution|incentive|pegged|hours|gross|net|deductions|payment|payable|ot(?:_|$)|sum_of_)/i;

export function isReportAmountColumn(column: string): boolean {
  const lower = column.toLowerCase();
  if (NON_AMOUNT_COLUMNS.has(lower)) return false;
  if (/^(count|days_|event_|headcount|nopay_days)/i.test(lower)) return false;
  return AMOUNT_COLUMN_PATTERN.test(lower);
}

export function formatReportAmount(value: unknown): string {
  if (value == null || value === "") return "—";
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return String(value);
  return num.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatReportCellValue(column: string, value: unknown): string {
  if (value == null || value === "") return "—";
  if (isReportAmountColumn(column)) return formatReportAmount(value);
  return String(value);
}
