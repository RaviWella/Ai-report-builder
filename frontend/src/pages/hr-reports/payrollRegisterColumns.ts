import type { HrCsvColumn } from "../../lib/exportHrTableCsv";
import { formatReportAmount } from "../../lib/reportAmountFormat";
import type { PayrollRegisterRow } from "../../services/api";

function money(value?: number | null): string {
  if (value == null) return "";
  return formatReportAmount(value);
}

export const PAYROLL_REGISTER_COLUMNS: HrCsvColumn<PayrollRegisterRow>[] = [
  { key: "emp_no", header: "Emp #" },
  { key: "emp_fullname", header: "Name" },
  { key: "payroll_group_name", header: "Pay group" },
  { key: "designation", header: "Designation" },
  { key: "basic_salary", header: "Basic", value: (r) => money(r.basic_salary) },
  { key: "gross_salary", header: "Gross", value: (r) => money(r.gross_salary) },
  { key: "tax_amount", header: "Tax", value: (r) => money(r.tax_amount) },
  { key: "net_salary", header: "Net", value: (r) => money(r.net_salary) },
];
