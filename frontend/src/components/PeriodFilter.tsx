import { useQuery } from "@tanstack/react-query";
import { hrApi } from "../services/api";

export interface PeriodFilterProps {
  value: string | undefined;
  onChange: (period: string) => void;
  label?: string;
  className?: string;
}

/** Month picker (YYYY-MM) backed by /hr/employment/periods. */
export default function PeriodFilter({
  value,
  onChange,
  label = "Period",
  className = "",
}: PeriodFilterProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["employment-periods"],
    queryFn: () => hrApi.getAvailablePeriods(),
    staleTime: 5 * 60 * 1000,
  });

  const periods = data?.periods ?? [];
  const selected = value ?? "";

  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      <label
        htmlFor="period-filter"
        className="text-sm font-medium"
        style={{ color: "var(--color-muted)" }}
      >
        {label}
      </label>
      <select
        id="period-filter"
        value={selected}
        disabled={isLoading || periods.length === 0}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-[2.75rem] min-w-[8.5rem] rounded-lg px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40"
        style={{
          border: "1px solid var(--color-border)",
          background: "#ffffff",
          color: "var(--color-text)",
        }}
      >
        {isLoading && <option value="">Loading…</option>}
        {!isLoading && periods.length === 0 && (
          <option value="">No periods</option>
        )}
        {periods.map((p) => (
          <option key={p} value={p}>
            {p}
            {p === data?.default_period ? " (latest)" : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
