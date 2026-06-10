"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers, Plus, Sparkles, Trash2 } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Bookmark, Collection } from "@/lib/types";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Badge, EmptyState } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Select } from "@/components/ui/input";

export default function CollectionsPage() {
  return (
    <AppShell>
      <CollectionsContent />
    </AppShell>
  );
}

const SMART_FIELDS = [
  { value: "domain", label: "Domain" },
  { value: "title", label: "Title" },
  { value: "url", label: "URL" },
  { value: "source_provider", label: "Source provider" },
  { value: "tag", label: "Tag" },
];

const SMART_OPERATORS = [
  { value: "equals", label: "equals" },
  { value: "contains", label: "contains" },
  { value: "starts_with", label: "starts with" },
  { value: "ends_with", label: "ends with" },
];

function CollectionsContent() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [isSmart, setIsSmart] = useState(false);
  const [ruleField, setRuleField] = useState("domain");
  const [ruleOperator, setRuleOperator] = useState("contains");
  const [ruleValue, setRuleValue] = useState("");

  const { data: collections } = useQuery({
    queryKey: ["collections"],
    queryFn: () => api.get<Collection[]>("/api/v1/collections"),
  });

  const { data: contents } = useQuery({
    queryKey: ["collection-bookmarks", selected],
    queryFn: () => api.get<Bookmark[]>(`/api/v1/collections/${selected}/bookmarks`),
    enabled: !!selected,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post("/api/v1/collections", {
        name,
        is_smart: isSmart,
        rules: isSmart
          ? {
              match: "all",
              conditions: [{ field: ruleField, operator: ruleOperator, value: ruleValue }],
            }
          : undefined,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["collections"] });
      setShowCreate(false);
      setName("");
      setIsSmart(false);
      setRuleValue("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/collections/${id}`),
    onSuccess: () => {
      setSelected(null);
      void queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
  });

  const selectedCollection = collections?.find((collection) => collection.id === selected);

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Collections</h1>
          <p className="text-sm text-muted">
            Curated groups of sources. Smart collections fill themselves by rule.
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" /> New collection
        </Button>
      </div>

      {collections && collections.length === 0 && (
        <EmptyState
          icon={<Layers className="h-8 w-8" />}
          title="No collections"
          description="Create “Read Later”, “Homelab”, or a smart collection that auto-collects by domain."
        />
      )}

      <div className="grid gap-6 md:grid-cols-[240px,1fr]">
        <div className="space-y-1">
          {collections?.map((collection) => (
            <button
              key={collection.id}
              onClick={() => setSelected(collection.id)}
              className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${
                selected === collection.id ? "bg-surface-2 font-medium" : "hover:bg-surface-2"
              }`}
            >
              {collection.is_smart ? (
                <Sparkles className="h-4 w-4 text-accent" />
              ) : (
                <Layers className="h-4 w-4 text-muted" />
              )}
              <span className="truncate">{collection.name}</span>
            </button>
          ))}
        </div>

        <div>
          {selectedCollection ? (
            <>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-sm font-semibold">
                  {selectedCollection.name}
                  {selectedCollection.is_smart && <Badge variant="accent">smart</Badge>}
                </h2>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Delete collection"
                  onClick={() => {
                    if (confirm("Delete this collection? Bookmarks are kept.")) {
                      deleteMutation.mutate(selectedCollection.id);
                    }
                  }}
                >
                  <Trash2 className="h-4 w-4 text-danger" />
                </Button>
              </div>
              <ul className="space-y-2">
                {contents?.map((bookmark) => (
                  <li key={bookmark.id} className="rounded-lg border border-border bg-surface px-3 py-2">
                    <a
                      href={bookmark.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-accent hover:underline"
                    >
                      {bookmark.title || bookmark.url}
                    </a>
                    <p className="text-xs text-muted">{bookmark.domain}</p>
                  </li>
                ))}
                {contents && contents.length === 0 && (
                  <p className="py-8 text-center text-xs text-muted">
                    {selectedCollection.is_smart
                      ? "No bookmarks match this collection's rules yet."
                      : "Empty. Add bookmarks from the bookmarks page or search results."}
                  </p>
                )}
              </ul>
            </>
          ) : (
            <p className="py-12 text-center text-sm text-muted">Select a collection.</p>
          )}
        </div>
      </div>

      <Dialog open={showCreate} onClose={() => setShowCreate(false)} title="New collection">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            createMutation.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="col-name">Name</Label>
            <Input
              id="col-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Read Later"
              autoFocus
              required
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={isSmart}
              onChange={(event) => setIsSmart(event.target.checked)}
            />
            Smart collection (auto-populates by rule)
          </label>
          {isSmart && (
            <div className="grid grid-cols-3 gap-2">
              <Select value={ruleField} onChange={(event) => setRuleField(event.target.value)}>
                {SMART_FIELDS.map((field) => (
                  <option key={field.value} value={field.value}>
                    {field.label}
                  </option>
                ))}
              </Select>
              <Select
                value={ruleOperator}
                onChange={(event) => setRuleOperator(event.target.value)}
              >
                {SMART_OPERATORS.map((operator) => (
                  <option key={operator.value} value={operator.value}>
                    {operator.label}
                  </option>
                ))}
              </Select>
              <Input
                value={ruleValue}
                onChange={(event) => setRuleValue(event.target.value)}
                placeholder="github.com"
                required={isSmart}
              />
            </div>
          )}
          {createMutation.isError && (
            <p className="text-xs text-danger">{(createMutation.error as Error).message}</p>
          )}
          <Button type="submit" className="w-full" disabled={createMutation.isPending}>
            Create
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
