"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History as HistoryIcon, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { api, qs } from "@/lib/api";
import type { HistoryEntry, Page } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Badge, EmptyState, Spinner } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function HistoryPage() {
  return (
    <AppShell>
      <HistoryContent />
    </AppShell>
  );
}

function HistoryContent() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["history", { query, page }],
    queryFn: () =>
      api.get<Page<HistoryEntry>>(
        `/api/v1/history${qs({ q: query || undefined, page, size: 40 })}`,
      ),
  });

  const clearMutation = useMutation({
    mutationFn: () => api.delete("/api/v1/history"),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["history"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/history/${id}`),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["history"] }),
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.size)) : 1;

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Search history</h1>
          <p className="text-sm text-muted">
            Searches made in privacy mode are never recorded.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            if (confirm("Clear your entire search history?")) clearMutation.mutate();
          }}
        >
          <Trash2 className="h-4 w-4" /> Clear all
        </Button>
      </div>

      <div className="relative mb-4">
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted" />
        <Input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setPage(1);
          }}
          placeholder="Filter history…"
          className="pl-9"
        />
      </div>

      {isLoading && (
        <div className="flex justify-center py-10">
          <Spinner className="h-6 w-6" />
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState icon={<HistoryIcon className="h-8 w-8" />} title="No history" />
      )}

      <ul className="space-y-1">
        {data?.items.map((entry) => (
          <li
            key={entry.id}
            className="group flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-surface-2"
          >
            <Link
              href={`/search?q=${encodeURIComponent(entry.query)}`}
              className="min-w-0 flex-1 truncate text-sm"
            >
              {entry.query}
            </Link>
            {entry.mode !== "normal" && <Badge variant="accent">{entry.mode}</Badge>}
            <span className="shrink-0 text-xs text-muted">{timeAgo(entry.created_at)}</span>
            <button
              onClick={() => deleteMutation.mutate(entry.id)}
              aria-label="Delete entry"
              className="rounded p-1 text-muted opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </li>
        ))}
      </ul>

      {totalPages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-3 text-sm">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Previous
          </Button>
          <span className="text-muted">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
