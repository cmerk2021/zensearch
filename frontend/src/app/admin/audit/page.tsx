"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, qs } from "@/lib/api";
import type { AuditEntry, Page } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/card";

export default function AdminAuditPage() {
  const [page, setPage] = useState(1);

  const { data } = useQuery({
    queryKey: ["admin-audit", page],
    queryFn: () => api.get<Page<AuditEntry>>(`/api/v1/admin/audit${qs({ page, size: 50 })}`),
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.size)) : 1;

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">
        Security-relevant actions: logins, settings changes, user and plugin management.
      </p>
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border bg-surface-2 text-xs text-muted">
            <tr>
              <th className="px-4 py-2 font-medium">Time</th>
              <th className="px-4 py-2 font-medium">Action</th>
              <th className="px-4 py-2 font-medium">Target</th>
              <th className="px-4 py-2 font-medium">IP</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((entry) => (
              <tr key={entry.id} className="border-b border-border last:border-0">
                <td className="whitespace-nowrap px-4 py-2 text-xs text-muted">
                  {new Date(entry.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-2">
                  <Badge variant="outline">{entry.action}</Badge>
                </td>
                <td className="px-4 py-2 text-xs">
                  {entry.target_type && `${entry.target_type}:${entry.target_id.slice(0, 8)}`}
                </td>
                <td className="px-4 py-2 text-xs text-muted">{entry.ip_address}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 text-sm">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Previous
          </Button>
          <span className="text-muted">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
