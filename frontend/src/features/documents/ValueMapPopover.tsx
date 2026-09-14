// After picking a field that has known sample values (e.g. Gender: Male/Female),
// offer to map each value to different display text — e.g. Male -> he, Female ->
// she — instead of inserting the raw value. Generic: works for any dimension
// with sample values, not just gender. Skipped entirely for fields with none,
// so every other "insert field" flow is unaffected.
import { useEffect, useState } from "react";
import { Box, Button, Popover, Stack, TextField, Typography } from "@mui/material";
import type { SemanticFieldMeta } from "../../types/spec";

export function ValueMapPopover({
  anchorEl, field, onClose, onInsert,
}: {
  anchorEl: HTMLElement | null;
  field: SemanticFieldMeta | null;
  onClose: () => void;
  onInsert: (tokenInner: string) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [defaultText, setDefaultText] = useState("");

  useEffect(() => {
    setValues({});
    setDefaultText("");
  }, [field]);

  if (!field) return null;
  const samples = field.sample_values ?? [];

  const insertPlain = () => { onInsert(field.ref); onClose(); };
  const insertMapped = () => {
    const parts = [field.ref];
    for (const sample of samples) {
      const text = values[sample]?.trim();
      if (text) parts.push(`${sample}=${text}`);
    }
    if (defaultText.trim()) parts.push(`default=${defaultText.trim()}`);
    onInsert(parts.join("|"));
    onClose();
  };
  const hasAnyMapping = samples.some((s) => values[s]?.trim()) || defaultText.trim();

  return (
    <Popover open={Boolean(anchorEl)} anchorEl={anchorEl} onClose={onClose}
      anchorOrigin={{ vertical: "bottom", horizontal: "left" }}>
      <Box sx={{ p: 2, width: 320 }}>
        <Typography variant="subtitle2" sx={{ mb: 0.5 }}>{field.label}</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1.5 }}>
          Show different text depending on the value — e.g. Male → he, Female → she.
          Leave blank to insert the field as-is.
        </Typography>
        <Stack spacing={1}>
          {samples.map((sample) => (
            <TextField key={sample} size="small" label={sample} placeholder="Show as…"
              value={values[sample] ?? ""}
              onChange={(e) => setValues((v) => ({ ...v, [sample]: e.target.value }))} />
          ))}
          <TextField size="small" label="Any other value" placeholder="e.g. they"
            value={defaultText} onChange={(e) => setDefaultText(e.target.value)} />
        </Stack>
        <Stack direction="row" spacing={1} sx={{ mt: 2, justifyContent: "flex-end" }}>
          <Button size="small" onClick={insertPlain}>Insert as-is</Button>
          <Button size="small" variant="contained" disabled={!hasAnyMapping} onClick={insertMapped}>
            Insert with mapping
          </Button>
        </Stack>
      </Box>
    </Popover>
  );
}
