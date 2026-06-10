"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Tags as TagsIcon, Trash2 } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Tag } from "@/lib/types";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Badge, EmptyState } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Select } from "@/components/ui/input";

interface TagWithCounts {
  tag: Tag;
  bookmark_count: number;
  note_count: number;
}

export default function TagsPage() {
  return (
    <AppShell>
      <TagsContent />
    </AppShell>
  );
}

function TagsContent() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [parentId, setParentId] = useState("");

  const { data: tags } = useQuery({
    queryKey: ["tags"],
    queryFn: () => api.get<TagWithCounts[]>("/api/v1/tags"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post("/api/v1/tags", { name, parent_id: parentId || null }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tags"] });
      setShowCreate(false);
      setName("");
      setParentId("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/tags/${id}`),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["tags"] }),
  });

  // Build hierarchy for display.
  const roots = tags?.filter((entry) => !entry.tag.parent_id) ?? [];
  const childrenOf = (id: string) =>
    tags?.filter((entry) => entry.tag.parent_id === id) ?? [];

  function TagRow({ entry, depth }: { entry: TagWithCounts; depth: number }) {
    return (
      <>
        <li
          className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2"
          style={{ marginLeft: depth * 20 }}
        >
          <TagsIcon className="h-3.5 w-3.5 text-muted" />
          <span className="text-sm font-medium">{entry.tag.name}</span>
          <Badge>{entry.bookmark_count} bookmarks</Badge>
          <Badge>{entry.note_count} notes</Badge>
          <button
            onClick={() => deleteMutation.mutate(entry.tag.id)}
            aria-label={`Delete tag ${entry.tag.name}`}
            className="ml-auto rounded p-1 text-muted hover:bg-surface-2 hover:text-danger"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </li>
        {childrenOf(entry.tag.id).map((child) => (
          <TagRow key={child.tag.id} entry={child} depth={depth + 1} />
        ))}
      </>
    );
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Tags</h1>
          <p className="text-sm text-muted">Hierarchical labels shared by bookmarks and notes.</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" /> New tag
        </Button>
      </div>

      {tags && tags.length === 0 && (
        <EmptyState
          icon={<TagsIcon className="h-8 w-8" />}
          title="No tags"
          description="Tags organize knowledge across workspaces — e.g. linux/networking."
        />
      )}

      <ul className="space-y-1.5">
        {roots.map((entry) => (
          <TagRow key={entry.tag.id} entry={entry} depth={0} />
        ))}
      </ul>

      <Dialog open={showCreate} onClose={() => setShowCreate(false)} title="New tag">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            createMutation.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="tag-name">Name</Label>
            <Input
              id="tag-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoFocus
              required
            />
          </div>
          <div>
            <Label htmlFor="tag-parent">Parent (optional)</Label>
            <Select
              id="tag-parent"
              value={parentId}
              onChange={(event) => setParentId(event.target.value)}
            >
              <option value="">None (top level)</option>
              {tags?.map((entry) => (
                <option key={entry.tag.id} value={entry.tag.id}>
                  {entry.tag.name}
                </option>
              ))}
            </Select>
          </div>
          {createMutation.isError && (
            <p className="text-xs text-danger">{(createMutation.error as Error).message}</p>
          )}
          <Button type="submit" className="w-full" disabled={createMutation.isPending}>
            Create
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
