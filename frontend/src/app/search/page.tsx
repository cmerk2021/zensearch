"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Sparkles } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api, qs } from "@/lib/api";
import type { SearchMode, SearchResponse, Workspace } from "@/lib/types";
import { useAuth } from "@/stores/auth";
import { useSearchUI } from "@/stores/search";
import { AppShell } from "@/components/app-shell";
import { ResultCard } from "@/components/search/result-card";
import { SearchBox } from "@/components/search/search-box";
import { Badge, Spinner } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function SearchPage() {
  return (
    <AppShell>
      <Suspense
        fallback={
          <div className="flex h-64 items-center justify-center">
            <Spinner className="h-6 w-6" />
          </div>
        }
      >
        <SearchContent />
      </Suspense>
    </AppShell>
  );
}

function SearchContent() {
  const params = useSearchParams();
  const router = useRouter();
  const query = params.get("q") ?? "";
  const mode = (params.get("mode") ?? "normal") as SearchMode;
  const profile = params.get("profile");
  const workspaceId = params.get("workspace_id");
  const page = Number(params.get("page") ?? "1");
  const { setMode, setProfile } = useSearchUI();
  const user = useAuth((state) => state.user);
  const [summary, setSummary] = useState<string | null>(null);
  const [summarizing, setSummarizing] = useState(false);

  useEffect(() => {
    setMode(mode);
    setProfile(profile);
  }, [mode, profile, setMode, setProfile]);

  const { data, isLoading, error } = useQuery({
    queryKey: ["search", query, mode, profile, workspaceId, page],
    queryFn: () =>
      api.get<SearchResponse>(
        `/api/v1/search${qs({
          q: query,
          mode: mode !== "normal" ? mode : undefined,
          profile: profile ?? undefined,
          workspace_id: workspaceId ?? undefined,
          page: page > 1 ? page : undefined,
        })}`,
      ),
    enabled: query.trim().length > 0,
    staleTime: 60_000,
  });

  const { data: workspaces } = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => api.get<Workspace[]>("/api/v1/workspaces"),
    enabled: !!user && user.role !== "readonly",
  });

  const { data: aiStatus } = useQuery({
    queryKey: ["ai-status"],
    queryFn: () => api.get<{ enabled: boolean; reachable: boolean }>("/api/v1/ai/status"),
    enabled: !!user,
    staleTime: 300_000,
  });

  useEffect(() => {
    if (data?.redirect) window.location.href = data.redirect;
  }, [data?.redirect]);

  useEffect(() => {
    setSummary(null);
  }, [query]);

  async function summarize() {
    if (!data) return;
    setSummarizing(true);
    try {
      const response = await api.post<{ text: string }>("/api/v1/ai/summarize", {
        q: query,
        results: data.results.slice(0, 12),
      });
      setSummary(response.text);
    } catch (err) {
      setSummary(
        err instanceof Error ? `Summary unavailable: ${err.message}` : "Summary unavailable.",
      );
    } finally {
      setSummarizing(false);
    }
  }

  const failedProviders = data?.providers.filter((p) => !p.ok && !p.skipped) ?? [];

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6">
      <SearchBox initialQuery={query} size="md" />

      {isLoading && (
        <div className="flex items-center gap-2 py-10 text-sm text-muted">
          <Spinner /> Searching {mode !== "normal" ? `in ${mode} mode` : ""}…
        </div>
      )}

      {error && (
        <div className="mt-6 rounded-xl border border-danger/30 bg-danger/5 p-4 text-sm text-danger">
          {(error as Error).message}
        </div>
      )}

      {data && !data.redirect && (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted">
            <span>
              {data.results.length} results in {data.duration_ms}ms
              {data.cached && " (cached)"}
            </span>
            {data.profile_slug && <Badge variant="outline">{data.profile_slug}</Badge>}
            {mode !== "normal" && <Badge variant="accent">{mode} mode</Badge>}
            {aiStatus?.enabled && data.results.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="ml-auto text-xs"
                onClick={() => void summarize()}
                disabled={summarizing}
              >
                <Sparkles className="h-3.5 w-3.5" />
                {summarizing ? "Summarizing…" : "AI summary"}
              </Button>
            )}
          </div>

          {failedProviders.length > 0 && (
            <div className="mt-3 flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                Partial results — {failedProviders.map((p) => p.name).join(", ")}{" "}
                {failedProviders.length === 1 ? "did" : "did"} not respond.
              </span>
            </div>
          )}

          {summary && (
            <div className="mt-4 rounded-xl border border-accent/30 bg-accent/5 p-4">
              <p className="mb-1 flex items-center gap-1.5 text-xs font-medium text-accent">
                <Sparkles className="h-3.5 w-3.5" /> AI summary
              </p>
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{summary}</p>
            </div>
          )}

          <div className="mt-4 space-y-1">
            {data.results.map((result) => (
              <ResultCard
                key={result.url}
                result={result}
                query={query}
                workspaces={workspaces}
              />
            ))}
          </div>

          {data.results.length === 0 && !isLoading && (
            <div className="py-16 text-center text-sm text-muted">
              No results. Try different terms or another search mode.
            </div>
          )}

          {data.results.length >= 20 && (
            <div className="mt-6 flex justify-center gap-2">
              {page > 1 && (
                <Button
                  variant="outline"
                  onClick={() =>
                    router.push(
                      `/search${qs({ q: query, mode: mode !== "normal" ? mode : undefined, page: page - 1 > 1 ? page - 1 : undefined })}`,
                    )
                  }
                >
                  Previous
                </Button>
              )}
              <Button
                variant="outline"
                onClick={() =>
                  router.push(
                    `/search${qs({ q: query, mode: mode !== "normal" ? mode : undefined, page: page + 1 })}`,
                  )
                }
              >
                Next page
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
