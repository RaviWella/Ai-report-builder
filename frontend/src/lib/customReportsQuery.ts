/** Shared React Query keys for Report Studio catalog reads. */
export const CUSTOM_REPORTS_QUERY_KEY = ["custom-reports", "all"] as const;

/** Cache report catalog metadata — changes only after config save or ETL sync. */
export const CUSTOM_REPORTS_STALE_MS = 5 * 60 * 1000;
