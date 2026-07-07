"use client";

import {
  BookMarked,
  Command,
  FolderOpen,
  History,
  Layers,
  LogOut,
  Search,
  Settings,
  Shield,
  StickyNote,
  Tags,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { useSearchUI } from "@/stores/search";
import { CommandPalette } from "@/components/command-palette";
import { Button } from "@/components/ui/button";
import { ZenLogo } from "@/components/ui/logo";

const NAV = [
  { href: "/", label: "Search", icon: Search, exact: true },
  { href: "/workspaces", label: "Workspaces", icon: FolderOpen },
  { href: "/bookmarks", label: "Bookmarks", icon: BookMarked },
  { href: "/collections", label: "Collections", icon: Layers },
  { href: "/notes", label: "Notes", icon: StickyNote },
  { href: "/tags", label: "Tags", icon: Tags },
  { href: "/history", label: "History", icon: History },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loaded, logout } = useAuth();
  const setPaletteOpen = useSearchUI((state) => state.setPaletteOpen);

  useEffect(() => {
    if (loaded && !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [loaded, user, router, pathname]);

  if (!loaded || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted">
        Loading…
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-56 flex-col border-r border-border bg-surface md:flex">
        <Link href="/" className="flex items-center gap-2 px-5 py-5">
          <ZenMark />
          <span className="text-base font-semibold tracking-tight">Zen</span>
        </Link>
        <nav className="flex-1 space-y-0.5 px-3" aria-label="Primary">
          {NAV.map(({ href, label, icon: Icon, exact }) => {
            const active = exact ? pathname === href : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors",
                  active
                    ? "bg-surface-2 font-medium text-foreground"
                    : "text-muted hover:bg-surface-2 hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
          {user.role === "admin" && (
            <Link
              href="/admin"
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors",
                pathname.startsWith("/admin")
                  ? "bg-surface-2 font-medium text-foreground"
                  : "text-muted hover:bg-surface-2 hover:text-foreground",
              )}
            >
              <Shield className="h-4 w-4" />
              Admin
            </Link>
          )}
        </nav>
        <div className="space-y-1 border-t border-border p-3">
          <button
            onClick={() => setPaletteOpen(true)}
            className="flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-sm text-muted hover:bg-surface-2 hover:text-foreground"
          >
            <span className="flex items-center gap-2.5">
              <Command className="h-4 w-4" /> Commands
            </span>
            <kbd className="rounded border border-border bg-surface-2 px-1.5 text-[10px]">
              ⌘K
            </kbd>
          </button>
          <Link
            href="/settings"
            className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-muted hover:bg-surface-2 hover:text-foreground"
          >
            <Settings className="h-4 w-4" />
            Settings
          </Link>
          <div className="flex items-center justify-between px-2.5 py-1.5">
            <span className="truncate text-xs text-muted" title={user.username}>
              {user.display_name || user.username}
            </span>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Sign out"
              onClick={() => {
                void logout().then(() => router.push("/login"));
              }}
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-surface px-4 md:hidden">
        <Link href="/" className="flex items-center gap-2">
          <ZenMark />
          <span className="font-semibold">Zen</span>
        </Link>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Open commands"
          onClick={() => setPaletteOpen(true)}
        >
          <Command className="h-4 w-4" />
        </Button>
      </header>

      {/* Mobile bottom nav */}
      <nav
        className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-surface md:hidden"
        aria-label="Primary mobile"
      >
        {NAV.slice(0, 5).map(({ href, label, icon: Icon, exact }) => {
          const active = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px]",
                active ? "text-accent" : "text-muted",
              )}
            >
              <Icon className="h-5 w-5" />
              {label}
            </Link>
          );
        })}
      </nav>

      <main className="min-h-screen w-full pb-20 pt-14 md:pb-6 md:pl-56 md:pt-0">
        {children}
      </main>
      <CommandPalette />
    </div>
  );
}

function ZenMark() {
  return (
    <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-accent-foreground">
      <ZenLogo className="h-5 w-5" />
    </span>
  );
}
