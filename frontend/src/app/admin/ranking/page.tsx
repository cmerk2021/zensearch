"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Ban, Pin, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import type { DomainRule } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardContent, EmptyState } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Select } from "@/components/ui/input";

const ACTION_META = {
  boost: { icon: ArrowUp, variant: "success" as const, label: "Boost" },
  lower: { icon: ArrowDown, variant: "warning" as const, label: "Lower" },
  pin: { icon: Pin, variant: "accent" as const, label: "Pin" },
  block: { icon: Ban, variant: "danger" as const, label: "Block" },
};

export default function AdminRankingPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [domain, setDomain] = useState("");
  const [action, setAction] = useState<keyof typeof ACTION_META>("boost");
  const [weight, setWeight] = useState("1.5");

  const { data: rules } = useQuery({
    queryKey: ["admin-domain-rules"],
    queryFn: () => api.get<DomainRule[]>("/api/v1/admin/domain-rules"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post("/api/v1/admin/domain-rules", {
        domain,
        action,
        weight: parseFloat(weight) || 1.0,
        scope: "instance",
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-domain-rules"] });
      setShowCreate(false);
      setDomain("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/admin/domain-rules/${id}`),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin-domain-rules"] }),
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">
          Domain rules shape ranking for every user: boost quality sources, bury content
          farms, pin documentation, block spam. Rules match subdomains automatically.
        </p>
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" /> Add rule
        </Button>
      </div>

      {rules && rules.length === 0 && (
        <EmptyState
          title="No domain rules"
          description="Example: boost docs.python.org, block pinterest.com."
        />
      )}

      <div className="space-y-1.5">
        {rules?.map((rule) => {
          const meta = ACTION_META[rule.action];
          const Icon = meta.icon;
          return (
            <Card key={rule.id}>
              <CardContent className="flex items-center gap-3 p-3">
                <Badge variant={meta.variant}>
                  <Icon className="h-3 w-3" /> {meta.label}
                </Badge>
                <span className="flex-1 truncate font-mono text-sm">{rule.domain}</span>
                {(rule.action === "boost" || rule.action === "lower") && (
                  <span className="text-xs text-muted">×{rule.weight.toFixed(1)}</span>
                )}
                <Badge variant="outline">{rule.scope}</Badge>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Delete rule"
                  onClick={() => deleteMutation.mutate(rule.id)}
                >
                  <Trash2 className="h-4 w-4 text-danger" />
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Dialog open={showCreate} onClose={() => setShowCreate(false)} title="Add domain rule">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            createMutation.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="rule-domain">Domain</Label>
            <Input
              id="rule-domain"
              value={domain}
              onChange={(event) => setDomain(event.target.value)}
              placeholder="docs.python.org"
              autoFocus
              required
            />
          </div>
          <div>
            <Label htmlFor="rule-action">Action</Label>
            <Select
              id="rule-action"
              value={action}
              onChange={(event) => setAction(event.target.value as keyof typeof ACTION_META)}
            >
              <option value="boost">Boost — rank higher</option>
              <option value="lower">Lower — rank lower</option>
              <option value="pin">Pin — always at top</option>
              <option value="block">Block — never shown</option>
            </Select>
          </div>
          {(action === "boost" || action === "lower") && (
            <div>
              <Label htmlFor="rule-weight">
                Multiplier ({action === "boost" ? "> 1" : "0 – 1"})
              </Label>
              <Input
                id="rule-weight"
                type="number"
                step="0.1"
                min="0"
                max="10"
                value={weight}
                onChange={(event) => setWeight(event.target.value)}
              />
            </div>
          )}
          {createMutation.isError && (
            <p className="text-xs text-danger">{(createMutation.error as Error).message}</p>
          )}
          <Button type="submit" className="w-full" disabled={createMutation.isPending}>
            Add rule
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
