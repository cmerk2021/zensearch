"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { applyTheme, useAuth } from "@/stores/auth";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
        },
      }),
  );
  const load = useAuth((state) => state.load);
  const preferences = useAuth((state) => state.preferences);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (preferences?.theme) {
      localStorage.setItem("zen-theme", preferences.theme);
      applyTheme(preferences.theme);
    }
  }, [preferences?.theme]);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
