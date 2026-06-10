"use client";

import { Eye, FolderOpen, Search as SearchIcon, Target, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, qs } from "@/lib/api";
import type { SearchMode, SearchProfile } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useSearchUI } from "@/stores/search";
import { useQuery } from "@tanstack/react-query";

const MODES: { value: SearchMode; label: string; icon: React.ElementType; hint: string }[] = [
  { value: "normal", label: "Normal", icon: SearchIcon, hint: "Standard search" },
  { value: "privacy", label: "Privacy", icon: Eye, hint: "No history, no personalization" },
  { value: "focus", label: "Focus", icon: Target, hint: "Distractions removed" },
  { value: "research", label: "Research", icon: FolderOpen, hint: "Capture to workspace" },
];

export function SearchBox({
  initialQuery = "",
  autoFocus = false,
  size = "lg",
}: {
  initialQuery?: string;
  autoFocus?: boolean;
  size?: "lg" | "md";
}) {
  const router = useRouter();
  const { mode, setMode, profileSlug, setProfile, workspaceId } = useSearchUI();
  const [query, setQuery] = useState(initialQuery);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [highlighted, setHighlighted] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const { data: profiles } = useQuery({
    queryKey: ["profiles"],
    queryFn: () => api.get<SearchProfile[]>("/api/v1/profiles"),
    staleTime: 300_000,
  });

  useEffect(() => {
    setQuery(initialQuery);
  }, [initialQuery]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (
        event.key === "/" &&
        !["INPUT", "TEXTAREA"].includes((event.target as HTMLElement)?.tagName)
      ) {
        event.preventDefault();
        inputRef.current?.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!query.trim() || query.startsWith("!") || mode === "privacy") {
      setSuggestions([]);
      return;
    }
    debounceRef.current = setTimeout(() => {
      api
        .get<string[]>(`/api/v1/search/suggest${qs({ q: query.trim() })}`)
        .then(setSuggestions)
        .catch(() => setSuggestions([]));
    }, 180);
    return () => debounceRef.current && clearTimeout(debounceRef.current);
  }, [query, mode]);

  function submit(text?: string) {
    const value = (text ?? query).trim();
    if (!value) return;
    setShowSuggestions(false);
    router.push(
      `/search${qs({
        q: value,
        mode: mode !== "normal" ? mode : undefined,
        profile: profileSlug ?? undefined,
        workspace_id: mode === "research" ? workspaceId ?? undefined : undefined,
      })}`,
    );
  }

  return (
    <div className="w-full">
      <div className="relative">
        <SearchIcon
          className={cn(
            "pointer-events-none absolute left-4 text-muted",
            size === "lg" ? "top-4 h-5 w-5" : "top-3 h-4 w-4",
          )}
        />
        <input
          ref={inputRef}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setShowSuggestions(true);
            setHighlighted(-1);
          }}
          onFocus={() => setShowSuggestions(true)}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 120)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              submit(highlighted >= 0 ? suggestions[highlighted] : undefined);
            } else if (event.key === "ArrowDown") {
              event.preventDefault();
              setHighlighted((current) => Math.min(current + 1, suggestions.length - 1));
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setHighlighted((current) => Math.max(current - 1, -1));
            } else if (event.key === "Escape") {
              setShowSuggestions(false);
            }
          }}
          placeholder="Search the web… (try !gh, !wiki)"
          autoFocus={autoFocus}
          aria-label="Search"
          autoComplete="off"
          spellCheck={false}
          className={cn(
            "w-full rounded-2xl border border-border bg-surface text-foreground shadow-sm placeholder:text-muted focus-ring",
            size === "lg" ? "h-[52px] pl-12 pr-12 text-base" : "h-10 pl-10 pr-10 text-sm",
          )}
        />
        {query && (
          <button
            onClick={() => {
              setQuery("");
              inputRef.current?.focus();
            }}
            aria-label="Clear search"
            className={cn(
              "absolute right-4 text-muted hover:text-foreground",
              size === "lg" ? "top-4" : "top-3",
            )}
          >
            <X className={size === "lg" ? "h-5 w-5" : "h-4 w-4"} />
          </button>
        )}

        {showSuggestions && suggestions.length > 0 && (
          <ul
            className="absolute z-20 mt-1.5 w-full overflow-hidden rounded-xl border border-border bg-surface shadow-lg"
            role="listbox"
          >
            {suggestions.map((suggestion, index) => (
              <li key={suggestion} role="option" aria-selected={index === highlighted}>
                <button
                  className={cn(
                    "flex w-full items-center gap-2.5 px-4 py-2.5 text-left text-sm",
                    index === highlighted ? "bg-surface-2" : "hover:bg-surface-2",
                  )}
                  onMouseDown={(event) => {
                    event.preventDefault();
                    submit(suggestion);
                  }}
                >
                  <SearchIcon className="h-3.5 w-3.5 text-muted" />
                  {suggestion}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {MODES.map(({ value, label, icon: Icon, hint }) => (
          <button
            key={value}
            onClick={() => setMode(value)}
            title={hint}
            aria-pressed={mode === value}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
              mode === value
                ? "border-accent/40 bg-accent/15 text-accent"
                : "border-border text-muted hover:bg-surface-2 hover:text-foreground",
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
        {profiles && profiles.length > 0 && (
          <select
            value={profileSlug ?? ""}
            onChange={(event) => setProfile(event.target.value || null)}
            aria-label="Search profile"
            className="ml-auto h-8 rounded-full border border-border bg-surface px-3 text-xs text-muted focus-ring"
          >
            <option value="">Default profile</option>
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.slug}>
                {profile.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {mode === "privacy" && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-success">
          <Eye className="h-3.5 w-3.5" />
          Privacy mode: nothing about this search will be stored.
        </p>
      )}
    </div>
  );
}
