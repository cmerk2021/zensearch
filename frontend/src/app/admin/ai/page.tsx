"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select, Switch } from "@/components/ui/input";

interface AIAdminStatus {
  enabled: boolean;
  backend: string;
  model: string;
  reachable: boolean;
  models: string[];
  error?: string;
}

export default function AdminAIPage() {
  const queryClient = useQueryClient();
  const [enabled, setEnabled] = useState(false);
  const [backend, setBackend] = useState("ollama");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [testOutput, setTestOutput] = useState("");

  const { data: status } = useQuery({
    queryKey: ["admin-ai-status"],
    queryFn: () => api.get<AIAdminStatus>("/api/v1/admin/ai/status"),
  });

  const { data: settings } = useQuery({
    queryKey: ["admin-settings"],
    queryFn: () => api.get<Record<string, unknown>>("/api/v1/admin/settings"),
  });

  useEffect(() => {
    if (settings) {
      setEnabled(Boolean(settings["ai.enabled"]));
      setBackend(String(settings["ai.backend"] ?? "ollama"));
      setBaseUrl(String(settings["ai.base_url"] ?? ""));
      setModel(String(settings["ai.model"] ?? ""));
    }
  }, [settings]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const values: Record<string, unknown> = {
        "ai.enabled": enabled,
        "ai.backend": backend,
        "ai.base_url": baseUrl,
        "ai.model": model,
      };
      if (apiKey) values["ai.api_key"] = apiKey;
      return api.put("/api/v1/admin/settings", { values });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-ai-status"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-settings"] });
      setApiKey("");
    },
  });

  async function runTest() {
    setTestOutput("Testing…");
    try {
      const result = await api.post<{ ok: boolean; response: string }>("/api/v1/admin/ai/test", {
        prompt: "Reply with the single word: pong",
      });
      setTestOutput(`Response: ${result.response}`);
    } catch (err) {
      setTestOutput(err instanceof Error ? err.message : "Test failed");
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-accent" /> AI integration
            {status?.enabled ? (
              <Badge variant={status.reachable ? "success" : "danger"}>
                {status.reachable ? "reachable" : "unreachable"}
              </Badge>
            ) : (
              <Badge>disabled</Badge>
            )}
          </CardTitle>
          <CardDescription>
            Optional. Zen is fully functional without AI. Local backends (Ollama, LM Studio)
            keep all data on your network.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm">Enable AI features</p>
            <Switch checked={enabled} onChange={setEnabled} label="Enable AI" />
          </div>
          <div>
            <Label htmlFor="ai-backend">Backend</Label>
            <Select
              id="ai-backend"
              value={backend}
              onChange={(event) => setBackend(event.target.value)}
            >
              <option value="ollama">Ollama (local)</option>
              <option value="lmstudio">LM Studio (local)</option>
              <option value="openai">OpenAI-compatible API</option>
              <option value="openrouter">OpenRouter</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="ai-url">Base URL</Label>
            <Input
              id="ai-url"
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder={
                backend === "ollama"
                  ? "http://localhost:11434"
                  : backend === "lmstudio"
                    ? "http://localhost:1234/v1"
                    : backend === "openrouter"
                      ? "https://openrouter.ai/api/v1"
                      : "https://api.openai.com/v1"
              }
            />
          </div>
          <div>
            <Label htmlFor="ai-key">API key (not needed for local backends)</Label>
            <Input
              id="ai-key"
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={settings?.["ai.api_key"] ? String(settings["ai.api_key"]) : "sk-…"}
              autoComplete="off"
            />
          </div>
          <div>
            <Label htmlFor="ai-model">Model</Label>
            {status?.models && status.models.length > 0 ? (
              <Select
                id="ai-model"
                value={model}
                onChange={(event) => setModel(event.target.value)}
              >
                <option value="">Select a model…</option>
                {status.models.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </Select>
            ) : (
              <Input
                id="ai-model"
                value={model}
                onChange={(event) => setModel(event.target.value)}
                placeholder="llama3.2"
              />
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
              Save
            </Button>
            <Button variant="outline" onClick={() => void runTest()}>
              <FlaskConical className="h-4 w-4" /> Test
            </Button>
            {testOutput && <span className="text-xs text-muted">{testOutput}</span>}
          </div>
          {saveMutation.isError && (
            <p className="text-xs text-danger">{(saveMutation.error as Error).message}</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
