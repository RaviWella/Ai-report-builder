import ReportEmptyState from "../../components/ReportEmptyState";

export function reportNoPeriodEmpty() {
  return (
    <ReportEmptyState
      title="No reporting period available"
      hint="Run HR ETL and dbt to populate month-end snapshots, then refresh this page."
      action={{ label: "Open ETL Control", to: "/etl/control" }}
    />
  );
}

function periodLabel(period?: string | null): string {
  return period ? ` for ${period}` : " for this period";
}

export function employeesTableEmpty(period?: string | null) {
  return (
    <ReportEmptyState
      title={`No employees${periodLabel(period)}`}
      hint="Change the period filter, or run ETL if this month has not been extracted yet."
      action={{ label: "Open ETL Control", to: "/etl/control" }}
    />
  );
}

export function payrollRegisterEmpty(period?: string | null) {
  return (
    <ReportEmptyState
      title={`No payroll register rows${periodLabel(period)}`}
      hint="Posted payroll appears after ETL and dbt build snapshots for the month. Try another period or confirm payroll was processed in your source HR system."
      action={{ label: "Open ETL Control", to: "/etl/control" }}
    />
  );
}

export function payrollComponentsEmpty(period?: string | null) {
  return (
    <ReportEmptyState
      title={`No pay component lines${periodLabel(period)}`}
      hint="Additions and deductions appear when payroll lines exist for the period. Check the payroll register section after payroll is posted."
    />
  );
}

export function payrollComplianceEmpty(period?: string | null) {
  return (
    <ReportEmptyState
      title={`No statutory amounts${periodLabel(period)}`}
      hint="EPF and ETF totals appear when compliance snapshots exist for the month. Run ETL after payroll close, then refresh this report."
      action={{ label: "Open ETL Control", to: "/etl/control" }}
    />
  );
}

export function headcountMonthlyEmpty() {
  return (
    <ReportEmptyState
      title="No monthly headcount rows yet"
      hint="History fills in after successful ETL runs. Run ETL or pick a period that already has extracts."
      action={{ label: "Open ETL Control", to: "/etl/control" }}
    />
  );
}

export function lifecycleTableEmpty(period?: string | null) {
  return (
    <ReportEmptyState
      title={`No lifecycle events${periodLabel(period)}`}
      hint="Hires, terminations, and transfers may not have been recorded for this month. Try an adjacent period or confirm events in your HR source system."
    />
  );
}

export function salaryBandsTableEmpty(period?: string | null) {
  return (
    <ReportEmptyState
      title={`No salary bands${periodLabel(period)}`}
      hint="Bands need employee and grade data for the month. Run ETL, confirm source databases, or change the period filter."
      action={{ label: "Configure source databases", to: "/settings/etl-sources" }}
    />
  );
}

export function payslipLinesEmpty() {
  return (
    <ReportEmptyState
      title="No payslip lines for this employee and period"
      hint="Select another employee or period if payroll was not posted for this combination."
    />
  );
}
