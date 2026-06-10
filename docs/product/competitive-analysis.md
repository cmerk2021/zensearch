# Competitive Analysis

> Written before implementation, per the Zen execution plan. This document drives
> differentiation decisions and is referenced by [ADR-0001](../architecture/decisions/0001-product-positioning.md).

## Landscape

| Product | Category | Hosting | Source | Business model |
|---|---|---|---|---|
| SearXNG | Metasearch | Self-hosted | AGPL | None (community) |
| Whoogle | Google proxy | Self-hosted | MIT | None (community) |
| LibreX | Metasearch | Self-hosted | AGPL | None (community) |
| Kagi | Premium search | SaaS | Proprietary | Subscription |
| Arc Search | Mobile browser+search | Client app | Proprietary | VC-backed |
| Perplexity | AI answer engine | SaaS | Proprietary | Subscription/ads |
| Google Search | Web search | SaaS | Proprietary | Advertising |
| Brave Search | Independent index | SaaS | Partially open | Ads/premium |

---

## SearXNG

**Strengths**
- Enormous provider catalog (200+ engines) with mature scraping logic.
- Battle-tested privacy model: no logs, no cookies required, result proxying.
- Active community; packaged in every homelab ecosystem (Docker, Helm, YunoHost).
- Bang syntax, per-category engines, instance federation.

**Weaknesses**
- UI is utilitarian; theming is brittle and dated. Mobile experience is poor.
- Zero persistence: no accounts, history, bookmarks, or research continuity.
- Configuration is YAML-file-driven; no admin UI. Changes need restarts.
- Engine breakage is constant and silent; health is opaque to non-admins.
- No knowledge tools whatsoever — it is a stateless query proxy.

**What Zen learns:** provider abstraction + graceful degradation are table stakes;
the gap is everything *after* the results page.

## Whoogle

**Strengths**
- Dead-simple: one container, proxies Google with tracking stripped.
- Familiar results quality (it *is* Google).

**Weaknesses**
- Single upstream — when Google blocks the IP, the product is dead.
- No multi-source, no persistence, no admin surface, minimal theming.
- Project maintenance has slowed; CAPTCHA arms race is losing ground.

**What Zen learns:** never depend on one upstream; design for provider failure as
a first-class state, not an error.

## LibreX / LibreY

**Strengths**
- Lightweight PHP metasearch; very low resource usage; tor-friendly.

**Weaknesses**
- Small maintainer base, frequent forks, inconsistent quality.
- Same statelessness as SearXNG with fewer engines and fewer features.

**What Zen learns:** low resource floor matters to this audience (Pi-class
hardware), but minimalism without product depth caps adoption.

## Kagi

**Strengths**
- Best-in-class result quality controls: domain pinning/blocking, lenses,
  personal ranking adjustments that persist.
- Fast, calm, ad-free UI that respects the user. Excellent typography.
- Power features (bangs, programmable widgets, summarizer) integrated tastefully.

**Weaknesses**
- Paid SaaS; identity-linked by necessity (account required). Not self-hostable.
- Privacy depends on trusting the company, not on architecture.

**What Zen learns:** *personal ranking control is the killer feature.* Zen ships
domain weighting, pin/block lists, and profile-scoped ranking — but self-hosted,
so trust derives from architecture instead of policy.

## Arc Search

**Strengths**
- "Browse for me" condenses results into a synthesized page; delightful motion
  design; mobile-first focus and distraction reduction.

**Weaknesses**
- Mobile-only client, proprietary, cloud-dependent AI; no persistence layer a
  researcher can own; company pivoted away, future uncertain.

**What Zen learns:** AI synthesis is valuable as an *optional layer* on top of
results, never a replacement for them. Calm presentation is a differentiator.

## Perplexity

**Strengths**
- Conversational research flow with citations; follow-up refinement; threads
  preserve research context.

**Weaknesses**
- Hallucination risk; citations frequently misattributed.
- Cloud-only, account-linked, opaque retention. Threads are not exportable into
  a real knowledge system.
- Expensive to operate → aggressive monetization pressure.

**What Zen learns:** the *thread/workspace* model (research as a continuing
context, not isolated queries) is the right mental model. Zen implements it with
local-first storage and optional local AI, with citations that always link to
the underlying saved results.

## Google Search

**Strengths**
- Unmatched index freshness/coverage; instant answers; universal muscle memory.

**Weaknesses**
- Engagement-optimized: ads, AI overviews, shopping modules, infinite SERP
  features crowd out organic results.
- Deep tracking; personalization bubble; result quality widely perceived as
  declining for technical queries.

**What Zen learns:** familiarity of layout (query box → ranked results with
title/URL/snippet) should be preserved; everything *around* it should be
stripped. Zen's Focus mode is the explicit anti-SERP.

## Brave Search

**Strengths**
- Independent index; Goggles (user-defined re-ranking rules) is genuinely novel;
  decent API.

**Weaknesses**
- SaaS; crypto/ads entanglement erodes trust for parts of this audience;
  Goggles syntax is too obscure to gain adoption.

**What Zen learns:** re-ranking rules are powerful but must be approachable —
Zen exposes them as admin-managed **search profiles** with a UI, not a DSL.

---

## Market gaps

1. **No self-hosted product owns "research continuity".** Every self-hosted
   option is stateless; every stateful option (Kagi, Perplexity) is cloud SaaS.
   The intersection — *self-hosted + persistent research workspace* — is empty.
2. **No admin-first metasearch.** SearXNG admins edit YAML; users get whatever
   the instance gives them. Nobody offers Jellyfin-grade admin UX (dashboard,
   plugin catalog, health monitoring) for search.
3. **No local-AI-native search product.** Tools bolt OpenAI on. Nothing treats
   Ollama/llama.cpp-class local inference as the primary AI path with cloud as
   fallback.
4. **No knowledge loop.** Search → save → annotate → resurface is broken across
   four different apps (search engine, bookmarks, notes app, read-later). Nobody
   closes the loop in one self-hosted deployment.
5. **Plugin ecosystems don't exist in this space.** SearXNG engines are PRs to
   core; there is no installable, versioned, third-party extension story.

## Zen differentiators

| # | Differentiator | Backed by |
|---|---|---|
| D1 | Research workspaces: searches, notes, bookmarks, AI digests in one place | Gap 1, Perplexity threads, Obsidian/Notion patterns |
| D2 | Instance-first administration: full admin dashboard, DB-backed config, zero YAML | Gap 2, Jellyfin/Home Assistant UX |
| D3 | Local-first AI with pluggable backends (Ollama, LM Studio, OpenAI-compatible, OpenRouter), fully optional | Gap 3 |
| D4 | Configurable ranking: domain weights, pin/block, profile-scoped boosts — Kagi-style control, self-hosted | Kagi lenses, Brave Goggles |
| D5 | Plugin platform with repositories (official/community/private), versioning, central install | Gap 5 |
| D6 | Search modes (Normal / Privacy / Focus / Research) as one-keystroke contexts | Arc/Kagi calm-UX learnings |
| D7 | Privacy by architecture: no telemetry, documented egress, privacy mode with zero retention | SearXNG ethos, applied to a stateful product |
| D8 | Homelab-grade ops: single compose file, ARM64+AMD64, Pi-class footprint, health/metrics endpoints | LibreX resource floor, SearXNG packaging lessons |

## Non-goals (anti-scope)

- **Not** a crawler/index — Zen aggregates; it does not crawl the web.
- **Not** a public multi-tenant SaaS — instance-first for trusted groups.
- **Not** an ad or monetization platform — no commercial hooks in core.
- **Not** a browser — Zen is a destination, reachable from any browser.
