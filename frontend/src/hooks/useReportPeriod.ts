import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { hrApi } from "../services/api";

function currentMonthLabel(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

/** Resolves default period from API, then holds user-selected YYYY-MM. */
export function useReportPeriod() {
  const fallbackPeriod = useMemo(() => currentMonthLabel(), []);

  const { data: periodsData, isLoading: periodsLoading, isError } = useQuery({
    queryKey: ["employment-periods"],
    queryFn: () => hrApi.getAvailablePeriods(),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  const defaultPeriod =
    periodsData?.default_period ??
    periodsData?.periods?.[0] ??
    (isError ? fallbackPeriod : undefined);
  const [period, setPeriod] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!period && defaultPeriod) {
      setPeriod(defaultPeriod);
    }
  }, [defaultPeriod, period]);

  const effectivePeriod = period ?? defaultPeriod;

  return {
    period: effectivePeriod,
    setPeriod,
    periods: periodsData?.periods ?? [],
    defaultPeriod,
    isLoading: periodsLoading && !effectivePeriod,
    periodsError: isError,
  };
}
