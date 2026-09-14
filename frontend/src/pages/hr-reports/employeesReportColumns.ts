import type { HrCsvColumn } from "../../lib/exportHrTableCsv";
import { formatReportAmount } from "../../lib/reportAmountFormat";
import type { EmployeeRow } from "../../services/api";

export const EMPLOYEE_TABLE_COLUMNS: HrCsvColumn<EmployeeRow>[] = [
  { key: "emp_no", header: "Emp #" },
  { key: "emp_fullname", header: "Name" },
  { key: "designation", header: "Designation" },
  { key: "grade", header: "Grade" },
  { key: "legal_entity", header: "Legal entity" },
  {
    key: "basic_salary",
    header: "Basic salary",
    value: (r) => (r.basic_salary != null ? formatReportAmount(r.basic_salary) : ""),
  },
];
