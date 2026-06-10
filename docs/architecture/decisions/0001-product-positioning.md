# ADR-0001: Product positioning — research OS, not metasearch clone

**Status:** Accepted

## Context

The self-hosted search space is crowded with stateless metasearch frontends
(SearXNG, Whoogle, LibreX). The [competitive analysis](../../product/competitive-analysis.md)
identified that the empty quadrant is *self-hosted + stateful research continuity*.

## Decision

Zen is a knowledge discovery platform where search is one feature. The domain
model centers on **workspaces**, **bookmarks**, **notes**, **collections**, and
**tags** — not on the query/response cycle. Search results are transient until a
user captures them, at which point they become first-class knowledge objects.

## Consequences

- The database schema is knowledge-centric; search history is a signal source.
- Privacy mode must be able to bypass *all* persistence paths.
- UI investment goes into capture/recall flows, not just the results page.
- We do not chase SearXNG's 200-engine catalog; we ship ~12 quality providers
  and a plugin system for the long tail.
