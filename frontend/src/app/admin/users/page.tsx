"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, ShieldCheck, UserX } from "lucide-react";
import { useState } from "react";
import { api, qs } from "@/lib/api";
import type { Page, User } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Select } from "@/components/ui/input";

export default function AdminUsersPage() {
  const queryClient = useQueryClient();
  const me = useAuth((state) => state.user);
  const [page, setPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("user");

  const { data } = useQuery({
    queryKey: ["admin-users", page],
    queryFn: () => api.get<Page<User>>(`/api/v1/admin/users${qs({ page, size: 25 })}`),
  });

  const createMutation = useMutation({
    mutationFn: () => api.post("/api/v1/admin/users", { username, password, role }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      setShowCreate(false);
      setUsername("");
      setPassword("");
      setRole("user");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.patch(`/api/v1/admin/users/${id}`, body),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.size)) : 1;

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" /> New user
        </Button>
      </div>

      {data?.items.map((user) => (
        <Card key={user.id}>
          <CardContent className="flex flex-wrap items-center gap-3 p-4">
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-2 text-sm font-medium">
                {user.username}
                {user.id === me?.id && <Badge variant="outline">you</Badge>}
                {!user.is_active && <Badge variant="danger">disabled</Badge>}
                <Badge variant="outline">{user.auth_source}</Badge>
              </p>
              <p className="text-xs text-muted">
                Last login {user.last_login_at ? timeAgo(user.last_login_at) : "never"}
              </p>
            </div>
            <Select
              value={user.role}
              onChange={(event) =>
                updateMutation.mutate({ id: user.id, body: { role: event.target.value } })
              }
              aria-label={`Role for ${user.username}`}
              className="w-32"
              disabled={user.id === me?.id}
            >
              <option value="admin">Admin</option>
              <option value="user">User</option>
              <option value="readonly">Read-only</option>
            </Select>
            <Button
              variant="ghost"
              size="icon"
              aria-label={user.is_active ? "Disable account" : "Enable account"}
              title={user.is_active ? "Disable account" : "Enable account"}
              disabled={user.id === me?.id}
              onClick={() =>
                updateMutation.mutate({ id: user.id, body: { is_active: !user.is_active } })
              }
            >
              {user.is_active ? (
                <UserX className="h-4 w-4 text-danger" />
              ) : (
                <ShieldCheck className="h-4 w-4 text-success" />
              )}
            </Button>
          </CardContent>
        </Card>
      ))}

      {updateMutation.isError && (
        <p className="text-xs text-danger">{(updateMutation.error as Error).message}</p>
      )}

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

      <Dialog open={showCreate} onClose={() => setShowCreate(false)} title="Create user">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            createMutation.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="new-username">Username</Label>
            <Input
              id="new-username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoFocus
              required
              minLength={2}
            />
          </div>
          <div>
            <Label htmlFor="new-password">Password</Label>
            <Input
              id="new-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={10}
            />
          </div>
          <div>
            <Label htmlFor="new-role">Role</Label>
            <Select id="new-role" value={role} onChange={(event) => setRole(event.target.value)}>
              <option value="user">User</option>
              <option value="admin">Admin</option>
              <option value="readonly">Read-only</option>
            </Select>
          </div>
          {createMutation.isError && (
            <p className="text-xs text-danger">{(createMutation.error as Error).message}</p>
          )}
          <Button type="submit" className="w-full" disabled={createMutation.isPending}>
            Create user
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
