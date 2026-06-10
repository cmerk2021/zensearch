# Changelog

All notable changes to Zen are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and Zen adheres to
[semantic versioning](https://semver.org/).

## [0.9.0] — 2026-06-09

First public release candidate.

### Added

**Search**
- Provider framework with 12 built-in providers: Google, Bing, DuckDuckGo,
  Brave (API + scrape), Startpage, Kagi (API), Mojeek, Wikipedia, GitHub,
  Reddit, Stack Overflow, YouTube
- Concurrent execution with per-provider timeout envelopes, single-retry
  policy, circuit breakers, and scheduled health probes
- Result pipeline: normalization, tracking-param stripping, URL
  canonicalization, cross-provider dedup/merge, favicon proxying
- Reciprocal Rank Fusion ranking with configurable factor weights, provider
  weights, and domain rules (boost / lower / pin / block) at instance,
  profile, and user scope
- Search modes: Normal, Privacy (zero retention), Focus (distraction
  filtering), Research (workspace capture)
- Admin-managed search profiles with six seeded presets
- 20+ built-in bangs, admin-defined custom bangs, plugin bangs
- History-based suggestions, result-set caching, click signals

**Knowledge**
- Research workspaces with overview, export (Markdown zip + JSON), archival
- Unified bookmarks with search provenance and URL-level dedup
- Manual collections and rule-based smart collections
- Hierarchical tags shared across bookmarks and notes
- Markdown notes with revision history, restore, pinning, and
  note↔bookmark/note linking
- Personal takeout export and Netscape bookmark export

**AI (optional)**
- Backends: Ollama, LM Studio, OpenAI-compatible, OpenRouter
- Capabilities: query expansion, cited result summaries, workspace digests,
  long-form reports, knowledge maps
- Admin connectivity testing and model discovery

**Platform**
- Plugin SDK 1.0: search providers, rankers, bangs, themes, exporters, AI
  backends, widgets; permission-gated capability API
- Plugin repositories (official/community/private) with checksum-verified
  installs, dependency resolution, updates, and rollback
- Authentication: local (argon2id), OIDC with PKCE (Authentik/Authelia/
  Keycloak), LDAP; roles admin/user/readonly
- Session management with revocation, sliding expiry, CSRF protection
- Three-layer configuration: env vars → DB-backed instance settings (with
  encrypted secrets) → user preferences
- Admin dashboard: providers, profiles, ranking, users, plugins, AI,
  settings, audit log, diagnostics
- Observability: structured JSON logs, Prometheus metrics, health/readiness
  endpoints
- In-process scheduler with cache-based leader election: session purging,
  history retention, provider probes, repository sync
- CLI: serve, doctor, db, users, settings, plugins
- First-run setup page; idempotent bootstrap seeding

**Frontend**
- Next.js app: search with suggestions and mode pills, workspaces, bookmarks,
  collections, notes editor with autosave, tags, history, settings
- Command palette (⌘K), `/` to search, full keyboard navigation
- Light / dark / AMOLED themes, mobile bottom navigation, accessibility
  labels throughout

**Deployment**
- Multi-arch (amd64/arm64) non-root Docker images
- Compose files: full (PostgreSQL+Redis) and minimal (SQLite)
- Kubernetes manifest, Nginx/Caddy/Traefik examples
- CI: lint, 133-test suite, PostgreSQL migration round-trip, frontend
  typecheck/build, Docker build smoke
- Release automation with version validation and changelog generation
