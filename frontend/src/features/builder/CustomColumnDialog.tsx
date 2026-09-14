// Define a custom column (FR-B5) — a governed derived field over existing
// fields. Two kinds: FORMULA (arithmetic, e.g. Take Home = Net − Loan) and
// BANDING (CASE WHEN … → label, e.g. Age < 20 → "Under 20"). No SQL is written
// by the user; the Query Engine compiles the structured spec to safe SQL.
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert, Autocomplete, Box, Button, Chip, ClickAwayListener, createFilterOptions, Dialog, DialogActions,
  DialogContent, DialogTitle, IconButton, InputAdornment, List, ListItemButton, ListItemText,
  MenuItem, Paper, Popper, Stack, Tab, Tabs, TextField, Tooltip, Typography,
} from "@mui/material";
import { Add, Close, AutoAwesome, DataObjectOutlined, SearchOutlined } from "@mui/icons-material";
import { semanticApi, aiApi } from "../../api/client";
import { useBuilderStore } from "../../store/builderStore";
import { formulaTokenAt, insertFormulaRef, matchFormulaFields, opLabel } from "./calcFieldUtils";
import type { CalcCase, CalculatedField, FilterOp, SemanticFieldMeta } from "../../types/spec";

const fieldFilter = createFilterOptions<SemanticFieldMeta>({
  stringify: (o) => `${o.label} ${o.ref} ${o.entity}`,
});

// Plain-language labels — same wording as the filter panel.
const OPS: { v: FilterOp; label: string }[] = [
  { v: "lt", label: "less than" },
  { v: "lte", label: "at most" },
  { v: "gt", label: "greater than" },
  { v: "gte", label: "at least" },
  { v: "eq", label: "is" },
  { v: "neq", label: "is not" },
  { v: "between", label: "is between" },
  { v: "contains", label: "contains" },
];
const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "custom";

function FormulaFieldInput({
  expression,
  onExpressionChange,
  fields,
  active,
}: {
  expression: string;
  onExpressionChange: (next: string) => void;
  fields: SemanticFieldMeta[];
  active: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [caret, setCaret] = useState(0);
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const [chipQuery, setChipQuery] = useState("");

  const measures = useMemo(
    () => fields.filter((f) => f.role === "measure"),
    [fields],
  );
  const token = formulaTokenAt(expression, caret);
  const suggestions = useMemo(
    () => matchFormulaFields(measures, token.text),
    [measures, token.text],
  );
  const chips = useMemo(
    () => (chipQuery.trim() ? matchFormulaFields(measures, chipQuery) : measures),
    [measures, chipQuery],
  );
  const showSuggest = suggestOpen && token.text.length > 0 && suggestions.length > 0;

  useEffect(() => { setHighlight(0); }, [token.text]);
  useEffect(() => {
    if (!active) { setChipQuery(""); setSuggestOpen(false); }
  }, [active]);

  const applyInsert = (next: string, nextCaret: number) => {
    const el = inputRef.current;
    onExpressionChange(next);
    setSuggestOpen(false);
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(nextCaret, nextCaret);
      setCaret(nextCaret);
    });
  };

  const insertRef = (ref: string, fromChip = false) => {
    const el = inputRef.current;
    const focused = document.activeElement === el;
    if (fromChip && !focused) {
      const prefix = expression && !expression.endsWith(" ") ? " " : "";
      const next = `${expression}${prefix}${ref}`;
      applyInsert(next, next.length);
      return;
    }
    const at = el?.selectionStart ?? caret;
    const { next, caret: nextCaret } = insertFormulaRef(expression, at, ref);
    applyInsert(next, nextCaret);
  };

  const syncCaret = (el: { selectionStart: number | null; value: string } | null) => {
    if (el && "selectionStart" in el) setCaret(el.selectionStart ?? el.value.length);
  };

  const onFormulaKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape" && suggestOpen) {
      e.preventDefault();
      setSuggestOpen(false);
      return;
    }
    if (!showSuggest) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((i) => (i + 1) % suggestions.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((i) => (i - 1 + suggestions.length) % suggestions.length);
    } else if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault();
      const pick = suggestions[highlight];
      if (pick) insertRef(pick.ref);
    }
  };

  return (
    <Box>
      <ClickAwayListener
        onClickAway={(e) => {
          const t = e.target as Node | null;
          if (t && document.getElementById("formula-field-suggestions")?.contains(t)) return;
          setSuggestOpen(false);
        }}
      >
        <Box>
          <TextField
            fullWidth
            size="small"
            label="Formula"
            value={expression}
            inputRef={inputRef}
            placeholder="Type a field name — e.g. basic"
            autoComplete="off"
            spellCheck={false}
            onChange={(e) => {
              onExpressionChange(e.target.value);
              syncCaret(inputRef.current);
              setSuggestOpen(true);
            }}
            onFocus={() => { syncCaret(inputRef.current); setSuggestOpen(true); }}
            onClick={() => syncCaret(inputRef.current)}
            onKeyUp={() => syncCaret(inputRef.current)}
            onSelect={() => syncCaret(inputRef.current)}
            onKeyDown={onFormulaKeyDown}
            slotProps={{
              htmlInput: {
                "aria-autocomplete": "list",
                "aria-expanded": suggestOpen && token.text.length > 0,
                "aria-controls": suggestOpen && token.text.length > 0 ? "formula-field-suggestions" : undefined,
                role: "combobox",
              },
            }}
          />
          <Popper
            open={suggestOpen && token.text.length > 0}
            anchorEl={inputRef.current}
            placement="bottom-start"
            style={{ zIndex: 1400, width: inputRef.current?.offsetWidth }}
          >
            <Paper
              id="formula-field-suggestions"
              role="listbox"
              elevation={8}
              sx={{ mt: 0.5, maxHeight: 240, overflow: "auto", borderRadius: 2 }}
            >
              {suggestions.length === 0 ? (
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", px: 1.5, py: 1.25 }}>
                  No fields match “{token.text}”.
                </Typography>
              ) : (
                <List dense disablePadding>
                  {suggestions.map((f, i) => (
                    <ListItemButton
                      key={f.ref}
                      role="option"
                      aria-selected={i === highlight}
                      selected={i === highlight}
                      onMouseDown={(e) => e.preventDefault()}
                      onMouseEnter={() => setHighlight(i)}
                      onClick={() => insertRef(f.ref)}
                      sx={{ py: 0.75, px: 1.5 }}
                    >
                      <ListItemText
                        primary={f.label}
                        secondary={f.ref}
                        primaryTypographyProps={{ variant: "body2", color: "text.primary" }}
                        secondaryTypographyProps={{ variant: "caption" }}
                      />
                    </ListItemButton>
                  ))}
                </List>
              )}
            </Paper>
          </Popper>
        </Box>
      </ClickAwayListener>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.75 }}>
        Use field refs with + − × ÷, e.g. <code>payroll.gross - payroll.deductions</code>. Type to search, or click a field:
      </Typography>
      <TextField
        fullWidth
        size="small"
        placeholder="Search fields…"
        value={chipQuery}
        onChange={(e) => setChipQuery(e.target.value)}
        sx={{ mt: 1 }}
        slotProps={{
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchOutlined sx={{ fontSize: 18, color: "text.secondary" }} aria-hidden />
              </InputAdornment>
            ),
          },
        }}
      />
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mt: 1, maxHeight: 120, overflowY: "auto" }}>
        {chips.length === 0 ? (
          <Typography variant="caption" color="text.secondary" sx={{ py: 1 }}>
            No fields match “{chipQuery.trim()}”.
          </Typography>
        ) : chips.map((f) => (
          <Chip key={f.ref} size="small" label={f.label} onClick={() => insertRef(f.ref, true)} />
        ))}
      </Box>
    </Box>
  );
}

export function CustomColumnDialog({
  open,
  onClose,
  initialLabel,
  initialCalc,
}: {
  open: boolean;
  onClose: () => void;
  initialLabel?: string;
  initialCalc?: CalculatedField | null;
}) {
  const { data: fields = [] } = useQuery({ queryKey: ["fields"], queryFn: semanticApi.fields });
  const { addCalculatedField, addField, removeField } = useBuilderStore();
  const [tab, setTab] = useState(0);
  const [label, setLabel] = useState("");
  const [expression, setExpression] = useState("");
  const [testRef, setTestRef] = useState("");
  const [cases, setCases] = useState<CalcCase[]>([{ ref: "", op: "lt", value: "", label: "" }]);
  const [elseLabel, setElseLabel] = useState("");
  // Lookup tab (value -> label mapping table)
  const [lookupOn, setLookupOn] = useState("");
  const [lookupRows, setLookupRows] = useState<{ k: string; v: string }[]>([{ k: "", v: "" }]);
  const [lookupDefault, setLookupDefault] = useState("");
  // JSON tab (paste/edit a governed logic sub-spec directly)
  const [jsonText, setJsonText] = useState("");
  const [jsonError, setJsonError] = useState("");
  // AI tab
  const [aiText, setAiText] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiResult, setAiResult] = useState<CalculatedField | null>(null);
  const [editingName, setEditingName] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    if (initialCalc) {
      setEditingName(initialCalc.name);
      setLabel(initialCalc.label);
      if (initialCalc.expression) {
        setTab(0);
        setExpression(initialCalc.expression);
        setTestRef("");
        setCases([{ ref: "", op: "lt", value: "", label: "" }]);
        setElseLabel("");
        setLookupOn("");
        setLookupRows([{ k: "", v: "" }]);
        setLookupDefault("");
      } else if (initialCalc.cases?.length) {
        setTab(1);
        setExpression("");
        setTestRef(initialCalc.cases[0].ref);
        setCases(initialCalc.cases.map((c) => ({ ...c, value: c.value ?? "" })));
        setElseLabel(initialCalc.else_label ?? "");
        setLookupOn("");
        setLookupRows([{ k: "", v: "" }]);
        setLookupDefault("");
      } else if (initialCalc.lookup) {
        setTab(2);
        setExpression("");
        setTestRef("");
        setCases([{ ref: "", op: "lt", value: "", label: "" }]);
        setElseLabel("");
        setLookupOn(initialCalc.lookup.on);
        const rows = Object.entries(initialCalc.lookup.map).map(([k, v]) => ({ k, v }));
        setLookupRows(rows.length ? rows : [{ k: "", v: "" }]);
        setLookupDefault(initialCalc.lookup.default ?? "");
      }
      setJsonText("");
      setJsonError("");
      setAiText("");
      setAiResult(null);
      setAiError("");
      return;
    }
    setEditingName(null);
    if (initialLabel) {
      setLabel(initialLabel);
      setTab(3);
    }
  }, [open, initialCalc, initialLabel]);

  const reset = () => {
    setLabel(""); setExpression(""); setTestRef("");
    setCases([{ ref: "", op: "lt", value: "", label: "" }]);
    setElseLabel("");
    setLookupOn(""); setLookupRows([{ k: "", v: "" }]); setLookupDefault("");
    setJsonText(""); setJsonError("");
    setAiText(""); setAiResult(null); setAiError("");
    setEditingName(null); setTab(0);
  };
  const close = () => { reset(); onClose(); };

  const generate = async () => {
    setAiBusy(true); setAiError(""); setAiResult(null);
    try {
      setAiResult(await aiApi.deriveField(aiText, label || undefined));
    } catch (e: unknown) {
      setAiError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "AI couldn’t build that — try rephrasing.");
    } finally { setAiBusy(false); }
  };

  const save = () => {
    if (tab === 4) {  // JSON — paste/edit a governed logic sub-spec directly
      try {
        const parsed = JSON.parse(jsonText);
        if (!parsed || typeof parsed !== "object" || !parsed.name || !parsed.label) {
          throw new Error("JSON must have at least a \"name\" and \"label\".");
        }
        addCalculatedField(parsed as CalculatedField);  // server validates the governed shape
      } catch (e) { setJsonError((e as Error).message || "Invalid JSON"); return; }
      close(); return;
    }
    const name = editingName ?? slug(label);
    if (tab === 0) {
      addCalculatedField({ name, label, expression });
    } else if (tab === 1) {
      const built = cases.filter((c) => c.label).map((c) => ({ ...c, ref: testRef, value: isNaN(Number(c.value)) ? c.value : Number(c.value) }));
      if (built.length === 0 && editingName) {
        // Cleared all rules — drop the calculated column and show the raw field again.
        removeField(`calc.${editingName}`);
        if (testRef && !useBuilderStore.getState().dataSpec.fields.some((f) => f.ref === testRef)) {
          addField({ ref: testRef, label });
        }
        close();
        return;
      }
      addCalculatedField({ name, label, cases: built, else_label: elseLabel || null });
    } else if (tab === 2) {
      const map: Record<string, string> = {};
      lookupRows.filter((r) => r.k && r.v).forEach((r) => { map[r.k] = r.v; });
      addCalculatedField({ name, label, lookup: { on: lookupOn, map, default: lookupDefault || null } });
    } else if (tab === 3 && aiResult) {
      addCalculatedField({ ...aiResult, label: label || aiResult.label, name: editingName ?? slug(label || aiResult.label) });
    }
    close();
  };

  const removingBanding = tab === 1 && Boolean(editingName) && !cases.some((c) => c.label);
  const valid = tab === 0 ? Boolean(label && expression)
    : tab === 1 ? Boolean(label && testRef && (cases.some((c) => c.label) || removingBanding))
    : tab === 2 ? Boolean(label && lookupOn && lookupRows.some((r) => r.k && r.v))
    : tab === 3 ? Boolean(aiResult)
    : Boolean(jsonText.trim());

  return (
    <Dialog open={open} onClose={close} maxWidth="sm" fullWidth>
      <DialogTitle>{editingName ? "Edit custom column" : "Add a custom column"}</DialogTitle>
      <DialogContent>
        <TextField fullWidth size="small" label="Column name (heading)" value={label}
          onChange={(e) => setLabel(e.target.value)} sx={{ mt: 1, mb: 2 }} placeholder="e.g. Take Home, Age Group" />

        <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto" sx={{ mb: 2 }}>
          <Tab label="Formula" sx={{ textTransform: "none" }} />
          <Tab label="Banding / labels" sx={{ textTransform: "none" }} />
          <Tab label="Lookup / mapping" sx={{ textTransform: "none" }} />
          <Tab icon={<AutoAwesome fontSize="small" />} iconPosition="start" label="Describe with AI" sx={{ textTransform: "none", minHeight: 40 }} />
          <Tab icon={<DataObjectOutlined fontSize="small" />} iconPosition="start" label="JSON" sx={{ textTransform: "none", minHeight: 40 }} />
        </Tabs>

        {tab === 0 && (
          <FormulaFieldInput
            expression={expression}
            onExpressionChange={setExpression}
            fields={fields as SemanticFieldMeta[]}
            active={open}
          />
        )}

        {tab === 1 && (
          <Box>
            <Autocomplete
              size="small" fullWidth sx={{ mb: 1.5 }} options={fields as SemanticFieldMeta[]}
              groupBy={(o) => o.entity} getOptionLabel={(o) => o.label} filterOptions={fieldFilter}
              isOptionEqualToValue={(o, v) => o.ref === v.ref}
              value={(fields as SemanticFieldMeta[]).find((f) => f.ref === testRef) ?? null}
              onChange={(_, v) => setTestRef(v?.ref ?? "")}
              renderOption={(props, o) => (
                <li {...props} key={o.ref}>
                  <Box><Typography variant="body2">{o.label}</Typography>
                    <Typography variant="caption" color="text.secondary">{o.ref}</Typography></Box>
                </li>
              )}
              renderInput={(p) => <TextField {...p} label="Based on field" placeholder="Search a field…" />}
            />
            <Typography variant="caption" color="text.secondary">
              When the value matches, show the label (first match wins). Click <b>×</b> on a row to remove that rule.
            </Typography>
            <Stack spacing={1} mt={1}>
              {cases.map((c, i) => (
                <Stack key={i} direction="row" spacing={1} alignItems="center">
                  <TextField select size="small" value={c.op} onChange={(e) => setCases((cs) => cs.map((x, j) => j === i ? { ...x, op: e.target.value as FilterOp } : x))} sx={{ minWidth: 130 }}>
                    {OPS.map((op) => <MenuItem key={op.v} value={op.v}>{op.label}</MenuItem>)}
                  </TextField>
                  <TextField size="small" placeholder="value" value={String(c.value ?? "")} onChange={(e) => setCases((cs) => cs.map((x, j) => j === i ? { ...x, value: e.target.value } : x))} sx={{ width: 90 }} />
                  <Typography variant="body2">→</Typography>
                  <TextField size="small" placeholder="label" value={c.label} onChange={(e) => setCases((cs) => cs.map((x, j) => j === i ? { ...x, label: e.target.value } : x))} sx={{ flex: 1, minWidth: 0 }} />
                  <Tooltip title="Remove rule">
                    <IconButton
                      size="small"
                      aria-label="Remove rule"
                      onClick={() => setCases((cs) => cs.filter((_, j) => j !== i))}
                      sx={{ color: "text.secondary", "&:hover": { color: "error.main" } }}
                    >
                      <Close fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Stack>
              ))}
              <Stack direction="row" spacing={1} alignItems="center">
                <Button size="small" startIcon={<Add />} onClick={() => setCases((cs) => [...cs, { ref: "", op: "lt", value: "", label: "" }])}>
                  Add rule
                </Button>
                {cases.length > 0 && (
                  <Button size="small" color="inherit" onClick={() => setCases([])}>
                    Clear all rules
                  </Button>
                )}
              </Stack>
              <TextField size="small" label="Otherwise (else label)" value={elseLabel} onChange={(e) => setElseLabel(e.target.value)} placeholder="e.g. 30+" />
              {removingBanding && (
                <Alert severity="info" sx={{ mt: 0.5 }}>
                  No rules left — click <b>Remove banding</b> to show the raw field value instead.
                </Alert>
              )}
            </Stack>
          </Box>
        )}

        {tab === 2 && (
          <Box>
            <Autocomplete
              size="small" fullWidth sx={{ mb: 1.5 }} options={fields as SemanticFieldMeta[]}
              groupBy={(o) => o.entity} getOptionLabel={(o) => o.label} filterOptions={fieldFilter}
              isOptionEqualToValue={(o, v) => o.ref === v.ref}
              value={(fields as SemanticFieldMeta[]).find((f) => f.ref === lookupOn) ?? null}
              onChange={(_, v) => setLookupOn(v?.ref ?? "")}
              renderOption={(props, o) => (
                <li {...props} key={o.ref}>
                  <Box><Typography variant="body2">{o.label}</Typography>
                    <Typography variant="caption" color="text.secondary">{o.ref}</Typography></Box>
                </li>
              )}
              renderInput={(p) => <TextField {...p} label="Map the values of" placeholder="Search a field…" />}
            />
            <Typography variant="caption" color="text.secondary">Translate each source value to a label:</Typography>
            <Stack spacing={1} mt={1}>
              {lookupRows.map((r, i) => (
                <Stack key={i} direction="row" spacing={1} alignItems="center">
                  <TextField size="small" placeholder="source value" value={r.k}
                    onChange={(e) => setLookupRows((rs) => rs.map((x, j) => j === i ? { ...x, k: e.target.value } : x))} />
                  <Typography variant="body2">→</Typography>
                  <TextField size="small" placeholder="label" value={r.v}
                    onChange={(e) => setLookupRows((rs) => rs.map((x, j) => j === i ? { ...x, v: e.target.value } : x))} />
                  <IconButton size="small" onClick={() => setLookupRows((rs) => rs.filter((_, j) => j !== i))}><Close fontSize="small" /></IconButton>
                </Stack>
              ))}
              <Button size="small" startIcon={<Add />} onClick={() => setLookupRows((rs) => [...rs, { k: "", v: "" }])}>Add mapping</Button>
              <TextField size="small" label="Otherwise (default label)" value={lookupDefault}
                onChange={(e) => setLookupDefault(e.target.value)} placeholder="e.g. Other" />
            </Stack>
          </Box>
        )}

        {tab === 3 && (
          <Box>
            <Typography variant="body2" sx={{ mb: 1 }}>
              Describe the column in plain words (or paste a rough formula). The AI turns it into a
              safe formula/banding — it never writes SQL and never sees employee data.
            </Typography>
            <TextField fullWidth multiline minRows={2} size="small" value={aiText}
              onChange={(e) => setAiText(e.target.value)}
              placeholder='e.g. "take home = net salary minus loan deductions" or "age under 20 → Junior, under 40 → Mid, else Senior"' />
            <Button sx={{ mt: 1 }} variant="outlined" startIcon={<AutoAwesome />} onClick={generate}
              disabled={aiBusy || !aiText.trim()}>
              {aiBusy ? "Thinking…" : "Generate"}
            </Button>
            {aiError && <Alert severity="error" sx={{ mt: 1.5 }}>{aiError}</Alert>}
            {aiResult && (
              <Alert severity="success" sx={{ mt: 1.5 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>{aiResult.label}</Typography>
                {aiResult.expression
                  ? <Typography variant="caption">Formula: <code>{aiResult.expression}</code></Typography>
                  : <Box>{(aiResult.cases ?? []).map((c, i) => (
                      <Typography key={i} variant="caption" sx={{ display: "block" }}>
                        {c.ref} {opLabel(c.op)} {String(c.value)} → “{c.label}”
                      </Typography>
                    ))}
                    {aiResult.else_label && <Typography variant="caption">otherwise → “{aiResult.else_label}”</Typography>}
                  </Box>}
              </Alert>
            )}
          </Box>
        )}

        {tab === 4 && (
          <Box>
            <Typography variant="body2" sx={{ mb: 1 }}>
              Paste a field-logic sub-spec as JSON — it’s injected into the report’s
              <code> calculated_fields</code>. Governed shapes only (validated server-side): a
              <b> formula</b>, a <b>banding</b> (cases), or a <b>lookup</b> map. No raw SQL.
            </Typography>
            <TextField fullWidth multiline minRows={8} size="small" value={jsonText}
              onChange={(e) => { setJsonText(e.target.value); setJsonError(""); }}
              slotProps={{ input: { sx: { fontFamily: "ui-monospace, monospace", fontSize: "0.8rem" } } }}
              placeholder={`{
  "name": "grade_band",
  "label": "Grade Band",
  "lookup": {
    "on": "employee.grade",
    "map": { "A": "Senior", "B": "Mid" },
    "default": "Other"
  }
}`} />
            <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
              <Button size="small" variant="text" onClick={() => setJsonText(JSON.stringify(
                { name: "take_home", label: "Take Home", expression: "payroll.net - payroll.loan_deduction" }, null, 2))}>
                Formula example
              </Button>
              <Button size="small" variant="text" onClick={() => setJsonText(JSON.stringify(
                { name: "grade_band", label: "Grade Band", lookup: { on: "employee.grade", map: { A: "Senior", B: "Mid" }, default: "Other" } }, null, 2))}>
                Lookup example
              </Button>
            </Stack>
            {jsonError && <Alert severity="error" sx={{ mt: 1.5 }}>{jsonError}</Alert>}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={close}>Cancel</Button>
        <Button variant="contained" onClick={save} disabled={!valid}
          color={removingBanding ? "warning" : "primary"}>
          {removingBanding ? "Remove banding" : editingName ? "Save changes" : "Add column"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
