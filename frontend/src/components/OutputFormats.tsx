// Per-template output permissions: which of View (on-screen table) / Excel / PDF
// the viewer offers. Used by the report builder and the payslip builder.
import { Checkbox, FormControlLabel, Stack, Typography } from "@mui/material";

const ALL = [
  { v: "view", label: "View (table)" },
  { v: "excel", label: "Excel" },
  { v: "pdf", label: "PDF" },
] as const;

export function OutputFormats({
  value, onChange,
}: {
  value: string[];
  onChange: (next: string[]) => void;
}) {
  const toggle = (v: string) =>
    onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  return (
    <Stack direction="row" spacing={0.5} flexWrap="wrap">
      {ALL.map((o) => (
        <FormControlLabel
          key={o.v}
          control={<Checkbox size="small" checked={value.includes(o.v)} onChange={() => toggle(o.v)} />}
          label={<Typography variant="body2">{o.label}</Typography>}
        />
      ))}
    </Stack>
  );
}
