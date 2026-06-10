"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, Database, HardDrive, Users } from "lucide-react";
import { api } from "@/lib/api";
import type { ProviderHealth } from "@/lib/types";
import { Badge, Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Diagnostics {
  version: string;
  platform: string;
  database: { ok: boolean; backend: string };
  cache: { ok: boolean; backend: string };
  counts: Record<string, number>;
}

export default function AdminOverviewPage() {
  const { data: diagnostics } = useQuery({
    queryKey: ["admin-diagnostics"],
    queryFn: () => api.get<Diagnostics>("/api/v1/admin/diagnostics"),
    refetchInterval: 30_000,
  });

  const { data: health } = useQuery({
    queryKey: ["admin-provider-health"],
    queryFn: () => api.get<Record<string, ProviderHealth>>("/api/v1/admin/providers/health"),
    refetchInterval: 30_000,
  });

  const degraded = Object.values(health ?? {}).filter((entry) => entry.state !== "closed");

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<Users className="h-4 w-4" />}
          label="Users"
          value={diagnostics?.counts.users ?? "—"}
        />
        <StatCard
          icon={<Activity className="h-4 w-4" />}
          label="Searches recorded"
          value={diagnostics?.counts.searches ?? "—"}
        />
        <StatCard
          icon={<Database className="h-4 w-4" />}
          label={`Database (${diagnostics?.database.backend ?? "?"})`}
          value={diagnostics?.database.ok ? "Healthy" : "Down"}
          ok={diagnostics?.database.ok}
        />
        <StatCard
          icon={<HardDrive className="h-4 w-4" />}
          label={`Cache (${diagnostics?.cache.backend ?? "?"})`}
          value={diagnostics?.cache.ok ? "Healthy" : "Down"}
          ok={diagnostics?.cache.ok}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Provider health</CardTitle>
        </CardHeader>
        <CardContent>
          {degraded.length === 0 ? (
            <p className="text-sm text-success">All provider circuits closed (healthy).</p>
          ) : (
            <ul className="space-y-2">
              {degraded.map((entry) => (
                <li
                  key={entry.slug}
                  className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 text-sm"
                >
                  <span className="font-medium">{entry.slug}</span>
                  <Badge variant="warning">{entry.state}</Badge>
                  <span className="truncate text-xs text-muted">{entry.last_error}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {Object.values(health ?? {}).map((entry) => (
              <div
                key={entry.slug}
                className="rounded-lg border border-border px-3 py-2 text-xs"
              >
                <p className="font-medium">{entry.slug}</p>
                <p className="text-muted">
                  {(entry.success_rate * 100).toFixed(0)}% ok ·{" "}
                  {Math.round(entry.latency_ms_avg)}ms avg
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <p className="text-xs text-muted">
        Zen {diagnostics ? `· Python ${diagnostics.version} · ${diagnostics.platform}` : ""}
      </p>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  ok,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  ok?: boolean;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <span className="rounded-lg bg-surface-2 p-2 text-muted">{icon}</span>
        <div>
          <p className="text-xs text-muted">{label}</p>
          <p
            className={`text-sm font-semibold ${
              ok === false ? "text-danger" : ok ? "text-success" : ""
            }`}
          >
            {value}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
