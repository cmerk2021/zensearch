# Installation

Zen ships as two containers: `zen-server` (API) and `zen-web` (UI). The
recommended path is Docker Compose.

## Requirements

- Docker Engine 24+ with the compose plugin (or Podman 4+, see below)
- 512 MB RAM minimum (1 GB+ recommended with PostgreSQL)
- amd64 or arm64 (Raspberry Pi 4/5 works)

## Quick start (recommended: PostgreSQL + Redis)

```bash
mkdir zen && cd zen
curl -fsSLO https://raw.githubusercontent.com/zensearch/zen/main/deploy/compose/docker-compose.yml
curl -fsSL  https://raw.githubusercontent.com/zensearch/zen/main/deploy/compose/.env.example -o .env

# Edit .env — set ZEN_SECRET_KEY and POSTGRES_PASSWORD:
python -c "import secrets; print(secrets.token_urlsafe(48))"   # secret key

docker compose up -d
```

Open `http://your-host:3000`. The first visit shows the **setup page** where
you create the administrator account. That's it.

## Minimal install (SQLite, no Redis)

For evaluation or a single user on constrained hardware:

```bash
curl -fsSLO https://raw.githubusercontent.com/zensearch/zen/main/deploy/compose/docker-compose.minimal.yml
# set ZEN_SECRET_KEY in .env as above
docker compose -f docker-compose.minimal.yml up -d
```

This runs one app container with an SQLite volume and an in-process cache.
You can migrate to PostgreSQL later (see the [admin backup guide](../admin/backups.md)).

## Podman

The compose files are podman-compatible:

```bash
podman compose -f docker-compose.yml up -d
```

## Kubernetes

A single-file manifest for k3s-class clusters is provided at
[deploy/kubernetes/zen.yaml](../../deploy/kubernetes/zen.yaml). Create the
namespace + secret as documented in the file header, adjust the Ingress host,
then `kubectl apply -f zen.yaml`.

## Reverse proxy / HTTPS

Zen should be served over HTTPS. Example configs for Nginx, Caddy and Traefik
are in [deploy/reverse-proxy/](../../deploy/reverse-proxy/). Two environment
variables matter:

| Variable | Purpose |
|---|---|
| `ZEN_BASE_URL` | Public URL (`https://zen.example.com`) — required for OIDC |
| `ZEN_TRUSTED_PROXIES` | Proxy IPs/CIDRs whose `X-Forwarded-For` is trusted |

## First-run checklist

1. Create the admin account on the setup page.
2. **Admin → Providers** — enable/disable providers; add API keys for Brave
   (free tier) or Kagi if you have them.
3. **Admin → Settings** — branding, registration policy, privacy settings.
4. **Admin → AI** (optional) — point Zen at Ollama or another backend.
5. Create your first workspace and start researching.

## Updating

```bash
docker compose pull
docker compose up -d
```

Database migrations run automatically via the `zen-migrate` one-shot service.
Always read the release notes before major-version updates.
