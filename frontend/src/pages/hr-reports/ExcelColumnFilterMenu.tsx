import { useEffect, useMemo, useRef, useState } from "react";
import { Search } from "lucide-react";
import { columnFilterLabel } from "./columnFilterUtils";

interface ExcelColumnFilterMenuProps {
  column: string;
  values: string[];
  loading?: boolean;
  initialSelected: string[];
  onApply: (selected: string[]) => void;
  onClear: () => void;
  onClose: () => void;
}

export default function ExcelColumnFilterMenu({
  column,
  values,
  loading = false,
  initialSelected,
  onApply,
  onClear,
  onClose,
}: ExcelColumnFilterMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [miniFilter, setMiniFilter] = useState("");
  const [checked, setChecked] = useState<Set<string>>(
    () => new Set(initialSelected.length ? initialSelected : values),
  );

  useEffect(() => {
    if (!loading) {
      setChecked(new Set(initialSelected.length ? initialSelected : values));
    }
  }, [loading, values, initialSelected]);

  const visibleValues = useMemo(() => {
    const query = miniFilter.trim().toLowerCase();
    if (!query) return values;
    return values.filter((value) => value.toLowerCase().includes(query));
  }, [values, miniFilter]);

  const allVisibleSelected =
    visibleValues.length > 0 && visibleValues.every((value) => checked.has(value));
  const someVisibleSelected = visibleValues.some((value) => checked.has(value));

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [onClose]);

  function toggleValue(value: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  function toggleSelectAllVisible() {
    setChecked((prev) => {
      const next = new Set(prev);
      if (allVisibleSelected) {
        for (const value of visibleValues) next.delete(value);
      } else {
        for (const value of visibleValues) next.add(value);
      }
      return next;
    });
  }

  function handleApply() {
    onApply(Array.from(checked));
    onClose();
  }

  return (
    <div
      ref={menuRef}
      role="dialog"
      aria-label={`Filter ${columnFilterLabel(column)}`}
      className="absolute left-0 top-full z-50 mt-1 w-64 rounded-lg border border-slate-200 bg-white shadow-lg"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="border-b border-slate-100 px-3 py-2">
        <p className="text-xs font-semibold text-slate-700 capitalize">
          {columnFilterLabel(column)}
        </p>
      </div>

      <div className="border-b border-slate-100 p-2">
        <div className="relative">
          <Search
            size={14}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            type="search"
            value={miniFilter}
            onChange={(e) => setMiniFilter(e.target.value)}
            placeholder="Search"
            className="w-full rounded-md border border-slate-300 py-1.5 pl-8 pr-2 text-sm text-slate-900 placeholder:text-slate-400"
            autoFocus
          />
        </div>
      </div>

      <label className="flex cursor-pointer items-center gap-2 border-b border-slate-100 px-3 py-2 text-sm text-slate-800 hover:bg-slate-50">
        <input
          type="checkbox"
          checked={allVisibleSelected}
          ref={(el) => {
            if (el) el.indeterminate = someVisibleSelected && !allVisibleSelected;
          }}
          onChange={toggleSelectAllVisible}
          className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
        />
        <span className="font-medium">(Select All)</span>
      </label>

      <div className="max-h-52 overflow-y-auto py-1">
        {loading ? (
          <p className="px-3 py-4 text-center text-xs text-slate-500">Loading values…</p>
        ) : visibleValues.length === 0 ? (
          <p className="px-3 py-4 text-center text-xs text-slate-500">No matching values</p>
        ) : (
          visibleValues.map((value) => (
            <label
              key={value}
              className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
            >
              <input
                type="checkbox"
                checked={checked.has(value)}
                onChange={() => toggleValue(value)}
                className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
              />
              <span className="truncate" title={value}>
                {value}
              </span>
            </label>
          ))
        )}
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-slate-100 px-2 py-2">
        <button
          type="button"
          onClick={() => {
            onClear();
            onClose();
          }}
          className="rounded px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
        >
          Clear filter
        </button>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleApply}
            className="rounded-md bg-teal-600 px-3 py-1 text-xs font-medium text-white hover:bg-teal-700"
          >
            OK
          </button>
        </div>
      </div>
    </div>
  );
}
