"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select, Switch } from "@/components/ui/input";

export default function AdminSettingsPage() {
  const queryClient = useQueryClient();
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [dirty, setDirty] = useState<Record<string, unknown>>({});
  const [oidcSecret, setOidcSecret] = useState("");
  const [message, setMessage] = useState("");

  const { data: settings } = useQuery({
    queryKey: ["admin-settings"],
    queryFn: () => api.get<Record<string, unknown>>("/api/v1/admin/settings"),
  });

  useEffect(() => {
    if (settings) setValues(settings);
  }, [settings]);

  function set(key: string, value: unknown) {
    setValues((current) => ({ ...current, [key]: value }));
    setDirty((current) => ({ ...current, [key]: value }));
  }

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = { ...dirty };
      if (oidcSecret) payload["auth.oidc.client_secret"] = oidcSecret;
      return api.put("/api/v1/admin/settings", { values: payload });
    },
    onSuccess: () => {
      setMessage("Settings saved. They apply instance-wide immediately.");
      setDirty({});
      setOidcSecret("");
      void queryClient.invalidateQueries({ queryKey: ["admin-settings"] });
    },
    onError: (error) => setMessage((error as Error).message),
  });

  const str = (key: string) => String(values[key] ?? "");
  const bool = (key: string) => Boolean(values[key]);
  const num = (key: string) => Number(values[key] ?? 0);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Branding</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="inst-name">Instance name</Label>
            <Input
              id="inst-name"
              value={str("instance.name")}
              onChange={(event) => set("instance.name", event.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="inst-tagline">Tagline</Label>
            <Input
              id="inst-tagline"
              value={str("instance.tagline")}
              onChange={(event) => set("instance.tagline", event.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Authentication</CardTitle>
          <CardDescription>
            OIDC works with Authentik, Authelia, Keycloak and any standard provider.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm">Allow local username/password login</p>
            <Switch
              checked={bool("auth.allow_local_login")}
              onChange={(value) => set("auth.allow_local_login", value)}
              label="Local login"
            />
          </div>
          <div>
            <Label htmlFor="auth-reg">Registration</Label>
            <Select
              id="auth-reg"
              value={str("auth.registration")}
              onChange={(event) => set("auth.registration", event.target.value)}
            >
              <option value="closed">Closed — admins create accounts</option>
              <option value="open">Open — anyone can register</option>
            </Select>
          </div>
          <div className="flex items-center justify-between">
            <p className="text-sm">Enable OIDC single sign-on</p>
            <Switch
              checked={bool("auth.oidc.enabled")}
              onChange={(value) => set("auth.oidc.enabled", value)}
              label="OIDC"
            />
          </div>
          {bool("auth.oidc.enabled") && (
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="oidc-name">Provider display name</Label>
                <Input
                  id="oidc-name"
                  value={str("auth.oidc.provider_name")}
                  onChange={(event) => set("auth.oidc.provider_name", event.target.value)}
                  placeholder="Authentik"
                />
              </div>
              <div>
                <Label htmlFor="oidc-issuer">Issuer URL</Label>
                <Input
                  id="oidc-issuer"
                  value={str("auth.oidc.issuer")}
                  onChange={(event) => set("auth.oidc.issuer", event.target.value)}
                  placeholder="https://auth.example.com/application/o/zen/"
                />
              </div>
              <div>
                <Label htmlFor="oidc-client">Client ID</Label>
                <Input
                  id="oidc-client"
                  value={str("auth.oidc.client_id")}
                  onChange={(event) => set("auth.oidc.client_id", event.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="oidc-secret">
                  Client secret {str("auth.oidc.client_secret") && "(set)"}
                </Label>
                <Input
                  id="oidc-secret"
                  type="password"
                  value={oidcSecret}
                  onChange={(event) => setOidcSecret(event.target.value)}
                  placeholder={str("auth.oidc.client_secret") || "secret"}
                  autoComplete="off"
                />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Privacy</CardTitle>
          <CardDescription>
            These apply to every user. Privacy-mode searches are never recorded regardless.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm">Record search history</p>
            <Switch
              checked={bool("privacy.search_history_enabled")}
              onChange={(value) => set("privacy.search_history_enabled", value)}
              label="History"
            />
          </div>
          <div className="flex items-center justify-between">
            <p className="text-sm">Use result clicks as a ranking signal</p>
            <Switch
              checked={bool("privacy.click_tracking_enabled")}
              onChange={(value) => set("privacy.click_tracking_enabled", value)}
              label="Click signal"
            />
          </div>
          <div>
            <Label htmlFor="retention">History retention (days, 0 = forever)</Label>
            <Input
              id="retention"
              type="number"
              min={0}
              value={num("privacy.search_history_retention_days")}
              onChange={(event) =>
                set("privacy.search_history_retention_days", Number(event.target.value))
              }
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Search</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm">Safe search</p>
            <Switch
              checked={bool("search.safe_search")}
              onChange={(value) => set("search.safe_search", value)}
              label="Safe search"
            />
          </div>
          <div>
            <Label htmlFor="default-theme">Default theme for new users</Label>
            <Select
              id="default-theme"
              value={str("ui.default_theme")}
              onChange={(event) => set("ui.default_theme", event.target.value)}
            >
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
              <option value="amoled">AMOLED</option>
            </Select>
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center gap-3">
        <Button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending || (Object.keys(dirty).length === 0 && !oidcSecret)}
        >
          Save changes
        </Button>
        {message && <span className="text-xs text-muted">{message}</span>}
      </div>
    </div>
  );
}
