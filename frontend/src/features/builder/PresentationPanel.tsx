// Branding & layout (FR-B8) — report title, header, footer, page orientation and
// totals. Drives the on-screen preview and the branded Excel/PDF exports.
import {
  Box, FormControlLabel, MenuItem, Stack, Switch, TextField, Typography,
} from "@mui/material";
import { useBuilderStore } from "../../store/builderStore";

export function PresentationPanel() {
  const { presentation, updateBranding, updatePage } = useBuilderStore();

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 0.5 }}>Header, Footer & Layout</Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1.5 }}>
        These appear on the branded Excel / PDF export.
      </Typography>

      <Stack spacing={1.5}>
        <TextField size="small" label="Header (top of page)" value={presentation.branding.header ?? ""}
          onChange={(e) => updateBranding({ header: e.target.value })}
          placeholder="e.g. Amazon (Pvt) Ltd — Confidential" />

        <TextField size="small" label="Footer (bottom of page)" value={presentation.branding.footer ?? ""}
          onChange={(e) => updateBranding({ footer: e.target.value })}
          placeholder="e.g. Confidential — HR use only" />

        <Stack direction="row" spacing={2} alignItems="center">
          <TextField select size="small" label="Page orientation" value={presentation.page.orientation}
            onChange={(e) => updatePage({ orientation: e.target.value })} sx={{ minWidth: 160 }}>
            <MenuItem value="portrait">Portrait</MenuItem>
            <MenuItem value="landscape">Landscape</MenuItem>
          </TextField>
          <FormControlLabel
            control={<Switch checked={presentation.page.totals}
              onChange={(e) => updatePage({ totals: e.target.checked })} />}
            label={<Typography variant="body2">Show totals row</Typography>}
          />
        </Stack>
      </Stack>
    </Box>
  );
}
