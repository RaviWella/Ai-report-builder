export function periodKey(year: number, month: number) {
  return `${year}-${month}`;
}

export function periodLabel(year: number, month: number) {
  return `${year}-${String(month).padStart(2, "0")}`;
}

export function parsePeriodKey(key: string): { proc_year: number; proc_month: number } {
  const [year, month] = key.split("-").map(Number);
  return { proc_year: year, proc_month: month };
}

export type ReportExportFilters = {
  proc_year: number;
  proc_month: number;
  emp_no?: string;
};
