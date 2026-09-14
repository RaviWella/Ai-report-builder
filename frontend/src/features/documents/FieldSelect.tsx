// Grouped field picker used in the document review step. Wraps MUI Autocomplete
// over the semantic catalogue; an empty value reads as "needs a field".
import { Autocomplete, Box, TextField } from "@mui/material";
import type { SemanticFieldMeta } from "../../types/spec";

export function FieldSelect({
  fields, value, onChange, placeholder, minWidth = 260, optional = false,
}: {
  fields: SemanticFieldMeta[];
  value: string | null;
  onChange: (ref: string | null) => void;
  placeholder?: string;
  minWidth?: number;
  optional?: boolean; // when true, an empty value is fine (no error styling)
}) {
  const selected = fields.find((f) => f.ref === value) ?? null;
  const options = [...fields].sort((a, b) =>
    Number(!!b.is_anchor) - Number(!!a.is_anchor)
    || a.entity.localeCompare(b.entity) || a.label.localeCompare(b.label));
  return (
    <Autocomplete
      size="small"
      options={options}
      groupBy={(f) => f.entity}
      getOptionLabel={(f) => f.label}
      value={selected}
      isOptionEqualToValue={(a, b) => a.ref === b.ref}
      onChange={(_, v) => onChange(v?.ref ?? null)}
      // Prefer beside the field when there is no room below — flipping upward
      // covers Paper / Orientation in the letter designer's narrow rail.
      slotProps={{
        popper: {
          modifiers: [
            { name: "flip", options: { fallbackPlacements: ["left-start", "right-start"] } },
            { name: "preventOverflow", options: { padding: 8, altAxis: true } },
          ],
        },
        paper: { sx: { minWidth: 280 } },
        listbox: { sx: { maxHeight: 280 } },
      }}
      // Default groupBy uses a sticky ListSubheader that clips the first option
      // ("Branch" under "Employee") depending on highlight / scroll.
      renderGroup={(params) => (
        <li key={params.key}>
          <Box sx={{ px: 1.5, pt: 1, pb: 0.25, fontSize: "0.68rem", fontWeight: 700, color: "text.secondary" }}>
            {params.group}
          </Box>
          <ul style={{ padding: 0, margin: 0 }}>{params.children}</ul>
        </li>
      )}
      renderInput={(p) => (
        <TextField {...p} placeholder={placeholder ?? "Pick a field"} error={!value && !optional} />
      )}
      renderOption={(props, o) => (
        <li {...props} key={o.ref}>
          <Box>
            <Box sx={{ fontSize: "0.85rem" }}>{o.label}</Box>
            {o.description && (
              <Box sx={{ fontSize: "0.7rem", color: "#6B7280" }}>{o.description}</Box>
            )}
            {!!o.sample_values?.length && (
              <Box sx={{ fontSize: "0.7rem", color: "#6B7280", fontStyle: "italic" }}>
                e.g. {o.sample_values.join(", ")}
              </Box>
            )}
          </Box>
        </li>
      )}
      sx={{ minWidth }}
    />
  );
}
