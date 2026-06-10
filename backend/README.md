# Zen Server

The Python backend for [Zen](../README.md) — a self-hosted research and
knowledge discovery platform.

## Quick start (development)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
zen users create-admin             # interactive
zen serve --reload
```

The API listens on `http://localhost:8000`. Interactive docs are served at
`/api/docs` outside production mode.

## Layout

| Path | Purpose |
|---|---|
| `zen/core` | Configuration (Layer 1), security primitives, cache, rate limiting |
| `zen/db` | Async SQLAlchemy engine + ORM models |
| `zen/search` | Providers, pipeline, ranking, modes, bangs, engine |
| `zen/services` | Business logic (auth, workspaces, knowledge, settings…) |
| `zen/ai` | Optional AI layer (Ollama / OpenAI-compatible backends) |
| `zen/plugins` | Plugin SDK, loader, manager, repositories |
| `zen/api` | FastAPI routes and dependencies |
| `zen/workers` | In-process scheduler and periodic tasks |
| `zen/observability` | Structured logging, Prometheus metrics |
| `tests` | Unit / API / integration test suites |

## Testing

```bash
pytest                  # full suite
pytest --cov=zen        # with coverage
ruff check zen tests    # lint
```

See [developer documentation](../docs/developer) for architecture details and
the plugin SDK guide.
