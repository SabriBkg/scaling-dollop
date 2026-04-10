import { create } from "zustand";

interface UIState {
  // Subscriber detail sheet
  activeSubscriberId: string | null;
  setActiveSubscriberId: (id: string | null) => void;

  // Batch selection for Supervised mode (FR14, UX-DR8)
  batchSelection: Set<string>;
  addToBatch: (id: string) => void;
  removeFromBatch: (id: string) => void;
  clearBatch: () => void;

  // Theme
  themePreference: "light" | "dark" | "system";
  setThemePreference: (theme: "light" | "dark" | "system") => void;
}

export const useUIStore = create<UIState>((set) => ({
  activeSubscriberId: null,
  setActiveSubscriberId: (id) => set({ activeSubscriberId: id }),

  batchSelection: new Set(),
  addToBatch: (id) =>
    set((state) => ({
      batchSelection: new Set([...state.batchSelection, id]),
    })),
  removeFromBatch: (id) =>
    set((state) => {
      const next = new Set(state.batchSelection);
      next.delete(id);
      return { batchSelection: next };
    }),
  clearBatch: () => set({ batchSelection: new Set() }),

  themePreference: "system",
  setThemePreference: (theme) => set({ themePreference: theme }),
}));
