# ADR-0003: Three-layer configuration architecture

**Status:** Accepted

## Context

The product brief mandates separation of infrastructure config, instance
behavior, and personal preferences.

## Decision

| Layer | Storage | Mutation path | Examples |
|---|---|---|---|
| 1. Environment | Env vars (`ZEN_*`), parsed once at boot by pydantic-settings | Deploy-time only; never via UI | DB/Redis URLs, secret key, bind address, trusted proxies |
| 2. Instance | `instance_settings` table (key → JSON), write-through cache | Admin dashboard, CLI | Providers, ranking, plugins, AI, auth policy, branding, profiles |
| 3. User | `user_preferences` table | User settings UI | Theme, shortcuts, default profile, layout |

Rules:

1. Layer 1 is immutable at runtime. The UI may *display* (redacted) but never edit it.
2. Layer 2 reads go through `SettingsService` with an in-process TTL cache;
   writes bump a cache-generation key so all processes converge without restart.
3. Layer 3 never affects another user. Any setting that would is, by
   definition, a Layer-2 setting.
4. Secrets stored in Layer 2 (provider API keys, AI keys) are encrypted at rest
   with a key derived from `ZEN_SECRET_KEY` and redacted in all read APIs.
