"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  BookMarked,
  Download,
  FileText,
  FolderOpen,
  Search,
  Sparkles,
  StickyNote,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Bookmark, HistoryEntry, Note, NoteListItem, Page, Workspace } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardContent, CardHeader, CardTitle, Spinner } from "@/components/ui/card";

interface Overview {
  workspace: Workspace;
  bookmark_count: number;
  note_count: number;
  search_count: number;
  recent_searches: HistoryEntry[];
}

export default function WorkspaceDetailPage() {
  return (
    <AppShell>
      <WorkspaceDetail />
    </AppShell>
  );
}

function WorkspaceDetail() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = params.id;
  const [digest, setDigest] = useState<string | null>(null);
  const [digestBusy, setDigestBusy] = useState(false);

  const { data: overview, isLoading } = useQuery({
    queryKey: ["workspace", id],
    queryFn: () => api.get<Overview>(`/api/v1/workspaces/${id}/overview`),
  });

  const { data: bookmarks } = useQuery({
    queryKey: ["bookmarks", { workspace: id }],
    queryFn: () => api.get<Page<Bookmark>>(`/api/v1/bookmarks?workspace_id=${id}&size=10`),
  });

  const { data: notes } = useQuery({
    queryKey: ["notes", { workspace: id }],
    queryFn: () => api.get<Page<NoteListItem>>(`/api/v1/notes?workspace_id=${id}&size=10`),
  });

  const { data: aiStatus } = useQuery({
    queryKey: ["ai-status"],
    queryFn: () => api.get<{ enabled: boolean }>("/api/v1/ai/status"),
    staleTime: 300_000,
  });

  const archiveMutation = useMutation({
    mutationFn: () =>
      api.patch(`/api/v1/workspaces/${id}`, {
        status: overview?.workspace.status === "archived" ? "active" : "archived",
      }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["workspace", id] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/api/v1/workspaces/${id}`),
    onSuccess: () => router.push("/workspaces"),
  });

  async function generateDigest() {
    setDigestBusy(true);
    try {
      const response = await api.post<{ text: string }>(`/api/v1/ai/workspaces/${id}/digest`);
      setDigest(response.text);
    } catch (err) {
      setDigest(err instanceof Error ? `Digest unavailable: ${err.message}` : "Unavailable.");
    } finally {
      setDigestBusy(false);
    }
  }

  if (isLoading || !overview) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  const { workspace } = overview;

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <FolderOpen className="h-5 w-5 text-accent" />
            {workspace.name}
            {workspace.status === "archived" && <Badge>archived</Badge>}
          </h1>
          {workspace.description && (
            <p className="mt-1 max-w-xl text-sm text-muted">{workspace.description}</p>
          )}
          <p className="mt-2 text-xs text-muted">
            {overview.search_count} searches · {overview.bookmark_count} bookmarks ·{" "}
            {overview.note_count} notes
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href={`/search?mode=research&workspace_id=${id}`}>
            <Button variant="primary" size="sm">
              <Search className="h-4 w-4" /> Research
            </Button>
          </Link>
          {aiStatus?.enabled && (
            <Button variant="secondary" size="sm" onClick={() => void generateDigest()} disabled={digestBusy}>
              <Sparkles className="h-4 w-4" /> {digestBusy ? "Working…" : "AI digest"}
            </Button>
          )}
          <a href={`/api/v1/workspaces/${id}/export.zip`} download>
            <Button variant="outline" size="sm">
              <Download className="h-4 w-4" /> Export
            </Button>
          </a>
          <Button variant="outline" size="sm" onClick={() => archiveMutation.mutate()}>
            <Archive className="h-4 w-4" />
            {workspace.status === "archived" ? "Unarchive" : "Archive"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (confirm("Delete this workspace? Bookmarks and notes will be kept, unfiled.")) {
                deleteMutation.mutate();
              }
            }}
          >
            <Trash2 className="h-4 w-4 text-danger" />
          </Button>
        </div>
      </div>

      {digest && (
        <Card className="mb-6 border-accent/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5 text-accent">
              <Sparkles className="h-4 w-4" /> Research digest
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="whitespace-pre-wrap text-sm leading-relaxed">{digest}</div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <Search className="h-4 w-4 text-muted" /> Recent searches
            </CardTitle>
          </CardHeader>
          <CardContent>
            {overview.recent_searches.length === 0 ? (
              <p className="text-xs text-muted">
                Searches made in research mode with this workspace will appear here.
              </p>
            ) : (
              <ul className="space-y-1">
                {overview.recent_searches.map((entry) => (
                  <li key={entry.id}>
                    <Link
                      href={`/search?q=${encodeURIComponent(entry.query)}&mode=research&workspace_id=${id}`}
                      className="flex items-center justify-between rounded px-2 py-1.5 text-sm hover:bg-surface-2"
                    >
                      <span className="truncate">{entry.query}</span>
                      <span className="ml-2 shrink-0 text-xs text-muted">
                        {timeAgo(entry.created_at)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <BookMarked className="h-4 w-4 text-muted" /> Saved sources
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!bookmarks || bookmarks.items.length === 0 ? (
              <p className="text-xs text-muted">Save search results into this workspace.</p>
            ) : (
              <ul className="space-y-1.5">
                {bookmarks.items.map((bookmark) => (
                  <li key={bookmark.id} className="truncate text-sm">
                    <a
                      href={bookmark.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent hover:underline"
                    >
                      {bookmark.title || bookmark.url}
                    </a>
                    <span className="ml-2 text-xs text-muted">{bookmark.domain}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <StickyNote className="h-4 w-4 text-muted" /> Notes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {notes?.items.map((note) => (
                <Link key={note.id} href={`/notes/${note.id}`}>
                  <span className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-surface-2">
                    <FileText className="h-3.5 w-3.5 text-muted" />
                    {note.title}
                  </span>
                </Link>
              ))}
              <Link href={`/notes/new?workspace_id=${id}`}>
                <span className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-border px-3 py-1.5 text-sm text-muted hover:bg-surface-2">
                  + New note
                </span>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
