# ADR-0007: Plugin trust model

**Status:** Accepted

## Context

Plugins ship Python code that runs in the Zen process. True in-process
sandboxing of Python is not achievable (every "restricted Python" approach has
known escapes). Claiming sandbox security we cannot deliver would be a security
lie.

## Decision

1. **Honesty first:** documentation states plainly that installing a plugin
   executes third-party code with the privileges of the Zen process. Admins
   install plugins; users never can.
2. **Permission-gated capability API:** plugins receive a `PluginContext`
   exposing only the capability registries their manifest declares
   (`search_providers`, `rankers`, `bangs`, `themes`, `exporters`,
   `ai_backends`, `widgets`). Undeclared capabilities raise
   `PluginPermissionError`. This is a *correctness and review* boundary, not a
   security boundary, and is documented as such.
3. **Supply-chain controls:** repository catalogs pin `sha256` checksums;
   installs verify them. Version pinning, rollback to the previously installed
   version, and a signed official repository are supported.
4. **Operational containment** is delegated to the deployment layer (container
   isolation, read-only rootfs, egress policies) and documented in the admin
   security guide.

## Consequences

- No false security claims; review and provenance carry the trust burden.
- The capability registries double as the public SDK surface, keeping the
  plugin API small and versionable (`zen.plugins.sdk.SDK_VERSION`).
