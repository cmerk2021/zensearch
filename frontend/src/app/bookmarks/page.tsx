"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookMarked, Heart, Plus, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { api, qs } from "@/lib/api";
import type { Bookmark, Page } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Badge, EmptyState, Spinner } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label } from "@/components/ui/input";

export default function BookmarksPage() {
  return (
    <AppShell>
      <BookmarksContent />
    </AppShell>
  );
}

function BookmarksContent() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [newUrl, setNewUrl] = useState("");
  const [newTitle, setNewTitle] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["bookmarks", { query, page, favoritesOnly }],
    queryFn: () =>
      api.get<Page<Bookmark>>(
        `/api/v1/bookmarks${qs({ q: query || undefined, page, favorites: favoritesOnly || undefined, size: 25 })}`,
      ),
  });

  const addMutation = useMutation({
    mutationFn: () => api.post("/api/v1/bookmarks", { url: newUrl, title: newTitle }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["bookmarks"] });
      setShowAdd(false);
      setNewUrl("");
      setNewTitle("");
    },
  });

  const favoriteMutation = useMutation({
    mutationFn: ({ id, value }: { id: string; value: boolean }) =>
      api.patch(`/api/v1/bookmarks/${id}`, { is_favorite: value }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["bookmarks"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/bookmarks/${id}`),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["bookmarks"] }),
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.size)) : 1;

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Bookmarks</h1>
          <p className="text-sm text-muted">{data?.total ?? 0} saved sources</p>
        </div>
        <div className="flex gap-2">
          <a href="/api/v1/bookmarks/export.html" download>
            <Button variant="outline" size="sm">Export</Button>
          </a>
          <Button size="sm" onClick={() => setShowAdd(true)}>
            <Plus className="h-4 w-4" /> Add
          </Button>
        </div>
      </div>

      <div className="mb-4 flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted" />
          <Input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder="Filter bookmarks…"
            className="pl-9"
          />
        </div>
        <Button
          variant={favoritesOnly ? "primary" : "outline"}
          size="icon"
          aria-label="Favorites only"
          onClick={() => {
            setFavoritesOnly(!favoritesOnly);
            setPage(1);
          }}
        >
          <Heart className="h-4 w-4" />
        </Button>
      </div>

      {isLoading && (
        <div className="flex justify-center py-10">
          <Spinner className="h-6 w-6" />
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState
          icon={<BookMarked className="h-8 w-8" />}
          title="No bookmarks"
          description="Save results from search, or add URLs manually."
        />
      )}

      <ul className="space-y-2">
        {data?.items.map((bookmark) => (
          <li
            key={bookmark.id}
            className="group rounded-xl border border-border bg-surface px-4 py-3"
          >
            <div className="flex items-center gap-2 text-xs text-muted">
              {bookmark.favicon_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={bookmark.favicon_url} alt="" width={14} height={14} className="rounded" />
              )}
              <span>{bookmark.domain}</span>
              <span>·</span>
              <span>{timeAgo(bookmark.created_at)}</span>
              {bookmark.source_provider && (
                <Badge variant="outline">via {bookmark.source_provider}</Badge>
              )}
              <span className="ml-auto flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                <button
                  onClick={() =>
                    favoriteMutation.mutate({ id: bookmark.id, value: !bookmark.is_favorite })
                  }
                  aria-label="Toggle favorite"
                  className="rounded p-1 hover:bg-surface-2"
                >
                  <Heart
                    className={`h-3.5 w-3.5 ${bookmark.is_favorite ? "fill-danger text-danger" : ""}`}
                  />
                </button>
                <button
                  onClick={() => deleteMutation.mutate(bookmark.id)}
                  aria-label="Delete bookmark"
                  className="rounded p-1 hover:bg-surface-2"
                >
                  <Trash2 className="h-3.5 w-3.5 text-danger" />
                </button>
              </span>
            </div>
            <a
              href={bookmark.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-0.5 block text-sm font-medium text-accent hover:underline"
            >
              {bookmark.title || bookmark.url}
            </a>
            {bookmark.snippet && (
              <p className="mt-0.5 line-clamp-2 text-xs text-muted">{bookmark.snippet}</p>
            )}
            {bookmark.tags.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {bookmark.tags.map((tag) => (
                  <Badge key={tag.id}>{tag.name}</Badge>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>

      {totalPages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-3 text-sm">
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

      <Dialog open={showAdd} onClose={() => setShowAdd(false)} title="Add bookmark">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            addMutation.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="bm-url">URL</Label>
            <Input
              id="bm-url"
              type="url"
              value={newUrl}
              onChange={(event) => setNewUrl(event.target.value)}
              placeholder="https://…"
              autoFocus
              required
            />
          </div>
          <div>
            <Label htmlFor="bm-title">Title (optional)</Label>
            <Input
              id="bm-title"
              value={newTitle}
              onChange={(event) => setNewTitle(event.target.value)}
            />
          </div>
          {addMutation.isError && (
            <p className="text-xs text-danger">{(addMutation.error as Error).message}</p>
          )}
          <Button type="submit" className="w-full" disabled={addMutation.isPending}>
            Save
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
