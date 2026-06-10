"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AuthMethods } from "@/lib/types";
import { useAuth } from "@/stores/auth";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

export default function RegisterPage() {
  const router = useRouter();
  const load = useAuth((state) => state.load);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const { data: methods } = useQuery({
    queryKey: ["auth-methods"],
    queryFn: () => api.get<AuthMethods>("/api/v1/auth/methods"),
  });

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.post("/api/v1/auth/register", { username, password });
      await load();
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    } finally {
      setBusy(false);
    }
  }

  if (methods && methods.registration !== "open") {
    return (
      <div className="flex min-h-screen items-center justify-center px-4 text-center">
        <div>
          <p className="text-sm">Registration is closed on this instance.</p>
          <a href="/login" className="mt-2 inline-block text-sm text-accent hover:underline">
            Back to sign in
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="mb-6 text-center text-xl font-semibold">Create your account</h1>
        <form onSubmit={submit} className="space-y-4 rounded-2xl border border-border bg-surface p-6">
          <div>
            <Label htmlFor="username">Username</Label>
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
          {error && <p className="text-xs text-danger">{error}</p>}
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? "Creating…" : "Create account"}
          </Button>
        </form>
      </div>
    </div>
  );
}
