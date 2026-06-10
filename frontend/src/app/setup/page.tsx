"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

export default function SetupPage() {
  const router = useRouter();
  const login = useAuth((state) => state.login);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await api.post("/api/v1/meta/setup", { username, password });
      await login(username, password);
      router.replace("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Setup failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-accent text-xl font-bold text-accent-foreground">
            禅
          </span>
          <h1 className="text-xl font-semibold">Welcome to Zen</h1>
          <p className="mt-1 text-sm text-muted">
            Create the administrator account to finish setup.
          </p>
        </div>
        <form onSubmit={submit} className="space-y-4 rounded-2xl border border-border bg-surface p-6">
          <div>
            <Label htmlFor="username">Admin username</Label>
            <Input
              id="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoFocus
              required
              minLength={2}
            />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={10}
            />
            <p className="mt-1 text-[11px] text-muted">At least 10 characters.</p>
          </div>
          <div>
            <Label htmlFor="confirm">Confirm password</Label>
            <Input
              id="confirm"
              type="password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              required
            />
          </div>
          {error && <p className="text-xs text-danger">{error}</p>}
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? "Creating…" : "Create admin account"}
          </Button>
        </form>
      </div>
    </div>
  );
}
