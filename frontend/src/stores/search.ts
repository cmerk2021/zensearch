"use client";

import { create } from "zustand";
import type { SearchMode } from "@/lib/types";

interface SearchUIState {
  mode: SearchMode;
  profileSlug: string | null;
  workspaceId: string | null;
  paletteOpen: boolean;
  setMode: (mode: SearchMode) => void;
  setProfile: (slug: string | null) => void;
  setWorkspace: (id: string | null) => void;
  setPaletteOpen: (open: boolean) => void;
}

export const useSearchUI = create<SearchUIState>((set) => ({
  mode: "normal",
  profileSlug: null,
  workspaceId: null,
  paletteOpen: false,
  setMode: (mode) => set({ mode }),
  setProfile: (profileSlug) => set({ profileSlug }),
  setWorkspace: (workspaceId) => set({ workspaceId }),
  setPaletteOpen: (paletteOpen) => set({ paletteOpen }),
}));
