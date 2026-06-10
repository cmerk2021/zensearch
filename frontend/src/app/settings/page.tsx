"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, KeyRound, Monitor, Moon, Smartphone, Sun } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import type { SearchProfile, UserSession } from "@/lib/types";
import { cn, timeAgo } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select, Switch } from "@/components/ui/input";

const THEMES = [
  { value: "system", label: "System", icon: Monitor },
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "amoled", label: "AMOLED", icon: Smartphone },
] as const;

export default function SettingsPage() {
  return (
    <AppShell>
      <SettingsContent />
    </AppShell>
  );
}

function SettingsContent() {
  const { user, preferences, setPreferences } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");

  const { data: profiles } = useQuery({
    queryKey: ["profiles"],
    queryFn: () => api.get<SearchProfile[]>("/api/v1/profiles"),
  });

  const { data: sessions, refetch: refetchSessions } = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api.get<UserSession[]>("/api/v1/auth/sessions"),
  });

  const passwordMutation = useMutation({
    mutationFn: () =>
      api.post("/api/v1/auth/password", {
        current_password: currentPassword,
        new_password: newPassword,
      }),
    onSuccess: () => {
      setPasswordMessage("Password updated.");
      setCurrentPassword("");
      setNewPassword("");
    },
    onError: (error) => setPasswordMessage((error as Error).message),
  });

  if (!preferences || !user) return null;

  return (
    <div className="mx-auto w-full max-w-2xl space-y-6 px-4 py-8">
      <h1 className="text-xl font-semibold">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
          <CardDescription>Personal — synchronizes across your devices.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>Theme</Label>
            <div className="flex gap-2">
              {THEMES.map(({ value, label, icon: Icon }) => (
                <button
                  key={value}
                  onClick={() => void setPreferences({ theme: value })}
                  aria-pressed={preferences.theme === value}
                  className={cn(
                    "flex flex-1 flex-col items-center gap-1.5 rounded-xl border p-3 text-xs transition-colors",
                    preferences.theme === value
                      ? "border-accent bg-accent/10 text-accent"
                      : "border-border text-muted hover:bg-surface-2",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm">Open results in a new tab</p>
              <p className="text-xs text-muted">Keeps your search page in place.</p>
            </div>
            <Switch
              checked={preferences.open_links_new_tab}
              onChange={(value) => void setPreferences({ open_links_new_tab: value })}
              label="Open links in new tab"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Search defaults</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="default-mode">Default mode</Label>
            <Select
              id="default-mode"
              value={preferences.default_mode}
              onChange={(event) =>
                void setPreferences({ default_mode: event.target.value as any })
              }
            >
              <option value="normal">Normal</option>
              <option value="privacy">Privacy</option>
              <option value="focus">Focus</option>
              <option value="research">Research</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="default-profile">Default profile</Label>
            <Select
              id="default-profile"
              value={preferences.default_profile_id ?? ""}
              onChange={(event) =>
                void setPreferences({ default_profile_id: event.target.value || null })
              }
            >
              <option value="">Instance default</option>
              {profiles?.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      {user.auth_source === "local" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <KeyRound className="h-4 w-4" /> Password
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                passwordMutation.mutate();
              }}
              className="space-y-3"
            >
              <div>
                <Label htmlFor="current-pw">Current password</Label>
                <Input
                  id="current-pw"
                  type="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                />
              </div>
              <div>
                <Label htmlFor="new-pw">New password</Label>
                <Input
                  id="new-pw"
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  autoComplete="new-password"
                  minLength={10}
                  required
                />
              </div>
              {passwordMessage && <p className="text-xs text-muted">{passwordMessage}</p>}
              <Button type="submit" disabled={passwordMutation.isPending}>
                Update password
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Sessions</CardTitle>
          <CardDescription>Devices currently signed in to your account.</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {sessions?.map((session) => (
              <li
                key={session.id}
                className="flex items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-xs"
              >
                <div className="min-w-0">
                  <p className="truncate">{session.user_agent || "Unknown device"}</p>
                  <p className="text-muted">
                    {session.ip_address} · active {timeAgo(session.last_seen_at)}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    void api
                      .delete(`/api/v1/auth/sessions/${session.id}`)
                      .then(() => refetchSessions())
                  }
                >
                  Revoke
                </Button>
              </li>
            ))}
          </ul>
          <Button
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() =>
              void api.post("/api/v1/auth/sessions/revoke-all").then(() => refetchSessions())
            }
          >
            Sign out everywhere else
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Your data</CardTitle>
          <CardDescription>
            Export everything you have stored in Zen — workspaces, bookmarks, notes.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <a href="/api/v1/me/export.json" download="zen-takeout.json">
            <Button variant="outline" size="sm">
              <Download className="h-4 w-4" /> Download takeout (JSON)
            </Button>
          </a>
        </CardContent>
      </Card>
    </div>
  );
}
