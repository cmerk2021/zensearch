"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import type { HistoryEntry, Page, Workspace } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { AppShell } from "@/components/app-shell";
import { SearchBox } from "@/components/search/search-box";
import { FolderOpen, History } from "lucide-react";

export default function HomePage() {
  return (
    <AppShell>
      <HomeContent />
    </AppShell>
  );
}

function HomeContent() {
  const user = useAuth((state) => state.user);

  const { data: workspaces } = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => api.get<Workspace[]>("/api/v1/workspaces"),
    enabled: !!user,
  });

  const { data: history } = useQuery({
    queryKey: ["history", "recent"],
    queryFn: () => api.get<Page<HistoryEntry>>("/api/v1/history?size=6"),
    enabled: !!user,
  });

  return (
    <div className="mx-auto flex min-h-[80vh] w-full max-w-2xl flex-col justify-center px-4 py-10">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-semibold tracking-tight">
          Search less. <span className="text-accent">Find more.</span>
        </h1>
      </div>

      <SearchBox autoFocus size="lg" />

      <div className="mt-10 grid gap-6 sm:grid-cols-2">
        {workspaces && workspaces.length > 0 && (
          <section>
            <h2 className="mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted">
              <FolderOpen className="h-3.5 w-3.5" /> Workspaces
            </h2>
            <ul className="space-y-1">
              {workspaces.slice(0, 5).map((workspace) => (
                <li key={workspace.id}>
                  <Link
                    href={`/workspaces/${workspace.id}`}
                    className="block truncate rounded-lg px-3 py-2 text-sm hover:bg-surface-2"
                  >
                    {workspace.name}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
        {history && history.items.length > 0 && (
          <section>
            <h2 className="mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted">
              <History className="h-3.5 w-3.5" /> Recent searches
            </h2>
            <ul className="space-y-1">
              {history.items.map((entry) => (
                <li key={entry.id}>
                  <Link
                    href={`/search?q=${encodeURIComponent(entry.query)}`}
                    className="flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm hover:bg-surface-2"
                  >
                    <span className="truncate">{entry.query}</span>
                    <span className="shrink-0 text-xs text-muted">
                      {timeAgo(entry.created_at)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
