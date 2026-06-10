"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pin, Plus, Search, StickyNote } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, qs } from "@/lib/api";
import type { NoteListItem, Page } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Badge, EmptyState, Spinner } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function NotesPage() {
  return (
    <AppShell>
      <NotesContent />
    </AppShell>
  );
}

function NotesContent() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["notes", { query, page }],
    queryFn: () =>
      api.get<Page<NoteListItem>>(
        `/api/v1/notes${qs({ q: query || undefined, page, size: 30 })}`,
      ),
  });

  const createMutation = useMutation({
    mutationFn: () => api.post<{ id: string }>("/api/v1/notes", { title: "", content: "" }),
    onSuccess: (note) => router.push(`/notes/${note.id}`),
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.size)) : 1;

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Notes</h1>
          <p className="text-sm text-muted">Markdown notes with revision history.</p>
        </div>
        <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
          <Plus className="h-4 w-4" /> New note
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
          placeholder="Search notes…"
          className="pl-9"
        />
      </div>

      {isLoading && (
        <div className="flex justify-center py-10">
          <Spinner className="h-6 w-6" />
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState
          icon={<StickyNote className="h-8 w-8" />}
          title="No notes"
          description="Capture findings while you research. Notes support Markdown and link to bookmarks."
        />
      )}

      <ul className="space-y-2">
        {data?.items.map((note) => (
          <li key={note.id}>
            <Link
              href={`/notes/${note.id}`}
              className="flex items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3 hover:border-accent/40"
            >
              {note.is_pinned && <Pin className="h-3.5 w-3.5 shrink-0 text-accent" />}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{note.title}</p>
                <p className="text-xs text-muted">Updated {timeAgo(note.updated_at)}</p>
              </div>
              <div className="flex gap-1">
                {note.tags.slice(0, 3).map((tag) => (
                  <Badge key={tag.id}>{tag.name}</Badge>
                ))}
              </div>
            </Link>
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
