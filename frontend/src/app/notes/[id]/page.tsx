"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, History, Pencil, Pin, Trash2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Note } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Markdown } from "@/components/ui/markdown";
import { RichEditor } from "@/components/ui/rich-editor";

interface Revision {
  id: string;
  title: string;
  created_at: string;
}

export default function NoteDetailPage() {
  return (
    <AppShell>
      <NoteEditor />
    </AppShell>
  );
}

function NoteEditor() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = params.id;

  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [showRevisions, setShowRevisions] = useState(false);

  const { data: note, isLoading } = useQuery({
    queryKey: ["note", id],
    queryFn: () => api.get<Note>(`/api/v1/notes/${id}`),
  });

  const { data: revisions } = useQuery({
    queryKey: ["note-revisions", id],
    queryFn: () => api.get<Revision[]>(`/api/v1/notes/${id}/revisions`),
    enabled: showRevisions,
  });

  useEffect(() => {
    if (note) {
      setTitle(note.title);
      setContent(note.content);
    }
  }, [note?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  function startEditing() {
    if (note) {
      setTitle(note.title);
      setContent(note.content);
    }
    setEditing(true);
  }

  async function save() {
    setSaving(true);
    try {
      await api.patch(`/api/v1/notes/${id}`, { title, content });
      setSavedAt(Date.now());
      await queryClient.invalidateQueries({ queryKey: ["note", id] });
      void queryClient.invalidateQueries({ queryKey: ["notes"] });
      void queryClient.invalidateQueries({ queryKey: ["note-revisions", id] });
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  const pinMutation = useMutation({
    mutationFn: () => api.patch(`/api/v1/notes/${id}`, { is_pinned: !note?.is_pinned }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["note", id] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/api/v1/notes/${id}`),
    onSuccess: () => router.push("/notes"),
  });

  const restoreMutation = useMutation({
    mutationFn: (revisionId: string) =>
      api.post<Note>(`/api/v1/notes/${id}/revisions/${revisionId}/restore`),
    onSuccess: (restored) => {
      setTitle(restored.title);
      setContent(restored.content);
      setShowRevisions(false);
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: ["note", id] });
    },
  });

  if (isLoading || !note) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-3.5rem)] w-full max-w-3xl flex-col px-4 py-6 md:h-screen">
      <div className="mb-3 flex items-center gap-2">
        {editing ? (
          <Input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Note title"
            className="border-none bg-transparent px-0 text-lg font-semibold shadow-none focus-visible:ring-0"
            aria-label="Note title"
          />
        ) : (
          <h1 className="min-w-0 flex-1 truncate text-lg font-semibold">
            {note.title || "Untitled note"}
          </h1>
        )}
        <span className="shrink-0 text-xs text-muted">
          {saving ? (
            "Saving…"
          ) : savedAt && !editing ? (
            <span className="inline-flex items-center gap-1 text-success">
              <Check className="h-3 w-3" /> Saved
            </span>
          ) : (
            `Updated ${timeAgo(note.updated_at)}`
          )}
        </span>
        {editing ? (
          <Button size="sm" onClick={() => void save()} disabled={saving}>
            <Check className="h-4 w-4" /> Save
          </Button>
        ) : (
          <Button size="sm" variant="secondary" onClick={startEditing}>
            <Pencil className="h-4 w-4" /> Edit
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          aria-label="Pin note"
          onClick={() => pinMutation.mutate()}
        >
          <Pin className={`h-4 w-4 ${note.is_pinned ? "text-accent" : ""}`} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Revision history"
          onClick={() => setShowRevisions(true)}
        >
          <History className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Delete note"
          onClick={() => {
            if (confirm("Delete this note?")) deleteMutation.mutate();
          }}
        >
          <Trash2 className="h-4 w-4 text-danger" />
        </Button>
      </div>

      {editing ? (
        <RichEditor content={content} onChange={setContent} className="flex-1 overflow-hidden" />
      ) : note.content.trim() ? (
        <div className="flex-1 overflow-y-auto pb-8">
          <Markdown content={note.content} />
        </div>
      ) : (
        <button
          onClick={startEditing}
          className="flex flex-1 items-start justify-start pt-2 text-left text-sm text-muted hover:text-foreground"
        >
          This note is empty. Click Edit to start writing…
        </button>
      )}

      <Dialog
        open={showRevisions}
        onClose={() => setShowRevisions(false)}
        title="Revision history"
      >
        {revisions && revisions.length === 0 && (
          <p className="text-sm text-muted">No previous revisions.</p>
        )}
        <ul className="max-h-80 space-y-1 overflow-y-auto">
          {revisions?.map((revision) => (
            <li
              key={revision.id}
              className="flex items-center justify-between gap-2 rounded-lg border border-border px-3 py-2"
            >
              <div className="min-w-0">
                <p className="truncate text-sm">{revision.title || "Untitled"}</p>
                <p className="text-xs text-muted">{timeAgo(revision.created_at)}</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => restoreMutation.mutate(revision.id)}
                disabled={restoreMutation.isPending}
              >
                Restore
              </Button>
            </li>
          ))}
        </ul>
      </Dialog>
    </div>
  );
}
