/**
 * MetricCard — lightweight metric display primitive.
 */
import clsx from "clsx";
import { HR_CURRENCY } from "../env";

interface MetricCardProps {
  label: string;
  value: number | null | undefined;
  unit?: string;
  currency?: string;
  trend?: "up" | "down" | "neutral";
  goodDirection?: "up" | "down";
  subtitle?: string;
  className?: string;
  /** Primary KPI emphasis for dashboard headlines */
  variant?: "default" | "lead";
}

function formatValue(
  value: number | null | undefined,
  unit: string,
  currency: string
): string {
  if (value === null || value === undefined) return "—";
  if (unit === "percent") return `${value.toFixed(1)}%`;
  if (unit === "currency") {
    return new Intl.NumberFormat("en-LK", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(value);
  }
  if (unit === "days" || unit === "hours") return `${value.toFixed(1)}`;
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}

function toneClass(
  trend: "up" | "down" | "neutral" | undefined,
  goodDirection: "up" | "down" | undefined
): string {
  if (!trend || trend === "neutral") return "";
  const isGood =
    (trend === "up" && goodDirection === "up") ||
    (trend === "down" && goodDirection === "down");
  return isGood ? "metric-card--positive" : "metric-card--negative";
}

export default function MetricCard({
  label,
  value,
  unit = "count",
  currency = HR_CURRENCY,
  trend,
  goodDirection,
  subtitle,
  className,
  variant = "default",
}: MetricCardProps) {
  const isLead = variant === "lead";
  return (
    <div
      className={clsx(
        "metric-card",
        isLead && "metric-card--lead",
        toneClass(trend, goodDirection),
        className
      )}
    >
      <span className="metric-card__label">{label}</span>
      <span className="metric-card__value">{formatValue(value, unit, currency)}</span>
      {subtitle ? <span className="metric-card__subtitle">{subtitle}</span> : null}
    </div>
  );
}
