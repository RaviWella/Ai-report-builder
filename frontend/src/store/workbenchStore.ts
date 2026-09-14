/**
 * MintHRM Workbench store — mirrors mint-analytics Zustand store pattern.
 * Manages canvas state, session, and narrative panel visibility.
 */
import { create } from "zustand";

export type PanelMode = "closed" | "narrative" | "history" | "trace";

export interface WorkbenchBlock {
  id: string;
  type: string;
  tool?: string;
  period?: string;
  metrics?: Record<string, number | null>;
  message?: string;
  timestamp: number;
}

interface WorkbenchState {
  // Canvas
  activeBlock: WorkbenchBlock | null;
  blockTrail: WorkbenchBlock[];

  // Narrative panel
  panelMode: PanelMode;

  // Session
  sessionId: string;
  tenantId: string;

  // Actions
  setActiveBlock: (block: WorkbenchBlock) => void;
  pushToTrail: (block: WorkbenchBlock) => void;
  setPanelMode: (mode: PanelMode) => void;
  resetSession: () => void;
}

export const useWorkbenchStore = create<WorkbenchState>((set, get) => ({
  activeBlock: null,
  blockTrail: [],
  panelMode: "closed",
  sessionId: crypto.randomUUID(),
  tenantId: "demo_tenant",

  setActiveBlock: (block) => {
    const current = get().activeBlock;
    if (current) {
      set((s) => ({ blockTrail: [...s.blockTrail.slice(-9), current] }));
    }
    set({ activeBlock: block });
  },

  pushToTrail: (block) =>
    set((s) => ({ blockTrail: [...s.blockTrail.slice(-9), block] })),

  setPanelMode: (mode) => set({ panelMode: mode }),

  resetSession: () =>
    set({
      activeBlock: null,
      blockTrail: [],
      panelMode: "closed",
      sessionId: crypto.randomUUID(),
    }),
}));
