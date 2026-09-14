// Builder working-state (Zustand) — the in-progress report during authoring.
// Both AI input modes (chat, Excel) and manual edits mutate THIS single spec,
// so they converge on one report definition (FR-A7).
import { create } from "zustand";
import {
  type DataSpec, type PresentationSpec, emptyDataSpec, emptyPresentation,
  type FieldSelection, type FilterClause, type CalculatedField, type UnpivotSpec, type SortSpec,
} from "../types/spec";

export const REPORT_MODULES = ["Payroll", "Leave", "Attendance", "Employee", "Workforce", "General"] as const;

interface BuilderState {
  templateId: string | null;
  dataSpec: DataSpec;
  presentation: PresentationSpec;
  module: string;
  setModule: (m: string) => void;
  description: string;
  setDescription: (d: string) => void;
  setTemplateId: (id: string) => void;
  // The uploaded Excel, held so the save flow can persist it (encrypted) with the
  // template. Cleared after a successful upload / on reset.
  sourceFile: File | null;
  setSourceFile: (f: File | null) => void;
  setDataSpec: (spec: DataSpec) => void;
  setPresentation: (p: PresentationSpec) => void;
  addField: (f: FieldSelection) => void;
  removeField: (ref: string) => void;
  reorderFields: (refs: string[]) => void;
  setFilters: (filters: FilterClause[]) => void;
  setRuntimeParams: (params: DataSpec["runtime_params"]) => void;
  setSort: (sort: SortSpec[]) => void;
  setUnpivot: (u: UnpivotSpec | null) => void;
  addCalculatedField: (calc: CalculatedField) => void;
  setFieldLabel: (ref: string, label: string) => void;
  setFieldTotal: (ref: string, total: boolean) => void;
  updatePresentation: (patch: Partial<PresentationSpec>) => void;
  updateBranding: (patch: Partial<PresentationSpec["branding"]>) => void;
  updatePage: (patch: Partial<PresentationSpec["page"]>) => void;
  reset: () => void;
}

export const useBuilderStore = create<BuilderState>((set) => ({
  templateId: null,
  dataSpec: emptyDataSpec(),
  presentation: emptyPresentation(),
  module: "General",
  setModule: (m) => set({ module: m }),
  description: "",
  setDescription: (d) => set({ description: d }),
  setTemplateId: (id) => set({ templateId: id }),
  sourceFile: null,
  setSourceFile: (f) => set({ sourceFile: f }),
  setDataSpec: (spec) => set({ dataSpec: spec }),
  setPresentation: (p) => set({ presentation: p }),
  setUnpivot: (u) => set((s) => ({ dataSpec: { ...s.dataSpec, unpivot: u } })),
  addField: (f) =>
    set((s) =>
      s.dataSpec.fields.some((x) => x.ref === f.ref)
        ? s
        : { dataSpec: { ...s.dataSpec, fields: [...s.dataSpec.fields, f] } },
    ),
  removeField: (ref) =>
    set((s) => ({
      dataSpec: {
        ...s.dataSpec,
        fields: s.dataSpec.fields.filter((f) => f.ref !== ref),
        calculated_fields: ref.startsWith("calc.")
          ? s.dataSpec.calculated_fields.filter((c) => `calc.${c.name}` !== ref)
          : s.dataSpec.calculated_fields,
      },
    })),
  reorderFields: (refs) =>
    set((s) => ({
      dataSpec: {
        ...s.dataSpec,
        fields: refs
          .map((r) => s.dataSpec.fields.find((f) => f.ref === r))
          .filter((f): f is FieldSelection => Boolean(f)),
      },
    })),
  setFilters: (filters) => set((s) => ({ dataSpec: { ...s.dataSpec, filters } })),
  setRuntimeParams: (runtime_params) => set((s) => ({ dataSpec: { ...s.dataSpec, runtime_params } })),
  setSort: (sort) => set((s) => ({ dataSpec: { ...s.dataSpec, sort } })),
  // Adds the derived field AND a column referencing it (calc.<name>).
  addCalculatedField: (calc) =>
    set((s) => {
      const ref = `calc.${calc.name}`;
      const calcs = s.dataSpec.calculated_fields.filter((c) => c.name !== calc.name);
      const fields = s.dataSpec.fields.some((f) => f.ref === ref)
        ? s.dataSpec.fields.map((f) => (f.ref === ref ? { ...f, label: calc.label } : f))
        : [...s.dataSpec.fields, { ref, label: calc.label }];
      return { dataSpec: { ...s.dataSpec, calculated_fields: [...calcs, calc], fields } };
    }),
  setFieldLabel: (ref, label) =>
    set((s) => ({
      dataSpec: { ...s.dataSpec, fields: s.dataSpec.fields.map((f) => (f.ref === ref ? { ...f, label } : f)) },
    })),
  setFieldTotal: (ref, total) =>
    set((s) => ({
      dataSpec: { ...s.dataSpec, fields: s.dataSpec.fields.map((f) => (f.ref === ref ? { ...f, total } : f)) },
    })),
  updatePresentation: (patch) => set((s) => ({ presentation: { ...s.presentation, ...patch } })),
  updateBranding: (patch) =>
    set((s) => ({ presentation: { ...s.presentation, branding: { ...s.presentation.branding, ...patch } } })),
  updatePage: (patch) =>
    set((s) => ({ presentation: { ...s.presentation, page: { ...s.presentation.page, ...patch } } })),
  reset: () => set({ dataSpec: emptyDataSpec(), presentation: emptyPresentation(), templateId: null, module: "General", description: "", sourceFile: null }),
}));
