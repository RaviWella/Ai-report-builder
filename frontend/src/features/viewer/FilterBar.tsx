// Dynamic runtime filter panel for the viewer (FR-V/FR-5.3). Renders the right
// control per filter type: dropdown (enum/dimension — values fetched live), text
// (string), number, date / date-range, boolean. Builds the params object.
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Autocomplete, Box, MenuItem, Stack, TextField,
} from "@mui/material";
import { reportApi, type RuntimeFilter } from "../../api/client";

export type FilterValues = Record<string, unknown>;

// A required period-ish filter is convenient to pre-select to the latest value.
const isPeriodLike = (f: RuntimeFilter) =>
  /period|month|year|cutoff/i.test(`${f.label} ${f.ref ?? ""}`);

function EnumFilter({ templateId, f, value, onChange }: {
  templateId: string; f: RuntimeFilter; value: unknown; onChange: (v: unknown) => void;
}) {
  // Live distinct values for the dropdown (e.g. all designations).
  const { data: values = [] } = useQuery({
    queryKey: ["field-values", templateId, f.ref],
    queryFn: () => reportApi.fieldValues(templateId, f.ref!),
    enabled: Boolean(f.ref),
  });
  const options = (f.enum_values ?? (values as unknown[]).map(String));
  // Pre-select the latest value for a required period filter so the report can
  // run straight away (the user can still change it).
  useEffect(() => {
    if (f.required && isPeriodLike(f) && (value == null || value === "") && options.length) {
      onChange(options[options.length - 1]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.length]);
  return (
    <Autocomplete
      size="small" options={options} value={(value as string) ?? null}
      onChange={(_, v) => onChange(v)} sx={{ minWidth: 220 }}
      renderInput={(p) => <TextField {...p} label={f.label + (f.required ? " *" : "")} placeholder={f.required ? "Required" : "All"} />}
    />
  );
}

export function FilterBar({ templateId, initialValues, onChange, onValidity, onReady }: {
  templateId: string;
  /** Restored filter values (e.g. from sessionStorage after a hard refresh). */
  initialValues?: FilterValues;
  onChange: (v: FilterValues) => void;
  onValidity?: (missing: string[]) => void;
  onReady?: () => void;
}) {
  const { data: filters = [], isSuccess } = useQuery({ queryKey: ["report-meta", templateId], queryFn: () => reportApi.meta(templateId) });
  const [values, setValues] = useState<FilterValues>(initialValues ?? {});

  useEffect(() => { setValues(initialValues ?? {}); }, [templateId, initialValues]);

  useEffect(() => { onChange(values); }, [values, onChange]);
  // Ready only after definitions load AND values settle (enum pre-select, restored
  // session filters, etc.) — avoids auto-running with stale/empty params on refresh.
  useEffect(() => {
    if (!isSuccess || !onReady) return;
    const t = window.setTimeout(() => onReady(), 500);
    return () => window.clearTimeout(t);
  }, [isSuccess, values, onReady]);
  // Report which required filters are still empty (so Run can be blocked).
  useEffect(() => {
    if (!onValidity) return;
    const empty = (v: unknown) =>
      v == null || v === "" || (Array.isArray(v) && v.every((x) => x === "" || x == null));
    onValidity(filters.filter((f) => f.required && empty(values[f.param])).map((f) => f.label));
  }, [values, filters, onValidity]);

  const set = (param: string, v: unknown) =>
    setValues((s) => {
      const next = { ...s };
      if (v === "" || v === null || v === undefined) delete next[param];
      else next[param] = v;
      return next;
    });

  if (filters.length === 0) return null;

  return (
    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.5, alignItems: "center" }}>
      {filters.map((f) => {
        if (f.op === "between" || f.type === "date_range") {
          const cur = (values[f.param] as [string, string]) ?? ["", ""];
          return (
            <Stack key={f.param} direction="row" spacing={1} alignItems="center">
              <TextField size="small" type="date" label={`${f.label}${f.required ? " *" : ""} from`} InputLabelProps={{ shrink: true }}
                value={cur[0]} onChange={(e) => set(f.param, [e.target.value, cur[1]])} />
              <TextField size="small" type="date" label="to" InputLabelProps={{ shrink: true }}
                value={cur[1]} onChange={(e) => set(f.param, [cur[0], e.target.value])} />
            </Stack>
          );
        }
        // Only an explicit "enum/dropdown" filter shows a value list. A plain
        // string (e.g. Employee No) is a free-text box — defined per template.
        if (f.type === "enum") {
          return <EnumFilter key={f.param} templateId={templateId} f={f} value={values[f.param]} onChange={(v) => set(f.param, v)} />;
        }
        if (f.type === "date") {
          return <TextField key={f.param} size="small" type="date" label={f.label + (f.required ? " *" : "")} InputLabelProps={{ shrink: true }}
            value={(values[f.param] as string) ?? ""} onChange={(e) => set(f.param, e.target.value)} />;
        }
        if (f.type === "number" || f.type === "integer" || f.type === "decimal") {
          return <TextField key={f.param} size="small" type="number" label={f.label}
            value={(values[f.param] as string) ?? ""} onChange={(e) => set(f.param, e.target.value === "" ? "" : Number(e.target.value))} sx={{ width: 150 }} />;
        }
        if (f.type === "boolean") {
          return (
            <TextField key={f.param} select size="small" label={f.label} sx={{ width: 130 }}
              value={(values[f.param] as string) ?? ""} onChange={(e) => set(f.param, e.target.value)}>
              <MenuItem value="">All</MenuItem><MenuItem value="true">Yes</MenuItem><MenuItem value="false">No</MenuItem>
            </TextField>
          );
        }
        // default: free text (e.g. employee no)
        return <TextField key={f.param} size="small" label={f.label} placeholder="type to filter…"
          value={(values[f.param] as string) ?? ""} onChange={(e) => set(f.param, e.target.value)} sx={{ minWidth: 180 }} />;
      })}
    </Box>
  );
}
