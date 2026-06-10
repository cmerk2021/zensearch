"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/stores/auth";
import { AppShell } from "@/components/app-shell";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/admin", label: "Overview", exact: true },
  { href: "/admin/providers", label: "Providers" },
  { href: "/admin/profiles", label: "Profiles" },
  { href: "/admin/ranking", label: "Ranking" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/plugins", label: "Plugins" },
  { href: "/admin/ai", label: "AI" },
  { href: "/admin/settings", label: "Settings" },
  { href: "/admin/audit", label: "Audit" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell>
      <AdminGate>{children}</AdminGate>
    </AppShell>
  );
}

function AdminGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loaded } = useAuth();

  useEffect(() => {
    if (loaded && user && user.role !== "admin") router.replace("/");
  }, [loaded, user, router]);

  if (!user || user.role !== "admin") return null;

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8">
      <h1 className="mb-1 text-xl font-semibold">Administration</h1>
      <p className="mb-5 text-sm text-muted">
        Instance-wide configuration. Changes apply to all users.
      </p>
      <nav className="mb-6 flex flex-wrap gap-1 border-b border-border" aria-label="Admin">
        {TABS.map(({ href, label, exact }) => {
          const active = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "-mb-px border-b-2 px-3 py-2 text-sm transition-colors",
                active
                  ? "border-accent font-medium text-foreground"
                  : "border-transparent text-muted hover:text-foreground",
              )}
            >
              {label}
            </Link>
          );
        })}
      </nav>
      {children}
    </div>
  );
}
