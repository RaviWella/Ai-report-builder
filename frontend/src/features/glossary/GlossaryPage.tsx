// Business glossary admin — define governed business terms (Take-home Pay,
// Headcount, Attrition) once, each pointing at the governed metric/field that
// computes it. Terms ground the NL builder ("in-hand salary by branch" -> the
// right metric) and document the layer for every user of the tenant.
import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress,
  Snackbar, Stack, TextField, Typography,
} from "@mui/material";
import { MenuBookOutlined, AddCircleOutline } from "@mui/icons-material";
import { glossaryApi, semanticApi } from "../../api/client";
import { FieldSelect } from "../documents/FieldSelect";
import type { GlossaryTerm } from "../../types/glossary";

const blank: GlossaryTerm = { term: "", definition: "", ref: null, category: "", aliases: [] };

export function GlossaryPage() {
  const qc = useQueryClient();
  const { data: terms = [], isLoading } = useQuery({ queryKey: ["glossary"], queryFn: glossaryApi.list });
  const { data: fields = [] } = useQuery({ queryKey: ["fields"], queryFn: semanticApi.fields });
  // A term can point at a metric (entity "Metrics") or any catalogue field.
  const targets = useMemo(() => fields, [fields]);
  const labelForRef = useMemo(() => {
    const m = new Map(fields.map((f) => [f.ref, f.label]));
    return (ref?: string | null) => (ref ? m.get(ref) ?? ref : "");
  }, [fields]);

  const [t, setT] = useState<GlossaryTerm>(blank);
  const [aliasText, setAliasText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [snack, setSnack] = useState("");
  const set = (p: Partial<GlossaryTerm>) => setT((cur) => ({ ...cur, ...p }));

  const save = async () => {
    setBusy(true); setError("");
    const payload: GlossaryTerm = {
      ...t,
      term: t.term.trim(),
      definition: t.definition.trim(),
      aliases: aliasText.split(",").map((s) => s.trim()).filter(Boolean),
      ref: t.ref || null,
      category: t.category?.trim() || null,
    };
    try {
      await glossaryApi.define(payload);
      qc.invalidateQueries({ queryKey: ["glossary"] });
      setSnack(`✓ Term “${payload.term}” saved.`);
      setT(blank); setAliasText("");
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Could not save the term.");
    } finally { setBusy(false); }
  };

  const seed = async () => {
    setBusy(true);
    try {
      const r = await glossaryApi.seedDefaults();
      qc.invalidateQueries({ queryKey: ["glossary"] });
      setSnack(r.created.length ? `✓ Added ${r.created.join(", ")}.` : "All default terms already exist.");
    } finally { setBusy(false); }
  };

  const valid = t.term.trim() && t.definition.trim();

  return (
    <Box sx={{ maxWidth: 980, mx: "auto" }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
        <Typography variant="h4">Glossary</Typography>
        <Button variant="outlined" startIcon={<MenuBookOutlined />} disabled={busy} onClick={seed}>
          Seed defaults
        </Button>
      </Stack>
      <Typography variant="body2" sx={{ mb: 3 }}>
        A glossary term is the governed definition of a business word, pointing at the metric or field that
        computes it. Terms ground the AI builder (so “in-hand salary” finds the right number) and keep
        language consistent for everyone on the tenant.
      </Typography>

      <Box sx={{ display: "grid", gap: 2.5, alignItems: "start", gridTemplateColumns: { xs: "1fr", lg: "minmax(0,1fr) minmax(340px,400px)" } }}>
        {/* Existing terms */}
        <Stack spacing={1.25}>
          {isLoading ? (
            <Box sx={{ textAlign: "center", py: 6 }}><CircularProgress /></Box>
          ) : terms.length === 0 ? (
            <Card><CardContent sx={{ textAlign: "center", py: 5, color: "text.secondary" }}>
              <MenuBookOutlined sx={{ fontSize: 34, color: "#C4CAD2" }} />
              <Typography sx={{ fontWeight: 600, mt: 1 }}>No terms yet</Typography>
              <Typography variant="body2">Seed the defaults or define one on the right.</Typography>
            </CardContent></Card>
          ) : terms.map((x) => (
            <Card key={x.term}><CardContent sx={{ py: 1.5 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                <Box sx={{ pr: 1 }}>
                  <Typography sx={{ fontWeight: 600 }}>{x.term}</Typography>
                  <Typography variant="body2" sx={{ color: "#4B5563", mt: 0.25 }}>{x.definition}</Typography>
                  {x.aliases && x.aliases.length > 0 && (
                    <Typography variant="caption" sx={{ color: "#6B7280" }}>
                      aka: {x.aliases.join(", ")}
                    </Typography>
                  )}
                </Box>
                <Stack direction="row" spacing={0.5} sx={{ flexShrink: 0 }}>
                  {x.category && <Chip size="small" label={x.category} />}
                  {x.ref && (
                    <Chip size="small" color="primary" variant="outlined"
                      label={`→ ${labelForRef(x.ref)}`} />
                  )}
                </Stack>
              </Stack>
            </CardContent></Card>
          ))}
        </Stack>

        {/* Define form */}
        <Card sx={{ position: { lg: "sticky" }, top: { lg: 76 } }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 1.5 }}>Define a term</Typography>
            <Stack spacing={1.5}>
              <Stack direction="row" spacing={1.5}>
                <TextField size="small" label="Term" placeholder="Take-home Pay" value={t.term}
                  onChange={(e) => set({ term: e.target.value })} sx={{ flex: 1 }} />
                <TextField size="small" label="Category" placeholder="payroll" value={t.category ?? ""}
                  onChange={(e) => set({ category: e.target.value })} sx={{ width: 130 }} />
              </Stack>
              <TextField size="small" label="Definition" value={t.definition}
                onChange={(e) => set({ definition: e.target.value })} fullWidth multiline minRows={2}
                placeholder="Net amount an employee receives after all deductions." />
              <Box>
                <Typography variant="caption" sx={{ color: "#6B7280", mb: 0.5, display: "block" }}>
                  Resolves to (metric or field) — optional
                </Typography>
                <FieldSelect fields={targets} value={t.ref ?? null} onChange={(ref) => set({ ref })}
                  placeholder="Pick a metric or field" minWidth={0} />
              </Box>
              <TextField size="small" label="Synonyms (comma-separated)" value={aliasText}
                onChange={(e) => setAliasText(e.target.value)} fullWidth
                placeholder="net pay, in-hand salary" />

              {error && <Alert severity="error">{error}</Alert>}
              <Button variant="contained" startIcon={<AddCircleOutline />} disabled={!valid || busy} onClick={save}>
                Save term
              </Button>
            </Stack>
          </CardContent>
        </Card>
      </Box>

      <Snackbar open={Boolean(snack)} autoHideDuration={5000} onClose={() => setSnack("")}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}>
        <Alert severity="success" variant="filled" onClose={() => setSnack("")}>{snack}</Alert>
      </Snackbar>
    </Box>
  );
}
