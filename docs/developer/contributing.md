# Contributing to Zen

Thanks for considering a contribution. This guide gets you productive fast.

## Development setup

```bash
git clone https://github.com/cmerk2021/zensearch && cd zensearch

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ZEN_ENV=development zen serve --reload              # API on :8000, docs at /api/docs

# Frontend (second terminal)
cd frontend
npm install
npm run dev                                          # UI on :3000, proxies /api to :8000
```

`ZEN_ENV=development` uses SQLite at `./data/zen.db`, auto-creates the schema,
and generates an ephemeral secret key. Create a user with
`zen users create-admin`.

## Quality bar

Every PR must pass:

```bash
# backend
ruff check zen tests
pytest -q                       # 100% pass, coverage ≥ 70%

# frontend
npm run typecheck
npm run build
```

CI enforces all of the above plus PostgreSQL migration round-trips and Docker
image builds.

## Code style

- Python: ruff-formatted, type-annotated public APIs, no bare `except` outside
  documented isolation boundaries, structlog for logging (never `print`).
- TypeScript: strict mode, no `any` in exported signatures, server state via
  TanStack Query, design tokens from `globals.css` (no hard-coded colors).
- Never log user query content at INFO or above (privacy requirement).
- Architectural changes need an ADR in `docs/architecture/decisions/`.

## Tests

- Unit tests for pure logic (`tests/unit/`).
- API tests through the ASGI transport (`tests/api/`) — no mocking of Zen
  internals; mock *upstreams* with `respx`.
- Integration tests for cross-cutting behavior (`tests/integration/`).
- A bug fix without a regression test will be asked to add one.

## Commits & PRs

- Conventional-ish subjects: `search: fix bing redirect decoding`,
  `admin: add provider test button`.
- One logical change per PR. Describe *why*, link issues.
- Breaking API/SDK changes require a changelog entry and (for the SDK) a
  version bump rationale.

## Adding a search provider (most common contribution)

1. Create `backend/zen/search/providers/<slug>.py` subclassing
   `SearchProvider` — study `wikipedia.py` (API-based) or `bing.py`
   (scraper).
2. Register it in `BUILTIN_PROVIDERS` (`providers/__init__.py`).
3. Add parser tests with captured HTML/JSON fixtures in
   `tests/unit/test_providers.py` and bump the provider-count test.
4. Document anything notable (API keys, rate limits) in the class
   `description`.

Prefer official/stable APIs over scraping. Scrapers must degrade gracefully —
return `[]` rather than raise on missing markup, and let the circuit breaker
handle hard failures.

## Releases (maintainers)

1. Bump `backend/zen/version.py` and `frontend/package.json` to the same
   version; update `CHANGELOG.md`.
2. Tag `vX.Y.Z` and push — the release workflow validates version
   consistency, runs tests, builds multi-arch images, and drafts the GitHub
   release with a generated changelog.
