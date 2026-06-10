"use client";

import { BookmarkPlus, Check, Copy, Pin, Sparkles } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import type { SearchResult, Workspace } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useAuth } from "@/stores/auth";

export function ResultCard({
  result,
  query,
  workspaces,
  onSummarizeDomain,
}: {
  result: SearchResult;
  query: string;
  workspaces?: Workspace[];
  onSummarizeDomain?: (domain: string) => void;
}) {
  const { user, preferences } = useAuth();
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showSave, setShowSave] = useState(false);
  const canWrite = user && user.role !== "readonly";

  async function save(workspaceId?: string | null) {
    try {
      await api.post("/api/v1/bookmarks", {
        url: result.url,
        title: result.title,
        snippet: result.snippet,
        workspace_id: workspaceId ?? null,
        source_provider: result.providers[0] ?? null,
        source_query: query,
      });
      setSaved(true);
      setShowSave(false);
    } catch {
      /* surfaced via saved state remaining false */
    }
  }

  async function copyCitation() {
    const citation = `${result.title}. ${result.url} (accessed ${new Date().toLocaleDateString()})`;
    await navigator.clipboard.writeText(citation);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  function recordClick() {
    if (!user || !canWrite) return;
    void api
      .post("/api/v1/search/click", {
        url: result.url,
        query,
        provider: result.providers[0] ?? null,
      })
      .catch(() => undefined);
  }

  return (
    <article
      className={cn(
        "group rounded-xl border border-transparent px-4 py-3 transition-colors hover:border-border hover:bg-surface",
        result.pinned && "border-accent/30 bg-accent/5",
      )}
    >
      <div className="flex items-center gap-2 text-xs text-muted">
        {result.favicon_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={result.favicon_url}
            alt=""
            width={16}
            height={16}
            loading="lazy"
            className="rounded"
          />
        ) : null}
        <span className="truncate">{result.domain}</span>
        {result.pinned && (
          <span className="inline-flex items-center gap-1 text-accent">
            <Pin className="h-3 w-3" /> pinned
          </span>
        )}
        <span className="ml-auto hidden gap-1 md:flex">
          {result.providers.map((provider) => (
            <span
              key={provider}
              className="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] uppercase tracking-wide"
              title={`Found by ${provider}`}
            >
              {provider}
            </span>
          ))}
        </span>
      </div>

      <h3 className="mt-1">
        <a
          href={result.url}
          target={preferences?.open_links_new_tab === false ? undefined : "_blank"}
          rel="noopener noreferrer"
          onClick={recordClick}
          onAuxClick={recordClick}
          className="text-[15px] font-medium leading-snug text-accent visited:opacity-80 hover:underline"
        >
          {result.title}
        </a>
      </h3>

      {result.snippet && (
        <p className="mt-1 max-w-reading text-sm leading-relaxed text-muted">
          {result.snippet}
        </p>
      )}

      {canWrite && (
        <div className="mt-2 flex items-center gap-1 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
          <div className="relative">
            <button
              onClick={() => (workspaces?.length ? setShowSave(!showSave) : void save())}
              disabled={saved}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted hover:bg-surface-2 hover:text-foreground disabled:text-success"
            >
              {saved ? <Check className="h-3.5 w-3.5" /> : <BookmarkPlus className="h-3.5 w-3.5" />}
              {saved ? "Saved" : "Save"}
            </button>
            {showSave && workspaces && (
              <div className="absolute left-0 top-7 z-10 w-52 rounded-lg border border-border bg-surface p-1 shadow-lg">
                <button
                  className="w-full rounded px-2 py-1.5 text-left text-xs hover:bg-surface-2"
                  onClick={() => void save(null)}
                >
                  Save without workspace
                </button>
                {workspaces.map((workspace) => (
                  <button
                    key={workspace.id}
                    className="w-full truncate rounded px-2 py-1.5 text-left text-xs hover:bg-surface-2"
                    onClick={() => void save(workspace.id)}
                  >
                    → {workspace.name}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={() => void copyCitation()}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted hover:bg-surface-2 hover:text-foreground"
          >
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied" : "Cite"}
          </button>
          {onSummarizeDomain && (
            <button
              onClick={() => onSummarizeDomain(result.domain)}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted hover:bg-surface-2 hover:text-foreground"
            >
              <Sparkles className="h-3.5 w-3.5" />
              Similar
            </button>
          )}
        </div>
      )}
    </article>
  );
}
