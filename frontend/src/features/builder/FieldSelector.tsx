// Field selector (FR-B1) — pick fields from the semantic catalogue, grouped by
// entity. To keep the ~140-field catalogue from becoming a wall, fields live in
// collapsible per-entity groups (groups with a selection start open) and a
// search box filters across every group at once. Click a chip to add/remove.
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert, Box, Chip, Collapse, InputAdornment, Stack, TextField, Typography,
} from "@mui/material";
import { ExpandMore, Search } from "@mui/icons-material";
import { semanticApi } from "../../api/client";
import { useBuilderStore } from "../../store/builderStore";
import type { SemanticFieldMeta } from "../../types/spec";

export function FieldSelector() {
  const { data: fields = [], isError, error } = useQuery({ queryKey: ["fields"], queryFn: semanticApi.fields });
  const fieldsError =
    (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ?? (isError ? "Could not load fields." : "");
  const { dataSpec, addField, removeField } = useBuilderStore();
  const selected = new Set(dataSpec.fields.map((f) => f.ref));
  const [search, setSearch] = useState("");
  // Per-entity open overrides; undefined means "use the default" (open if it
  // contains a selected field). A search query force-opens every match.
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const q = search.trim().toLowerCase();

  const byEntity = useMemo(
    () =>
      (fields as SemanticFieldMeta[]).reduce<Record<string, SemanticFieldMeta[]>>((acc, f) => {
        (acc[f.entity] ??= []).push(f);
        return acc;
      }, {}),
    [fields],
  );

  const groups = useMemo(
    () =>
      Object.entries(byEntity)
        .map(([entity, list]) => {
          const matched = q
            ? list.filter(
                (f) =>
                  f.label.toLowerCase().includes(q) ||
                  f.ref.toLowerCase().includes(q) ||
                  entity.toLowerCase().includes(q),
              )
            : list;
          return [entity, matched] as const;
        })
        .filter(([, list]) => list.length > 0),
    [byEntity, q],
  );

  const toggle = (entity: string, cur: boolean) => setOpen((o) => ({ ...o, [entity]: !cur }));

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
        <Typography variant="h6">Fields</Typography>
        <Typography variant="caption" color="text.secondary">{selected.size} selected</Typography>
      </Stack>

      <TextField
        size="small"
        fullWidth
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search fields — e.g. salary, department, join date"
        slotProps={{
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <Search fontSize="small" sx={{ color: "#9CA3AF" }} />
              </InputAdornment>
            ),
          },
        }}
        sx={{ mb: 1.5 }}
      />

      {fieldsError && (
        <Alert severity="error" sx={{ mb: 1.5 }}>
          {fieldsError}
        </Alert>
      )}

      {groups.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          {fieldsError
            ? "Fix the issue above, then refresh the page."
            : fields.length === 0
              ? "Loading fields…"
              : `No fields match “${search}”.`}
        </Typography>
      ) : (
        <Stack spacing={0.75}>
          {groups.map(([entity, list]) => {
            const selCount = list.filter((f) => selected.has(f.ref)).length;
            const expanded = q ? true : open[entity] ?? selCount > 0;
            return (
              <Box key={entity} sx={{ border: "1px solid #E5E7EB", borderRadius: 2, overflow: "hidden" }}>
                <Stack
                  direction="row"
                  alignItems="center"
                  spacing={1}
                  onClick={() => !q && toggle(entity, expanded)}
                  sx={{
                    px: 1.25, py: 0.85, bgcolor: "#F9FAFB", userSelect: "none",
                    cursor: q ? "default" : "pointer",
                    "&:hover": { bgcolor: q ? "#F9FAFB" : "#F3F4F6" },
                  }}
                >
                  <ExpandMore
                    fontSize="small"
                    sx={{
                      color: "#6B7280",
                      transform: expanded ? "none" : "rotate(-90deg)",
                      transition: "transform .15s ease",
                    }}
                  />
                  <Typography
                    variant="caption"
                    sx={{ fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.4, flex: 1, color: "#374151" }}
                  >
                    {entity}
                  </Typography>
                  <Typography variant="caption" sx={{ color: selCount > 0 ? "primary.main" : "#9CA3AF", fontWeight: selCount > 0 ? 600 : 400 }}>
                    {selCount > 0 ? `${selCount} of ${list.length}` : list.length}
                  </Typography>
                </Stack>
                <Collapse in={expanded} unmountOnExit>
                  <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, p: 1.25 }}>
                    {list.map((f) => (
                      <Chip
                        key={f.ref}
                        label={f.label}
                        size="small"
                        color={selected.has(f.ref) ? "primary" : "default"}
                        variant={selected.has(f.ref) ? "filled" : "outlined"}
                        onClick={() =>
                          selected.has(f.ref) ? removeField(f.ref) : addField({ ref: f.ref, label: f.label })
                        }
                        title={`${f.ref} · ${f.role}`}
                        sx={{ cursor: "pointer" }}
                      />
                    ))}
                  </Box>
                </Collapse>
              </Box>
            );
          })}
        </Stack>
      )}
    </Box>
  );
}
