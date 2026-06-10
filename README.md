<p align="center">
  <strong>禅</strong>
</p>

<h1 align="center">Zen</h1>
<p align="center"><em>Search less. Find more.</em></p>

<p align="center">
  Self-hosted, privacy-first research and knowledge discovery platform<br/>
  for homelabs, families, and small teams.
</p>

---

Most search engines are built to maximize engagement. **Zen is built to
maximize clarity.** It aggregates results from many providers into one calm,
fast, keyboard-first interface — and then closes the loop that every other
tool leaves open: searches become saved sources, sources become notes,
notes become knowledge you can actually find again.

Search is one feature. **Knowledge discovery is the product.**

## What you get

- **Multi-source search** — Google, Bing, DuckDuckGo, Brave, Startpage, Kagi,
  Mojeek, Wikipedia, GitHub, Reddit, Stack Overflow, YouTube. Queried
  concurrently; one dead provider never breaks your search (circuit breakers
  + health probes included).
- **Search modes** — *Normal*, *Privacy* (zero retention, visibly), *Focus*
  (social/shopping/entertainment removed), *Research* (everything captured to
  a workspace).
- **Research workspaces** — searches, bookmarks, and notes live together per
  project, exportable as Markdown + JSON.
- **Knowledge management** — unified bookmarks with search provenance, manual
  and rule-based smart collections, hierarchical tags, Markdown notes with
  revision history and linking.
- **Kagi-style ranking control, self-hosted** — boost, lower, pin, or block
  domains instance-wide, per profile, or per user. Reciprocal Rank Fusion
  under the hood, fully configurable.
- **Search profiles** — admin-curated presets (Engineering, Research,
  Homelab, Academic, Privacy…) users switch with one click, synced across
  devices.
- **Optional local-first AI** — query expansion, cited result summaries,
  workspace digests/reports, knowledge maps. Ollama, LM Studio, any
  OpenAI-compatible endpoint, or OpenRouter. Zen is 100% functional with AI
  off.
- **Plugin platform** — installable providers, rankers, bangs, themes,
  exporters and AI backends from official/community/private repositories,
  with checksums, versioning, and one-click rollback.
- **Admin dashboard** — providers, profiles, ranking rules, users, plugins,
  AI, privacy policy, audit log, live health. Zero YAML.
- **Privacy by architecture** — no telemetry, no tracking, documented egress,
  encrypted secrets, and a privacy mode you can trust because you host it.

## Quick start

```bash
mkdir zen && cd zen
curl -fsSLO https://raw.githubusercontent.com/cmerk2021/zensearch/main/deploy/compose/docker-compose.yml
curl -fsSL  https://raw.githubusercontent.com/cmerk2021/zensearch/main/deploy/compose/.env.example -o .env
# edit .env: set ZEN_SECRET_KEY (python -c "import secrets; print(secrets.token_urlsafe(48))")
docker compose up -d
```

Open `http://your-host:3000`, create the admin account on the setup page,
and start searching. Raspberry Pi-class hardware is fine — there's also a
[single-container SQLite variant](deploy/compose/docker-compose.minimal.yml).

Full guides: [Installation](docs/user/installation.md) ·
[Usage](docs/user/usage.md) · [Administration](docs/admin/administration.md) ·
[AI setup](docs/user/ai.md)

## How it compares

| | SearXNG | Whoogle | Kagi | Perplexity | **Zen** |
|---|---|---|---|---|---|
| Self-hosted | ✅ | ✅ | ❌ | ❌ | ✅ |
| Multi-provider | ✅ | ❌ | ✅ | ✅ | ✅ |
| Accounts & sync | ❌ | ❌ | ✅ | ✅ | ✅ |
| Workspaces / notes / bookmarks | ❌ | ❌ | ❌ | partial | ✅ |
| Ranking control (pin/block/boost) | ❌ | ❌ | ✅ | ❌ | ✅ |
| Admin web UI | ❌ | ❌ | n/a | n/a | ✅ |
| Local AI integration | ❌ | ❌ | ❌ | ❌ | ✅ |
| Installable plugins | ❌ | ❌ | ❌ | ❌ | ✅ |

The full [competitive analysis](docs/product/competitive-analysis.md) explains
the positioning.

## Stack

FastAPI + SQLAlchemy (async) + PostgreSQL/SQLite + Redis (optional) on the
backend; Next.js + Tailwind on the frontend. Multi-arch images (amd64/arm64),
non-root containers, Prometheus metrics, structured logs.
[Architecture overview](docs/architecture/overview.md) ·
[ADRs](docs/architecture/decisions/README.md)

## Extending Zen

Write a provider in ~40 lines of Python and ship it through a plugin
repository — see the [Plugin SDK guide](docs/developer/plugin-sdk.md).

## Contributing

PRs welcome. Start with [contributing guide](docs/developer/contributing.md).
Good first contributions: new search providers, themes, translations of docs.

## License

[AGPL-3.0](LICENSE) — Zen is free software; if you run a modified version as
a service, share your changes.
