"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Star, Trash2 } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import type { ProviderConfig, SearchProfile } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Textarea } from "@/components/ui/input";

export default function AdminProfilesPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<SearchProfile | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [providers, setProviders] = useState<string[]>([]);

  const { data: profiles } = useQuery({
    queryKey: ["admin-profiles"],
    queryFn: () => api.get<SearchProfile[]>("/api/v1/admin/profiles"),
  });

  const { data: allProviders } = useQuery({
    queryKey: ["admin-providers"],
    queryFn: () => api.get<ProviderConfig[]>("/api/v1/admin/providers"),
  });

  const saveMutation = useMutation({
    mutationFn: () => {
      const body = { name, description, providers };
      return editing
        ? api.patch(`/api/v1/admin/profiles/${editing.id}`, body)
        : api.post("/api/v1/admin/profiles", body);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-profiles"] });
      void queryClient.invalidateQueries({ queryKey: ["profiles"] });
      close();
    },
  });

  const defaultMutation = useMutation({
    mutationFn: (id: string) => api.patch(`/api/v1/admin/profiles/${id}`, { is_default: true }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin-profiles"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/admin/profiles/${id}`),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin-profiles"] }),
  });

  function open(profile?: SearchProfile) {
    if (profile) {
      setEditing(profile);
      setName(profile.name);
      setDescription(profile.description);
      setProviders(profile.providers);
    } else {
      setEditing(null);
      setName("");
      setDescription("");
      setProviders([]);
    }
    setCreating(true);
  }

  function close() {
    setCreating(false);
    setEditing(null);
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => open()}>
          <Plus className="h-4 w-4" /> New profile
        </Button>
      </div>

      {profiles?.map((profile) => (
        <Card key={profile.id}>
          <CardContent className="flex flex-wrap items-center gap-3 p-4">
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-2 text-sm font-medium">
                {profile.name}
                {profile.is_default && <Badge variant="accent">default</Badge>}
                {!profile.is_active && <Badge>inactive</Badge>}
              </p>
              <p className="text-xs text-muted">
                {profile.description || "No description"} ·{" "}
                {profile.providers.length === 0
                  ? "all providers"
                  : `${profile.providers.length} providers`}
              </p>
            </div>
            {!profile.is_default && (
              <Button
                variant="ghost"
                size="icon"
                aria-label="Make default"
                title="Make default"
                onClick={() => defaultMutation.mutate(profile.id)}
              >
                <Star className="h-4 w-4" />
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={() => open(profile)}>
              Edit
            </Button>
            {!profile.is_default && (
              <Button
                variant="ghost"
                size="icon"
                aria-label="Delete profile"
                onClick={() => {
                  if (confirm(`Delete profile "${profile.name}"?`)) {
                    deleteMutation.mutate(profile.id);
                  }
                }}
              >
                <Trash2 className="h-4 w-4 text-danger" />
              </Button>
            )}
          </CardContent>
        </Card>
      ))}

      <Dialog
        open={creating}
        onClose={close}
        title={editing ? `Edit ${editing.name}` : "New search profile"}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            saveMutation.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="profile-name">Name</Label>
            <Input
              id="profile-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="profile-desc">Description</Label>
            <Textarea
              id="profile-desc"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={2}
            />
          </div>
          <div>
            <Label>Providers (none selected = all enabled providers)</Label>
            <div className="grid max-h-44 grid-cols-2 gap-1 overflow-y-auto rounded-lg border border-border p-2">
              {allProviders?.map((provider) => (
                <label key={provider.slug} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={providers.includes(provider.slug)}
                    onChange={(event) =>
                      setProviders(
                        event.target.checked
                          ? [...providers, provider.slug]
                          : providers.filter((slug) => slug !== provider.slug),
                      )
                    }
                  />
                  {provider.name}
                </label>
              ))}
            </div>
          </div>
          {saveMutation.isError && (
            <p className="text-xs text-danger">{(saveMutation.error as Error).message}</p>
          )}
          <Button type="submit" className="w-full" disabled={saveMutation.isPending}>
            Save profile
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
