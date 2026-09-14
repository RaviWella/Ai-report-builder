// Summary / Grand-Total mode (generic). Turns selected MEASURES into ROWS — one
// row per measure: its label, the aggregated value and an optional non-zero
// count. Powers Grand-Summary-style reports (Transaction Name | Amount |
// Number of Employees) from ANY wide entity, with no report-specific code.
import { useQuery } from "@tanstack/react-query";
import {
  Box, Checkbox, FormControlLabel, Stack, Switch, TextField, Typography,
} from "@mui/material";
import { semanticApi } from "../../api/client";
import { useBuilderStore } from "../../store/builderStore";
import type { SemanticFieldMeta } from "../../types/spec";

export function SummaryModePanel() {
  const { data: fields = [] } = useQuery({ queryKey: ["fields"], queryFn: semanticApi.fields });
  const { dataSpec, setUnpivot } = useBuilderStore();
  const up = dataSpec.unpivot;
  const measures = (fields as SemanticFieldMeta[]).filter((f) => f.role === "measure");

  const toggle = (on: boolean) =>
    setUnpivot(on
      ? { measures: [], label_header: "Transaction Name", value_header: "Amount",
          count_header: "Number of Employees", agg: "sum" }
      : null);
  const patch = (p: Partial<NonNullable<typeof up>>) => up && setUnpivot({ ...up, ...p });
  const toggleMeasure = (ref: string) =>
    up && setUnpivot({
      ...up,
      measures: up.measures.includes(ref)
        ? up.measures.filter((r) => r !== ref)
        : [...up.measures, ref],
    });

  return (
    <Box>
      <FormControlLabel
        control={<Switch checked={Boolean(up)} onChange={(e) => toggle(e.target.checked)} />}
        label={<Typography sx={{ fontWeight: 600 }}>Summary mode — turn measures into rows</Typography>}
      />
      <Typography variant="body2" color="text.secondary" sx={{ mb: up ? 1.5 : 0 }}>
        Each measure you pick becomes a <b>row</b> (its name, total and how many records have it) —
        e.g. a payroll Grand Summary: Transaction Name · Amount · Number of Employees.
      </Typography>

      {up && (
        <Stack spacing={2}>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
            <TextField size="small" label="Name column" value={up.label_header}
              onChange={(e) => patch({ label_header: e.target.value })} />
            <TextField size="small" label="Value column" value={up.value_header}
              onChange={(e) => patch({ value_header: e.target.value })} />
            <TextField size="small" label="Count column (blank = none)" value={up.count_header ?? ""}
              onChange={(e) => patch({ count_header: e.target.value || null })} />
          </Stack>

          <Box>
            <Typography variant="caption" sx={{ fontWeight: 600 }}>
              Measures to summarise ({up.measures.length} selected)
            </Typography>
            <Box sx={{ maxHeight: 260, overflowY: "auto", border: "1px solid #E5E7EB", borderRadius: 1, p: 1, mt: 0.5 }}>
              {measures.map((m) => (
                <FormControlLabel key={m.ref} sx={{ display: "flex" }}
                  control={<Checkbox size="small" checked={up.measures.includes(m.ref)}
                    onChange={() => toggleMeasure(m.ref)} />}
                  label={<Typography variant="body2">{m.label} <span style={{ color: "#9CA3AF" }}>· {m.entity}</span></Typography>}
                />
              ))}
              {!measures.length && <Typography variant="body2" color="text.secondary">No measures available.</Typography>}
            </Box>
          </Box>
          <Typography variant="caption" color="text.secondary">
            In summary mode the picked measures define the rows; add a Pay Period (or similar) filter to scope it.
          </Typography>
        </Stack>
      )}
    </Box>
  );
}
