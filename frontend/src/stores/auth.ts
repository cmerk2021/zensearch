"use client";

import { create } from "zustand";
import { api } from "@/lib/api";
import type { Preferences, User } from "@/lib/types";

interface AuthState {
  user: User | null;
  preferences: Preferences | null;
  loaded: boolean;
  load: () => Promise<void>;
  login: (username: string, password: string, method?: "local" | "ldap") => Promise<void>;
  logout: () => Promise<void>;
  setPreferences: (prefs: Partial<Preferences>) => Promise<void>;
}

export const useAuth = create<AuthState>((set, get) => ({
  user: null,
  preferences: null,
  loaded: false,

  load: async () => {
    try {
      const user = await api.get<User>("/api/v1/me");
      const preferences = await api.get<Preferences>("/api/v1/me/preferences");
      set({ user, preferences, loaded: true });
    } catch {
      set({ user: null, preferences: null, loaded: true });
    }
  },

  login: async (username, password, method = "local") => {
    await api.post("/api/v1/auth/login", { username, password, method });
    await get().load();
  },

  logout: async () => {
    try {
      await api.post("/api/v1/auth/logout");
    } finally {
      set({ user: null, preferences: null });
    }
  },

  setPreferences: async (prefs) => {
    const preferences = await api.patch<Preferences>("/api/v1/me/preferences", prefs);
    set({ preferences });
    applyTheme(preferences.theme);
  },
}));

export function applyTheme(theme: string) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.classList.remove("dark", "amoled");
  const prefersDark =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  if (theme === "dark" || (theme === "system" && prefersDark)) {
    root.classList.add("dark");
  } else if (theme === "amoled") {
    root.classList.add("dark", "amoled");
  }
}
