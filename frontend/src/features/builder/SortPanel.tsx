// Sort panel — sets the report's fixed ORDER BY (author-time, not a Viewer
// control). Multiple rows are applied in order (first row = primary sort),
// matching DataSpec.sort / the compiler's ORDER BY. Mirrors FilterPanel's
// field-picker pattern.
import { useQuery } from "@tanstack/react-query";
import {
  Autocomplete, Box, Button, IconButton, MenuItem, Select, Stack, TextField, Typography,
} from "@mui/material";
import { Add, ArrowDownward, ArrowUpward, Close } from "@mui/icons-material";
import { semanticApi } from "../../api/client";
import { useBuilderStore } from "../../store/builderStore";
import type { SemanticFieldMeta, SortDir } from "../../types/spec";

export function SortPanel() {
  const { data: fields = [] } = useQuery({ queryKey: ["fields"], queryFn: semanticApi.fields });
  const { dataSpec, setSort } = useBuilderStore();
  const sort = dataSpec.sort;

  const fieldOf = (ref: string) => (fields as SemanticFieldMeta[]).find((f) => f.ref === ref);

  const add = () => {
    const ref = dataSpec.fields.find((f) => !sort.some((s) => s.ref === f.ref))?.ref;
    if (!ref) return;
    setSort([...sort, { ref, dir: "asc" }]);
  };
  const remove = (i: number) => setSort(sort.filter((_, idx) => idx !== i));
  const setRef = (i: number, ref: string) =>
    setSort(sort.map((s, idx) => (idx === i ? { ...s, ref } : s)));
  const setDir = (i: number, dir: SortDir) =>
    setSort(sort.map((s, idx) => (idx === i ? { ...s, dir } : s)));
  const move = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= sort.length) return;
    const next = [...sort];
    [next[i], next[j]] = [next[j], next[i]];
    setSort(next);
  };

  // Only offer columns actually on the report — sorting by something not shown is confusing.
  const options = dataSpec.fields
    .map((f) => fieldOf(f.ref))
    .filter((f): f is SemanticFieldMeta => Boolean(f));

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
        <Typography variant="h6">Sort</Typography>
        <Button size="small" startIcon={<Add />} onClick={add} disabled={sort.length >= dataSpec.fields.length}>
          Sort
        </Button>
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
        Rows are ordered top to bottom — e.g. Date then Employee groups every employee under
        each date; Employee then Date groups every date under each employee.
      </Typography>
      <Stack spacing={1}>
        {sort.map((s, i) => (
          <Stack key={i} direction="row" spacing={1} alignItems="center">
            <Autocomplete
              size="small" sx={{ minWidth: 220 }} blurOnSelect
              options={options}
              groupBy={(o) => o.entity} getOptionLabel={(o) => o.label}
              isOptionEqualToValue={(o, v) => o.ref === v.ref}
              value={fieldOf(s.ref) ?? null}
              onChange={(_, v) => v && setRef(i, v.ref)}
              renderInput={(p) => <TextField {...p} placeholder="Column…" />}
            />
            <Select size="small" value={s.dir} onChange={(e) => setDir(i, e.target.value as SortDir)} sx={{ minWidth: 120 }}>
              <MenuItem value="asc">A → Z / 1 → 9</MenuItem>
              <MenuItem value="desc">Z → A / 9 → 1</MenuItem>
            </Select>
            <IconButton size="small" disabled={i === 0} onClick={() => move(i, -1)}>
              <ArrowUpward fontSize="small" />
            </IconButton>
            <IconButton size="small" disabled={i === sort.length - 1} onClick={() => move(i, 1)}>
              <ArrowDownward fontSize="small" />
            </IconButton>
            <IconButton size="small" onClick={() => remove(i)}><Close fontSize="small" /></IconButton>
          </Stack>
        ))}
        {!sort.length && <Typography variant="body2">No sort set — rows come back in the datamart's own order.</Typography>}
      </Stack>
    </Box>
  );
}
