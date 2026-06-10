"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Workspace } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, EmptyState } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Textarea } from "@/components/ui/input";

export default function WorkspacesPage() {
  return (
    <AppShell>
      <WorkspacesContent />
    </AppShell>
  );
}

function WorkspacesContent() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [showArchived, setShowArchived] = useState(false);

  const { data: workspaces } = useQuery({
    queryKey: ["workspaces", showArchived],
    queryFn: () =>
      api.get<Workspace[]>(`/api/v1/workspaces?include_archived=${showArchived}`),
  });

  const createMutation = useMutation({
    mutationFn: () => api.post<Workspace>("/api/v1/workspaces", { name, description }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      setShowCreate(false);
      setName("");
      setDescription("");
    },
  });

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Workspaces</h1>
          <p className="text-sm text-muted">
            Persistent research contexts: searches, notes, and sources in one place.
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" /> New workspace
        </Button>
      </div>

      <label className="mb-4 flex items-center gap-2 text-xs text-muted">
        <input
          type="checkbox"
          checked={showArchived}
          onChange={(event) => setShowArchived(event.target.checked)}
        />
        Show archived
      </label>

      {workspaces && workspaces.length === 0 && (
        <EmptyState
          icon={<FolderOpen className="h-8 w-8" />}
          title="No workspaces yet"
          description="Create one for each research project — e.g. “NAS upgrade”, “Learning Rust”."
          action={
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="h-4 w-4" /> Create workspace
            </Button>
          }
        />
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {workspaces?.map((workspace) => (
          <Link key={workspace.id} href={`/workspaces/${workspace.id}`}>
            <Card className="h-full transition-colors hover:border-accent/40">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FolderOpen className="h-4 w-4 text-accent" />
                  {workspace.name}
                  {workspace.status === "archived" && (
                    <span className="text-[10px] uppercase text-muted">archived</span>
                  )}
                </CardTitle>
                {workspace.description && (
                  <CardDescription>{workspace.description}</CardDescription>
                )}
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted">Updated {timeAgo(workspace.updated_at)}</p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <Dialog open={showCreate} onClose={() => setShowCreate(false)} title="New workspace">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            createMutation.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="ws-name">Name</Label>
            <Input
              id="ws-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Kubernetes Lab Build"
              autoFocus
              required
            />
          </div>
          <div>
            <Label htmlFor="ws-desc">Description (optional)</Label>
            <Textarea
              id="ws-desc"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              placeholder="What are you researching?"
            />
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
