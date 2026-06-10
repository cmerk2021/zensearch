"use client";

import { Command } from "cmdk";
import {
  BookMarked,
  Eye,
  FolderOpen,
  Layers,
  LayoutDashboard,
  Moon,
  Search,
  Settings,
  Shield,
  StickyNote,
  Sun,
  Target,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Workspace } from "@/lib/types";
import { useAuth } from "@/stores/auth";
import { useSearchUI } from "@/stores/search";

export function CommandPalette() {
  const router = useRouter();
  const { paletteOpen, setPaletteOpen, setMode } = useSearchUI();
  const { user, setPreferences } = useAuth();
  const [query, setQuery] = useState("");

  const { data: workspaces } = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => api.get<Workspace[]>("/api/v1/workspaces"),
    enabled: paletteOpen && !!user,
  });

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault();
        setPaletteOpen(!paletteOpen);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [paletteOpen, setPaletteOpen]);

  const run = useCallback(
    (action: () => void) => {
      action();
      setPaletteOpen(false);
      setQuery("");
    },
    [setPaletteOpen],
  );

  if (!paletteOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-[14vh]"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) setPaletteOpen(false);
      }}
      role="presentation"
    >
      <Command
        label="Command palette"
        className="w-full max-w-xl animate-fade-in overflow-hidden rounded-xl border border-border bg-surface shadow-2xl"
        loop
      >
        <Command.Input
          value={query}
          onValueChange={setQuery}
          placeholder="Type a command or search…"
          autoFocus
          className="h-12 w-full border-b border-border bg-transparent px-4 text-sm outline-none placeholder:text-muted"
        />
        <Command.List className="max-h-[50vh] overflow-y-auto p-2">
          <Command.Empty className="px-3 py-6 text-center text-sm text-muted">
            No matches.
          </Command.Empty>

          {query.trim() && (
            <Command.Group>
              <Item
                icon={<Search className="h-4 w-4" />}
                onSelect={() =>
                  run(() => router.push(`/search?q=${encodeURIComponent(query.trim())}`))
                }
              >
                Search for “{query.trim()}”
              </Item>
            </Command.Group>
          )}

          <Command.Group heading="Navigate" className="text-[11px] text-muted [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5">
            <Item icon={<LayoutDashboard className="h-4 w-4" />} onSelect={() => run(() => router.push("/"))}>
              Home
            </Item>
            <Item icon={<FolderOpen className="h-4 w-4" />} onSelect={() => run(() => router.push("/workspaces"))}>
              Workspaces
            </Item>
            <Item icon={<BookMarked className="h-4 w-4" />} onSelect={() => run(() => router.push("/bookmarks"))}>
              Bookmarks
            </Item>
            <Item icon={<Layers className="h-4 w-4" />} onSelect={() => run(() => router.push("/collections"))}>
              Collections
            </Item>
            <Item icon={<StickyNote className="h-4 w-4" />} onSelect={() => run(() => router.push("/notes"))}>
              Notes
            </Item>
            <Item icon={<Settings className="h-4 w-4" />} onSelect={() => run(() => router.push("/settings"))}>
              Settings
            </Item>
            {user?.role === "admin" && (
              <Item icon={<Shield className="h-4 w-4" />} onSelect={() => run(() => router.push("/admin"))}>
                Admin dashboard
              </Item>
            )}
          </Command.Group>

          <Command.Group heading="Search mode" className="text-[11px] text-muted [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5">
            <Item icon={<Search className="h-4 w-4" />} onSelect={() => run(() => setMode("normal"))}>
              Normal mode
            </Item>
            <Item icon={<Eye className="h-4 w-4" />} onSelect={() => run(() => setMode("privacy"))}>
              Privacy mode — no history, no personalization
            </Item>
            <Item icon={<Target className="h-4 w-4" />} onSelect={() => run(() => setMode("focus"))}>
              Focus mode — remove distractions
            </Item>
            <Item icon={<FolderOpen className="h-4 w-4" />} onSelect={() => run(() => setMode("research"))}>
              Research mode — capture to workspace
            </Item>
          </Command.Group>

          {workspaces && workspaces.length > 0 && (
            <Command.Group heading="Workspaces" className="text-[11px] text-muted [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5">
              {workspaces.slice(0, 6).map((workspace) => (
                <Item
                  key={workspace.id}
                  icon={<FolderOpen className="h-4 w-4" />}
                  onSelect={() => run(() => router.push(`/workspaces/${workspace.id}`))}
                >
                  {workspace.name}
                </Item>
              ))}
            </Command.Group>
          )}

          {user && (
            <Command.Group heading="Theme" className="text-[11px] text-muted [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5">
              <Item icon={<Sun className="h-4 w-4" />} onSelect={() => run(() => void setPreferences({ theme: "light" }))}>
                Light theme
              </Item>
              <Item icon={<Moon className="h-4 w-4" />} onSelect={() => run(() => void setPreferences({ theme: "dark" }))}>
                Dark theme
              </Item>
              <Item icon={<Moon className="h-4 w-4" />} onSelect={() => run(() => void setPreferences({ theme: "amoled" }))}>
                AMOLED theme
              </Item>
            </Command.Group>
          )}
        </Command.List>
      </Command>
    </div>
  );
}

function Item({
  children,
  icon,
  onSelect,
}: {
  children: React.ReactNode;
  icon?: React.ReactNode;
  onSelect: () => void;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-foreground aria-selected:bg-surface-2"
    >
      <span className="text-muted">{icon}</span>
      {children}
    </Command.Item>
  );
}
