# Plugin SDK guide

Zen plugins extend the instance with new search providers, rankers, bangs,
themes, exporters, AI backends, and dashboard widgets. Plugins are installed
**once per instance** by an administrator — never per user.

> **Trust model:** a plugin is Python code running inside the Zen process.
> Review what you install. See the
> [security guide](../admin/security.md#plugin-security-read-this).

## Anatomy of a plugin

A plugin is a zip archive:

```
my-plugin-1.0.0.zip
├── zen-plugin.json      # manifest (required, at archive root)
└── my_plugin.py         # entry module (anything importable works)
```

### Manifest (`zen-plugin.json`)

```json
{
  "id": "lobsters-provider",
  "name": "Lobsters Provider",
  "version": "1.0.0",
  "entry": "lobsters_provider",
  "description": "Search lobste.rs stories.",
  "author": "you",
  "license": "MIT",
  "homepage": "https://github.com/you/zen-lobsters",
  "permissions": ["search_providers", "bangs"],
  "requires": [],
  "min_zen_version": "0.9.0",
  "sdk_version": "1.0"
}
```

| Field | Rules |
|---|---|
| `id` | 3–64 chars, `[a-z0-9-]`, unique per instance |
| `version` | PEP 440 / semver-style, drives update detection |
| `entry` | Python module path importable from the archive root |
| `permissions` | Subset of: `search_providers`, `rankers`, `bangs`, `themes`, `exporters`, `ai_backends`, `widgets` |
| `requires` | Other plugin ids installed first (resolved automatically from repositories) |
| `sdk_version` | Major must match the host (`1.x` today) |

### Entry module

```python
# lobsters_provider.py
import httpx
from zen.search.http import resilient_get
from zen.search.models import ProviderCategory, RawResult, SearchQuery
from zen.search.providers.base import SearchProvider


class LobstersProvider(SearchProvider):
    slug = "lobsters"
    name = "Lobsters"
    category = ProviderCategory.SOCIAL
    default_weight = 0.8
    description = "lobste.rs stories via the public API."

    async def search(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        response = await resilient_get(
            client, "https://lobste.rs/search.json",
            params={"q": query.text, "what": "stories", "order": "relevance"},
        )
        results = []
        for item in response.json():
            results.append(RawResult(
                title=item["title"],
                url=item["url"] or item["comments_url"],
                snippet=f'{item["score"]} points · {item["comment_count"]} comments',
                position=len(results) + 1,
            ))
        return results


def setup(ctx):
    ctx.register_search_provider(LobstersProvider)
    ctx.register_bang("lob", "https://lobste.rs/search?q={q}&what=stories")
```

`setup(ctx)` receives a `PluginContext` exposing **only the capabilities the
manifest declared** — undeclared calls raise `PluginPermissionError`.

## Context API (SDK 1.0)

| Method | Permission | Notes |
|---|---|---|
| `ctx.register_search_provider(cls)` | `search_providers` | `cls` subclasses `SearchProvider`; slug must not collide with built-ins |
| `ctx.register_ranker(obj)` | `rankers` | `obj` has `.name` and `.rank(results, ctx) -> list` |
| `ctx.register_bang(name, template)` | `bangs` | template must contain `{q}` |
| `ctx.register_theme(id, definition)` | `themes` | requires `name` and `colors` keys |
| `ctx.register_exporter(format_id, fn)` | `exporters` | callable receiving export payloads |
| `ctx.register_ai_backend(name, factory)` | `ai_backends` | factory matching `AIBackend` protocol |
| `ctx.register_widget(id, definition)` | `widgets` | requires `name` |
| `ctx.config` | — | dict from the stored plugin config |

Everything registered is automatically removed when the plugin is disabled,
removed, or replaced — no teardown hook needed.

## Compatibility contract

- `SDK_VERSION` major bump ⇒ breaking change; Zen refuses to load
  incompatible plugins at manifest parse time.
- The classes/functions documented on this page (plus
  `zen.search.models.RawResult/SearchQuery`, `zen.search.http.resilient_get/post`,
  `zen.search.providers.base.SearchProvider`) are the supported surface.
  Anything else may change between minor versions.

## Publishing to a repository

A repository is any HTTPS URL serving a catalog:

```json
{
  "name": "My Plugin Repo",
  "plugins": [
    {
      "id": "lobsters-provider",
      "name": "Lobsters Provider",
      "version": "1.0.0",
      "description": "Search lobste.rs stories.",
      "download_url": "https://example.com/dist/lobsters-provider-1.0.0.zip",
      "sha256": "<sha256 of the zip>",
      "manifest": { ...contents of zen-plugin.json... }
    }
  ]
}
```

GitHub Pages, raw GitHub URLs, or any static host works. Compute the digest
with `sha256sum`. Zen verifies it on every install.

## Local development

```bash
# Sideload without a repository:
zip -r my-plugin.zip zen-plugin.json my_plugin.py
# Admin → Plugins → Upload, or:
curl -X POST https://zen.local/api/v1/admin/plugins/upload \
     -H "X-CSRF-Token: …" -b cookies.txt -F file=@my-plugin.zip
```

Errors during `setup()` mark the plugin `error` with the message visible in
the admin UI; fix and re-upload a bumped version, or roll back.
