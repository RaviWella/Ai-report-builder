// Filter panel (FR-B2). A "runtime" filter becomes a control in the Viewer; the
// builder picks how it appears (Dropdown / Text / Number / Date / Date range),
// stored as the runtime param's type. The param name is the FULL field ref so it
// stays unique and in-sync when the field is changed. Static filters fix a value.
import { useQuery } from "@tanstack/react-query";
import {
  Autocomplete, Box, Button, Checkbox, createFilterOptions, FormControlLabel, IconButton,
  MenuItem, Select, Stack, Switch, TextField, Tooltip, Typography,
} from "@mui/material";
import { Add, Close } from "@mui/icons-material";
import { semanticApi } from "../../api/client";
import { useBuilderStore } from "../../store/builderStore";
import type {
  DataSpec, FilterClause, FilterOp, ParamType, SemanticFieldMeta,
} from "../../types/spec";

// Search matches the field label, ref and entity — so a filter field is easy to
// find in a 140-field catalogue (same as the column mapping picker).
const fieldFilter = createFilterOptions<SemanticFieldMeta>({
  stringify: (o) => `${o.label} ${o.ref} ${o.entity}`,
});

// Plain-language operator labels — HR admins shouldn't have to read `gte`.
// Order is the dropdown order; values stay the wire-level FilterOp.
const OPS: { v: FilterOp; label: string }[] = [
  { v: "eq", label: "is" },
  { v: "neq", label: "is not" },
  { v: "gt", label: "greater than" },
  { v: "lt", label: "less than" },
  { v: "gte", label: "at least" },
  { v: "lte", label: "at most" },
  { v: "between", label: "is between" },
  { v: "in", label: "is any of" },
  { v: "contains", label: "contains" },
  { v: "is_null", label: "is empty" },
  { v: "is_not_null", label: "is not empty" },
];
const INPUT_TYPES: { v: ParamType; label: string }[] = [
  { v: "enum", label: "Dropdown" },
  { v: "string", label: "Text" },
  { v: "number", label: "Number" },
  { v: "date", label: "Date" },
  { v: "date_range", label: "Date range" },
  { v: "boolean", label: "Yes/No" },
];

export function FilterPanel() {
  const { data: fields = [] } = useQuery({ queryKey: ["fields"], queryFn: semanticApi.fields });
  const { dataSpec, setFilters, setRuntimeParams } = useBuilderStore();
  const rps = dataSpec.runtime_params;

  const fieldOf = (ref: string) => fields.find((f: SemanticFieldMeta) => f.ref === ref);
  const defaultType = (ref: string): ParamType => {
    const fld = fieldOf(ref);
    if (!fld) return "string";
    if (fld.type === "date" || fld.type === "datetime") return "date";
    if (fld.type === "integer" || fld.type === "decimal") return "number";
    if (fld.type === "boolean") return "boolean";
    return fld.role === "dimension" ? "enum" : "string";
  };
  const paramType = (name: string): ParamType =>
    (rps.find((p) => p.name === name)?.type as ParamType) ?? "string";
  const paramRequired = (name: string): boolean =>
    rps.find((p) => p.name === name)?.required ?? false;

  // Rebuild runtime_params from the current filters — one per runtime filter,
  // keyed by its ref (unique). Preserves the chosen type where the param exists.
  const syncParams = (filters: FilterClause[]) => {
    const out: DataSpec["runtime_params"] = [];
    const seen = new Set<string>();
    for (const f of filters) {
      if (f.param == null || seen.has(f.param)) continue;
      seen.add(f.param);
      const existing = rps.find((p) => p.name === f.param);
      out.push(existing ?? { name: f.param, type: defaultType(f.ref), required: false, label: fieldOf(f.ref)?.label });
    }
    setRuntimeParams(out);
  };

  const commit = (filters: FilterClause[]) => { setFilters(filters); syncParams(filters); };

  // New filters default to RUNTIME (appear in the Viewer); toggle off for static.
  const add = () => {
    const ref = fields[0]?.ref ?? "";
    if (!ref) return;
    commit([...dataSpec.filters, { ref, op: "eq", param: ref }]);
  };
  const remove = (i: number) => commit(dataSpec.filters.filter((_, idx) => idx !== i));

  const setRef = (i: number, ref: string) =>
    commit(dataSpec.filters.map((f, idx) => (idx === i ? { ...f, ref, param: f.param != null ? ref : null } : f)));
  const setOp = (i: number, op: FilterOp) =>
    setFilters(dataSpec.filters.map((f, idx) => (idx === i ? { ...f, op } : f)));
  const setValue = (i: number, value: unknown) =>
    setFilters(dataSpec.filters.map((f, idx) => (idx === i ? { ...f, value } : f)));
  const toggleRuntime = (i: number, on: boolean) =>
    commit(dataSpec.filters.map((f, idx) => (idx === i ? { ...f, param: on ? f.ref : null, value: on ? undefined : "" } : f)));
  const setType = (param: string, type: ParamType) =>
    setRuntimeParams(rps.map((p) => (p.name === param ? { ...p, type } : p)));
  const setRequired = (param: string, required: boolean) =>
    setRuntimeParams(rps.map((p) => (p.name === param ? { ...p, required } : p)));
  const paramLabel = (name: string): string =>
    rps.find((p) => p.name === name)?.label ?? "";
  const setLabel = (param: string, label: string) =>
    setRuntimeParams(rps.map((p) => (p.name === param ? { ...p, label } : p)));

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
        <Typography variant="h6">Filters</Typography>
        <Button size="small" startIcon={<Add />} onClick={add}>Filter</Button>
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
        <b>Runtime</b> filters appear as controls in the Viewer — pick how each one looks.
      </Typography>
      <Stack spacing={1}>
        {dataSpec.filters.map((f, i) => (
          <Stack key={i} direction="row" spacing={1} alignItems="center" flexWrap="wrap">
            <Autocomplete
              size="small" sx={{ minWidth: 190 }} blurOnSelect
              options={fields as SemanticFieldMeta[]}
              groupBy={(o) => o.entity} getOptionLabel={(o) => o.label} filterOptions={fieldFilter}
              isOptionEqualToValue={(o, v) => o.ref === v.ref}
              value={fieldOf(f.ref) ?? null}
              onChange={(_, v) => v && setRef(i, v.ref)}
              renderOption={(props, o) => (
                <li {...props} key={o.ref}>
                  <Box><Typography variant="body2">{o.label}</Typography>
                    <Typography variant="caption" color="text.secondary">{o.ref}</Typography></Box>
                </li>
              )}
              renderInput={(p) => <TextField {...p} placeholder="Search a field…" />}
            />
            {f.param != null && (
              <TextField size="small" sx={{ minWidth: 150 }} placeholder={fieldOf(f.ref)?.label ?? "Label"}
                label="Label shown in Viewer" value={paramLabel(f.param)}
                onChange={(e) => setLabel(f.param!, e.target.value)} />
            )}
            <Select size="small" value={f.op} onChange={(e) => setOp(i, e.target.value as FilterOp)} sx={{ minWidth: 130 }}>
              {OPS.map((op) => <MenuItem key={op.v} value={op.v}>{op.label}</MenuItem>)}
            </Select>
            {f.param != null ? (
              <Select size="small" value={paramType(f.param)} sx={{ minWidth: 130 }}
                onChange={(e) => setType(f.param!, e.target.value as ParamType)}>
                {INPUT_TYPES.map((t) => <MenuItem key={t.v} value={t.v}>as {t.label}</MenuItem>)}
              </Select>
            ) : (
              <TextField size="small" placeholder="value" value={String(f.value ?? "")} onChange={(e) => setValue(i, e.target.value)} />
            )}
            <FormControlLabel
              control={<Switch size="small" checked={f.param != null} onChange={(e) => toggleRuntime(i, e.target.checked)} />}
              label={<Typography variant="caption">runtime</Typography>}
            />
            {f.param != null && (
              <Tooltip title="User must choose a value before the report can run (e.g. payroll period)">
                <FormControlLabel
                  control={<Checkbox size="small" checked={paramRequired(f.param)} onChange={(e) => setRequired(f.param!, e.target.checked)} />}
                  label={<Typography variant="caption">required</Typography>}
                />
              </Tooltip>
            )}
            <IconButton size="small" onClick={() => remove(i)}><Close fontSize="small" /></IconButton>
          </Stack>
        ))}
        {!dataSpec.filters.length && <Typography variant="body2">No filters.</Typography>}
      </Stack>
    </Box>
  );
}
