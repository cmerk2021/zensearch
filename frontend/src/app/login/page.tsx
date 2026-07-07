"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AuthMethods, InstanceInfo } from "@/lib/types";
import { useAuth } from "@/stores/auth";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { ZenLogo } from "@/components/ui/logo";

export default function LoginPage() {
  return (
    <Suspense>
      <LoginContent />
    </Suspense>
  );
}

function LoginContent() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/";
  const { user, loaded, login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [method, setMethod] = useState<"local" | "ldap">("local");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const { data: instance } = useQuery({
    queryKey: ["instance"],
    queryFn: () => api.get<InstanceInfo>("/api/v1/meta/instance"),
  });
  const { data: methods } = useQuery({
    queryKey: ["auth-methods"],
    queryFn: () => api.get<AuthMethods>("/api/v1/auth/methods"),
  });

  useEffect(() => {
    if (instance?.bootstrap_required) router.replace("/setup");
  }, [instance?.bootstrap_required, router]);

  useEffect(() => {
    if (loaded && user) router.replace(next);
  }, [loaded, user, router, next]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(username, password, method);
      router.replace(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <ZenLogo className="h-7 w-7" />
          </span>
          <h1 className="text-xl font-semibold">{instance?.name ?? "Zen"}</h1>
          <p className="mt-1 text-sm text-muted">
            {instance?.tagline ?? "Search less. Find more."}
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4 rounded-2xl border border-border bg-surface p-6">
          {(methods?.local ?? true) && (
            <>
              <div>
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="username"
                  autoFocus
                  required
                />
              </div>
              <div>
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                />
              </div>
              {methods?.ldap && (
                <div className="flex items-center gap-3 text-xs text-muted">
                  <label className="flex items-center gap-1.5">
                    <input
                      type="radio"
                      checked={method === "local"}
                      onChange={() => setMethod("local")}
                    />
                    Local account
                  </label>
                  <label className="flex items-center gap-1.5">
                    <input
                      type="radio"
                      checked={method === "ldap"}
                      onChange={() => setMethod("ldap")}
                    />
                    LDAP
                  </label>
                </div>
              )}
              {error && <p className="text-xs text-danger">{error}</p>}
              <Button type="submit" className="w-full" disabled={busy}>
                {busy ? "Signing in…" : "Sign in"}
              </Button>
            </>
          )}

          {methods?.oidc && (
            <Button
              type="button"
              variant="outline"
              className="w-full"
              onClick={() => {
                window.location.href = "/api/v1/auth/oidc/login";
              }}
            >
              Continue with {methods.oidc_provider_name}
            </Button>
          )}
        </form>

        {methods?.registration === "open" && (
          <p className="mt-4 text-center text-xs text-muted">
            New here?{" "}
            <a href="/register" className="text-accent hover:underline">
              Create an account
            </a>
          </p>
        )}
      </div>
    </div>
  );
}
