# AI integration

AI in Zen is **optional and off by default**. Every feature works without it.
When enabled, Zen adds: query expansion, result-set summaries, workspace
digests, long-form research reports, and knowledge maps.

## Supported backends

| Backend | Where it runs | Notes |
|---|---|---|
| **Ollama** | Your hardware | Recommended. Default URL `http://localhost:11434`. |
| **LM Studio** | Your hardware | OpenAI-compatible server, default `http://localhost:1234/v1`. |
| **OpenAI-compatible** | Anywhere | Works with vLLM, llama.cpp server, LocalAI, or OpenAI itself. |
| **OpenRouter** | Cloud | One key, many models. |

## Setup (Ollama example)

1. Install Ollama on any machine on your network and pull a model:
   ```bash
   ollama pull llama3.2
   ```
2. In Zen: **Admin → AI**
   - Enable AI
   - Backend: *Ollama*
   - Base URL: `http://<ollama-host>:11434`
   - Model: pick from the detected list
3. Press **Test** — you should see a response.

> If Zen runs in Docker and Ollama on the host, use
> `http://host.docker.internal:11434` (add `extra_hosts:
> ["host.docker.internal:host-gateway"]` on Linux).

## Privacy notes

- With local backends (Ollama/LM Studio), no search data ever leaves your
  network.
- With cloud backends, the *context Zen sends* (queries, snippets, workspace
  materials) goes to that provider — the admin UI says this plainly.
- AI calls are rate-limited per user (`security.rate_limits.ai`).
- API keys are encrypted at rest and never returned by the API after saving.

## What each capability sends

| Capability | Context sent to the model |
|---|---|
| Query expansion | The query text only |
| Search summary | Query + top result titles/URLs/snippets |
| Workspace digest/report/map | Workspace name, recent searches, saved source titles/URLs/snippets, note contents (truncated) |

## Troubleshooting

- **"AI features are disabled"** — enable in Admin → AI.
- **"unreachable"** — check the base URL from *inside* the Zen container:
  `docker compose exec zen-server curl http://your-ollama:11434/api/version`.
- **Slow responses** — increase `ai.timeout_seconds` in Admin → Settings, use
  a smaller model, or reduce `ai.max_tokens`.
