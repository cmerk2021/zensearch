"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Package, Plus, RefreshCw, RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import type { PluginInfo, Repository } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardContent, CardHeader, CardTitle, EmptyState } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Select, Switch } from "@/components/ui/input";

interface CatalogEntry {
  id: string;
  name?: string;
  version: string;
  description?: string;
}

export default function AdminPluginsPage() {
  const queryClient = useQueryClient();
  const [showAddRepo, setShowAddRepo] = useState(false);
  const [repoName, setRepoName] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [repoKind, setRepoKind] = useState("community");
  const [browsing, setBrowsing] = useState<Repository | null>(null);
  const [installError, setInstallError] = useState("");

  const { data: plugins } = useQuery({
    queryKey: ["admin-plugins"],
    queryFn: () => api.get<PluginInfo[]>("/api/v1/admin/plugins"),
  });

  const { data: repositories } = useQuery({
    queryKey: ["admin-repositories"],
    queryFn: () => api.get<Repository[]>("/api/v1/admin/repositories"),
  });

  const { data: catalog } = useQuery({
    queryKey: ["repo-catalog", browsing?.id],
    queryFn: () =>
      api.get<{ plugins: CatalogEntry[] }>(
        `/api/v1/admin/repositories/${browsing!.id}/catalog`,
      ),
    enabled: !!browsing,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin-plugins"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-repositories"] });
  };

  const addRepoMutation = useMutation({
    mutationFn: () =>
      api.post("/api/v1/admin/repositories", { name: repoName, url: repoUrl, kind: repoKind }),
    onSuccess: () => {
      invalidate();
      setShowAddRepo(false);
      setRepoName("");
      setRepoUrl("");
    },
  });

  const syncMutation = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/admin/repositories/${id}/sync`),
    onSuccess: invalidate,
  });

  const installMutation = useMutation({
    mutationFn: (pluginId: string) =>
      api.post("/api/v1/admin/plugins/install", { plugin_id: pluginId }),
    onSuccess: () => {
      invalidate();
      setInstallError("");
    },
    onError: (error) => setInstallError((error as Error).message),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ slug, enable }: { slug: string; enable: boolean }) =>
      api.post(`/api/v1/admin/plugins/${slug}/${enable ? "enable" : "disable"}`),
    onSuccess: invalidate,
  });

  const rollbackMutation = useMutation({
    mutationFn: (slug: string) => api.post(`/api/v1/admin/plugins/${slug}/rollback`),
    onSuccess: invalidate,
  });

  const removeMutation = useMutation({
    mutationFn: (slug: string) => api.delete(`/api/v1/admin/plugins/${slug}`),
    onSuccess: invalidate,
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Installed plugins</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {plugins && plugins.length === 0 && (
            <EmptyState
              icon={<Package className="h-8 w-8" />}
              title="No plugins installed"
              description="Add a repository below, sync its catalog, then install plugins from it."
            />
          )}
          {plugins?.map((plugin) => (
            <div
              key={plugin.slug}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-border p-3"
            >
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-sm font-medium">
                  {plugin.name}
                  <Badge variant="outline">v{plugin.version}</Badge>
                  {plugin.status === "error" && <Badge variant="danger">error</Badge>}
                  {plugin.status === "disabled" && <Badge>disabled</Badge>}
                </p>
                <p className="text-xs text-muted">
                  {plugin.description || plugin.slug}
                  {plugin.error && <span className="text-danger"> — {plugin.error}</span>}
                </p>
              </div>
              {plugin.previous_version && (
                <Button
                  variant="ghost"
                  size="icon"
                  title={`Roll back to ${plugin.previous_version}`}
                  aria-label="Rollback"
                  onClick={() => rollbackMutation.mutate(plugin.slug)}
                >
                  <RotateCcw className="h-4 w-4" />
                </Button>
              )}
              <Switch
                checked={plugin.status === "enabled"}
                onChange={(value) => toggleMutation.mutate({ slug: plugin.slug, enable: value })}
                label={`Enable ${plugin.name}`}
              />
              <Button
                variant="ghost"
                size="icon"
                aria-label="Remove plugin"
                onClick={() => {
                  if (confirm(`Remove plugin "${plugin.name}"?`)) {
                    removeMutation.mutate(plugin.slug);
                  }
                }}
              >
                <Trash2 className="h-4 w-4 text-danger" />
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Repositories</CardTitle>
          <Button size="sm" variant="outline" onClick={() => setShowAddRepo(true)}>
            <Plus className="h-4 w-4" /> Add repository
          </Button>
        </CardHeader>
        <CardContent className="space-y-2">
          {repositories?.map((repo) => (
            <div
              key={repo.id}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-border p-3"
            >
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-sm font-medium">
                  {repo.name}
                  <Badge
                    variant={
                      repo.kind === "official"
                        ? "accent"
                        : repo.kind === "private"
                          ? "warning"
                          : "default"
                    }
                  >
                    {repo.kind}
                  </Badge>
                </p>
                <p className="truncate text-xs text-muted">
                  {repo.url} · synced{" "}
                  {repo.last_synced_at ? timeAgo(repo.last_synced_at) : "never"}
                </p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setBrowsing(repo)}>
                Browse
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Sync repository"
                onClick={() => syncMutation.mutate(repo.id)}
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          ))}
          {repositories && repositories.length === 0 && (
            <p className="py-4 text-center text-xs text-muted">
              No repositories configured. Plugins can also be sideloaded via the API.
            </p>
          )}
          <p className="text-[11px] leading-relaxed text-muted">
            Plugins run with the same privileges as Zen itself — install only from sources
            you trust. Artifact checksums are verified against the repository catalog.
          </p>
        </CardContent>
      </Card>

      <Dialog open={showAddRepo} onClose={() => setShowAddRepo(false)} title="Add repository">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            addRepoMutation.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="repo-name">Name</Label>
            <Input
              id="repo-name"
              value={repoName}
              onChange={(event) => setRepoName(event.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="repo-url">Catalog URL (index.json)</Label>
            <Input
              id="repo-url"
              type="url"
              value={repoUrl}
              onChange={(event) => setRepoUrl(event.target.value)}
              placeholder="https://plugins.example.com/index.json"
              required
            />
          </div>
          <div>
            <Label htmlFor="repo-kind">Kind</Label>
            <Select
              id="repo-kind"
              value={repoKind}
              onChange={(event) => setRepoKind(event.target.value)}
            >
              <option value="official">Official</option>
              <option value="community">Community</option>
              <option value="private">Private</option>
            </Select>
          </div>
          {addRepoMutation.isError && (
            <p className="text-xs text-danger">{(addRepoMutation.error as Error).message}</p>
          )}
          <Button type="submit" className="w-full" disabled={addRepoMutation.isPending}>
            Add
          </Button>
        </form>
      </Dialog>

      <Dialog
        open={!!browsing}
        onClose={() => setBrowsing(null)}
        title={browsing ? `Catalog — ${browsing.name}` : ""}
      >
        {installError && <p className="mb-2 text-xs text-danger">{installError}</p>}
        <ul className="max-h-96 space-y-2 overflow-y-auto">
          {catalog?.plugins.map((entry) => {
            const installed = plugins?.find((plugin) => plugin.slug === entry.id);
            return (
              <li
                key={entry.id}
                className="flex items-center gap-3 rounded-lg border border-border p-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    {entry.name || entry.id}{" "}
                    <span className="text-xs text-muted">v{entry.version}</span>
                  </p>
                  {entry.description && (
                    <p className="truncate text-xs text-muted">{entry.description}</p>
                  )}
                </div>
                {installed ? (
                  installed.version === entry.version ? (
                    <Badge variant="success">installed</Badge>
                  ) : (
                    <Button
                      size="sm"
                      onClick={() => installMutation.mutate(entry.id)}
                      disabled={installMutation.isPending}
                    >
                      Update
                    </Button>
                  )
                ) : (
                  <Button
                    size="sm"
                    onClick={() => installMutation.mutate(entry.id)}
                    disabled={installMutation.isPending}
                  >
                    Install
                  </Button>
                )}
              </li>
            );
          })}
          {catalog && catalog.plugins.length === 0 && (
            <p className="py-4 text-center text-xs text-muted">
              Catalog is empty — try syncing the repository.
            </p>
          )}
        </ul>
      </Dialog>
    </div>
  );
}
