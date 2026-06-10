"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, KeyRound } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import type { ProviderConfig } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Switch } from "@/components/ui/input";

export default function AdminProvidersPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<ProviderConfig | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [weight, setWeight] = useState("1.0");
  const [testResult, setTestResult] = useState<string | null>(null);

  const { data: providers } = useQuery({
    queryKey: ["admin-providers"],
    queryFn: () => api.get<ProviderConfig[]>("/api/v1/admin/providers"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ slug, body }: { slug: string; body: Record<string, unknown> }) =>
      api.patch(`/api/v1/admin/providers/${slug}`, body),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin-providers"] }),
  });

  async function testProvider(slug: string) {
    setTestResult("Testing…");
    try {
      const result = await api.post<{
        ok: boolean;
        result_count?: number;
        duration_ms: number;
        error?: string;
      }>(`/api/v1/admin/providers/${slug}/test?q=zen`);
      setTestResult(
        result.ok
          ? `OK — ${result.result_count} results in ${result.duration_ms}ms`
          : `Failed — ${result.error}`,
      );
    } catch (err) {
      setTestResult(err instanceof Error ? err.message : "Test failed");
    }
  }

  return (
    <div className="space-y-3">
      {providers?.map((provider) => (
        <Card key={provider.slug}>
          <CardContent className="flex flex-wrap items-center gap-3 p-4">
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-2 text-sm font-medium">
                {provider.name}
                <Badge variant="outline">{provider.category}</Badge>
                {provider.requires_api_key && (
                  <Badge variant={provider.has_api_key ? "success" : "warning"}>
                    <KeyRound className="h-3 w-3" />
                    {provider.has_api_key ? "key set" : "key required"}
                  </Badge>
                )}
                {!provider.builtin && <Badge variant="accent">plugin</Badge>}
              </p>
              <p className="mt-0.5 text-xs text-muted">{provider.description}</p>
            </div>
            <span className="text-xs text-muted">weight {provider.weight.toFixed(1)}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setEditing(provider);
                setWeight(String(provider.weight));
                setApiKey("");
                setTestResult(null);
              }}
            >
              Configure
            </Button>
            <Switch
              checked={provider.enabled}
              onChange={(value) =>
                updateMutation.mutate({ slug: provider.slug, body: { enabled: value } })
              }
              label={`Enable ${provider.name}`}
            />
          </CardContent>
        </Card>
      ))}

      <Dialog
        open={!!editing}
        onClose={() => setEditing(null)}
        title={editing ? `Configure ${editing.name}` : ""}
      >
        {editing && (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const body: Record<string, unknown> = { weight: parseFloat(weight) };
              if (apiKey) body.api_key = apiKey;
              updateMutation.mutate({ slug: editing.slug, body });
              setEditing(null);
            }}
            className="space-y-4"
          >
            <div>
              <Label htmlFor="prov-weight">Ranking weight (0–10)</Label>
              <Input
                id="prov-weight"
                type="number"
                step="0.1"
                min="0"
                max="10"
                value={weight}
                onChange={(event) => setWeight(event.target.value)}
              />
              <p className="mt-1 text-[11px] text-muted">
                Higher weight = more influence on result ranking.
              </p>
            </div>
            {(editing.requires_api_key || editing.has_api_key || editing.slug === "github" || editing.slug === "brave" || editing.slug === "stackoverflow") && (
              <div>
                <Label htmlFor="prov-key">API key {editing.has_api_key && "(set — leave blank to keep)"}</Label>
                <Input
                  id="prov-key"
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder={editing.has_api_key ? "••••••••" : "Paste API key"}
                  autoComplete="off"
                />
              </div>
            )}
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void testProvider(editing.slug)}
              >
                <FlaskConical className="h-4 w-4" /> Test provider
              </Button>
              {testResult && <span className="text-xs text-muted">{testResult}</span>}
            </div>
            <Button type="submit" className="w-full">
              Save
            </Button>
          </form>
        )}
      </Dialog>
    </div>
  );
}
