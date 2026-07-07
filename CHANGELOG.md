# Changelog

All notable changes to Zen are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and Zen adheres to
[semantic versioning](https://semver.org/).

## [0.11.0] — 2026-07-07

### Added

- **Per-user AI access.** AI is now gated per account in addition to the
  instance-level switch. New accounts have AI **disabled by default**; admins
  grant or revoke it per user in **Admin → Users**. AI endpoints return `403`
  for users without access.
- **Markdown-rendered AI output.** Search summaries, workspace digests and
  reports now render the models' Markdown (headings, lists, tables, code,
  links) instead of raw text.
- **WYSIWYG notes.** Notes open in a reading view and provide an **Edit**
  button that opens a rich-text (TipTap) editor styled to match the app;
  **Save** returns to the reading view. Content is still stored as Markdown.
- **Research-mode workspace selector.** Research mode now requires choosing a
  workspace to log into, surfaced as a selector under the search box. A
  workspace's **Research** button pre-selects that workspace.
- New brand mark: an SVG ensō logo (with a matching favicon) replaces the
  placeholder kanji glyph across the sidebar, login and setup screens.

### Changed

- **Web scraping hardened.** Provider requests now send browser-like headers;
  Google scraping sends an accepted-consent cookie and uses the plain web
  results view (`udm=14`), with a fallback parser for markup changes — fixing
  cases where upstream returned `200 OK` with an unparseable, JS-only page.
- **Faster searches.** Provider fetching now overlaps with ranking-context
  database queries, and a quorum-based tail trim cancels the slowest providers
  once most have responded, bounding total search time.

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
