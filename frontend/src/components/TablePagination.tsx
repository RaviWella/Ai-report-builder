interface TablePaginationProps {
  total: number;
  limit: number;
  offset: number;
  onPageChange: (page: number) => void;
  disabled?: boolean;
}

export default function TablePagination({
  total,
  limit,
  offset,
  onPageChange,
  disabled = false,
}: TablePaginationProps) {
  if (total <= 0) return null;

  const page = Math.floor(offset / limit);
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const start = offset + 1;
  const end = Math.min(offset + limit, total);
  const canPrev = page > 0;
  const canNext = page < totalPages - 1;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm">
      <p className="text-slate-600">
        Showing <span className="font-medium text-slate-800">{start}</span>
        {"–"}
        <span className="font-medium text-slate-800">{end}</span> of{" "}
        <span className="font-medium text-slate-800">{total.toLocaleString()}</span>
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={disabled || !canPrev}
          className="px-3 py-1.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Previous
        </button>
        <span className="text-slate-500 tabular-nums px-1">
          Page {page + 1} of {totalPages}
        </span>
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={disabled || !canNext}
          className="px-3 py-1.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Next
        </button>
      </div>
    </div>
  );
}
