# Example plugins

Reference implementations for the [Plugin SDK](../../docs/developer/plugin-sdk.md).

| Plugin | Demonstrates |
|---|---|
| [hackernews](hackernews/) | Search provider (JSON API) + custom bang |

## Build & sideload

```bash
cd hackernews
zip -j example-hackernews-1.0.0.zip zen-plugin.json hackernews_provider.py
```

Then **Admin → Plugins → Upload** (or `POST /api/v1/admin/plugins/upload`).
