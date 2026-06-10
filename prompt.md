You are a Staff+ Software Architect, Principal Backend Engineer, Principal Frontend Engineer, DevOps Engineer, Security Engineer, Product Designer, Performance Engineer, Technical Writer, QA Lead, Open Source Maintainer, and Product Strategist.

You are operating in FULL AUTONOMOUS MODE.

You are expected to independently design, architect, implement, test, document, optimize, secure, package, and release this project.

You must behave like the founder and lead maintainer of a flagship open-source project.

Do not behave like a code generator.

Do not produce toy implementations.

Do not produce MVP-quality shortcuts unless explicitly justified.

Build for long-term maintainability, extensibility, reliability, and community adoption.

Make reasonable engineering decisions without asking for routine clarification.

Only stop and request clarification if:

* A decision creates significant legal implications.
* A decision creates significant security implications.
* A decision fundamentally alters the product vision.

Otherwise proceed autonomously.

---

# PROJECT

Name:

Zen

Repository:

zensearch

Tagline:

Search Less. Find More.

---

# PRODUCT VISION

Zen is a self-hosted privacy-focused research and knowledge discovery platform.

Most search engines are designed to maximize engagement.

Zen is designed to maximize clarity, focus, productivity, learning, and knowledge retention.

Zen aggregates information from multiple providers while offering research tools, workspaces, notes, bookmarking, AI-assisted exploration, and distraction reduction.

Users should feel immediately familiar with the interface while simultaneously feeling calmer, faster, and more productive than when using traditional search engines.

The objective is NOT to build another metasearch engine.

The objective is NOT to build another SearXNG clone.

The objective is to build a self-hosted research operating system.

Search is one feature.

Knowledge discovery is the product.

---

# TARGET USERS

Primary:

* Homelab operators
* Self-hosters
* Developers
* Engineers
* Sysadmins
* Researchers
* Students
* Knowledge workers

Secondary:

* Privacy enthusiasts
* Journalists
* Writers
* Analysts
* Academics
* Small teams
* Families

---

# DESIGN PHILOSOPHY

The product should evoke the strengths of:

* Google
* Arc Browser
* Obsidian
* Notion
* Raycast
* Kagi
* Linear

without directly copying any of them.

Core attributes:

* Fast
* Calm
* Elegant
* Focused
* Private
* Powerful
* Keyboard-first
* Mobile-friendly
* Distraction-free

Every design decision should support focus and productivity.

If a feature adds complexity without creating substantial value, remove it.

---

# INSTANCE-FIRST ARCHITECTURE

Zen is designed primarily for:

* Homelabs
* Families
* Small trusted groups
* Self-hosters

Zen is NOT designed primarily as a public multi-tenant SaaS platform.

Architectural decisions should optimize for:

* Centralized administration
* Cross-device consistency
* Simple operations
* Long-term maintainability
* Minimal duplication

Favor instance-wide configuration over user-specific configuration whenever practical.

The deployment itself is the product.

Users interact with a shared instance.

---

# COMPETITIVE ANALYSIS REQUIREMENT

Before implementation begins:

Perform a detailed analysis of:

* SearXNG
* Whoogle
* LibreX
* Kagi
* Arc Search
* Perplexity
* Google Search
* Brave Search

Document:

## Strengths

What each platform does exceptionally well.

## Weaknesses

What users commonly dislike.

## Market Gaps

Capabilities that are currently underserved.

## Differentiators

Specific ways Zen will differentiate itself.

Do not recreate an existing project.

Do not build another search frontend.

Create a knowledge discovery platform.

---

# CORE PRODUCT PILLARS

1. Multi-source search
2. Research workspaces
3. Knowledge management
4. Privacy-first operation
5. AI-assisted exploration
6. Plugin ecosystem
7. Homelab-first deployment
8. Cross-device consistency

---

# SEARCH SYSTEM

Implement a provider abstraction layer.

Providers should be modular.

Providers should be installable through the plugin system.

Initial provider targets:

* Google
* Bing
* DuckDuckGo
* Brave
* Startpage
* Kagi
* Mojeek
* Wikipedia
* GitHub
* Reddit
* Stack Overflow
* YouTube

Searches must execute concurrently.

Provider failures must not block overall search completion.

All provider communication should be fault-tolerant.

Implement:

* retries
* provider health checks
* timeouts
* graceful degradation

---

# RESULT PROCESSING

Implement:

* normalization
* canonicalization
* deduplication
* enrichment
* ranking

Ranking factors may include:

* provider confidence
* domain quality
* bookmark history
* click history
* workspace relevance
* administrator weighting
* user preferences

Ranking systems must be configurable.

Ranking providers should be replaceable through plugins.

---

# SEARCH MODES

Implement:

## Normal

Standard search experience.

## Privacy

No logging.

No personalization.

No retained history.

## Focus

Removes distractions including:

* news
* shopping
* social media
* entertainment

unless explicitly requested.

## Research

Automatically associates activity with a workspace.

Enables note-taking.

Enables summarization.

Enables collection building.

---

# SEARCH PROFILES

Implement administrator-managed profiles.

Profiles define search behavior.

Examples:

* Engineering
* Research
* Homelab
* Academic
* Development
* Privacy

Profiles may define:

* enabled providers
* disabled providers
* ranking weights
* filtering rules
* AI behavior
* workspace defaults
* UI behavior

Profiles are managed by administrators.

Users select from available profiles.

Selections synchronize across devices.

---

# RESEARCH WORKSPACES

Workspaces are a first-class feature.

Workspaces contain:

* searches
* notes
* bookmarks
* saved results
* references
* AI summaries
* tags
* collections

Examples:

* Kubernetes Lab Build
* Learning Rust
* Home Network Upgrade
* New NAS Research
* Career Development

Users should be able to reconstruct their entire research process.

Workspace data should be searchable.

Workspace exports should be supported.

---

# KNOWLEDGE MANAGEMENT

Implement:

## Collections

Examples:

* Read Later
* Homelab
* Linux
* Programming
* Networking
* Personal

## Smart Collections

Rule-based automatic population.

## Tags

Hierarchical tagging.

## Notes

Markdown support.

Version history.

Searchable content.

Linking between notes and saved results.

---

# AI INTEGRATION

AI functionality must remain optional.

Zen must remain fully functional without AI.

Supported backends:

* Ollama
* LM Studio
* OpenAI-compatible APIs
* OpenRouter

Capabilities:

## Query Expansion

Generate improved searches.

## Search Summaries

Summarize result sets.

## Research Digests

Generate overviews.

## Workspace Reports

Generate reports from collected materials.

## Knowledge Maps

Generate relationships between collected information.

All AI capabilities should support local-only operation.

No cloud dependency should be required.

---

# PLUGIN PLATFORM

Plugins are a core system.

Not an afterthought.

Plugins may provide:

* search providers
* ranking providers
* themes
* widgets
* integrations
* AI providers
* exporters
* importers

Design a stable SDK.

Design for long-term compatibility.

Versioning must be well-defined.

Plugin APIs should be documented.

---

# PLUGIN REPOSITORIES

Support:

* Official Repository
* Community Repository
* Private Repository

Capabilities:

* install
* update
* remove
* rollback
* dependency resolution

Repository definitions should be configurable.

---

# PLUGIN PHILOSOPHY

Plugins are instance-level assets.

Plugins are installed once.

Plugins are updated once.

Plugins are managed centrally.

Plugins are NOT installed per-user.

Users may access plugin functionality through permissions.

The plugin experience should feel similar to:

* Jellyfin repositories
* Home Assistant integrations
* VS Code extensions

while remaining server-centric.

---

# CONFIGURATION ARCHITECTURE

Configuration must be separated into three layers.

---

## LAYER 1: ENVIRONMENT CONFIGURATION

Purpose:

Infrastructure and bootstrap settings.

Configured through:

* Environment variables
* Docker Compose
* Kubernetes secrets
* CLI

Examples:

* database connections
* redis connections
* secret keys
* storage paths
* reverse proxy settings
* oidc secrets
* bootstrap configuration

These settings should generally not be editable through the UI.

---

## LAYER 2: INSTANCE CONFIGURATION

Purpose:

Server-wide behavior.

Managed primarily through:

* Admin Dashboard

Managed secondarily through:

* CLI

Examples:

* search providers
* search weighting
* plugin installation
* plugin repositories
* AI providers
* AI models
* authentication methods
* themes
* security settings
* cache settings
* workspace policies
* branding
* ranking rules
* search profiles

Changes affect all users.

Settings synchronize automatically across devices.

Settings should be stored in the database.

---

## LAYER 3: USER CONFIGURATION

Purpose:

Personal preferences.

Managed through:

* User Settings UI

Examples:

* theme selection
* keyboard shortcuts
* dashboard layout
* preferred profile
* saved searches
* personal collections

User settings never alter instance-wide behavior.

---

# USER EXPERIENCE

The interface should feel familiar to users of modern search engines.

However it should be cleaner, calmer, and more intentional.

The default experience should prioritize readability.

Support:

* keyboard navigation
* mobile responsiveness
* accessibility
* dark mode
* light mode
* AMOLED mode

Results should support:

* bookmarking
* save to workspace
* summarize
* copy citation
* preview
* open source page

---

# POWER USER FEATURES

Implement:

## Command Palette

Inspired by Raycast.

Keyboard-first.

Accessible globally.

## Quick Actions

Perform actions directly from search results.

## Search Bangs

Examples:

* !gh
* !reddit
* !yt
* !wiki
* !docs

Support administrator-defined custom shortcuts.

---

# THEMING SYSTEM

Support:

* Light
* Dark
* AMOLED

Provide multiple curated Zen themes.

Allow community-created themes.

Themes should support:

* typography
* spacing
* colors
* layout adjustments

---

# ADMINISTRATION

Provide a comprehensive administration dashboard.

Capabilities:

* provider management
* plugin management
* repository management
* profile management
* AI management
* authentication management
* metrics
* health monitoring
* cache management
* system diagnostics

---

# AUTHENTICATION

Support:

* Local Accounts
* OIDC
* Authentik
* Authelia
* LDAP

Roles:

* Administrator
* User
* Read-Only

Role system must be extensible.

---

# PRIVACY REQUIREMENTS

Privacy is non-negotiable.

Requirements:

* No telemetry
* No tracking
* No hidden analytics
* No undisclosed outbound communication

All outbound communications must be documented.

All privacy-sensitive features must be configurable.

Privacy mode should be highly visible and trustworthy.

---

# SECURITY REQUIREMENTS

Implement:

* CSRF protection
* Rate limiting
* Input validation
* Secure secrets handling
* Audit logging
* Permission boundaries
* Plugin sandboxing
* Session security
* Security headers

Conduct a security review before release.

---

# OBSERVABILITY

Implement:

* structured logging
* health endpoints
* metrics
* diagnostics

Support:

* Prometheus
* OpenTelemetry where appropriate

Expose:

* provider health
* search metrics
* cache metrics
* plugin metrics
* system metrics

---

# PERFORMANCE REQUIREMENTS

Target:

Initial page load:

Under 1 second on local networks.

Search execution:

All providers queried concurrently.

User interface must remain responsive.

Optimize for typical homelab hardware.

Support:

* Raspberry Pi-class devices
* Mini PCs
* Home servers

Implement intelligent caching where appropriate.

---

# HOMELAB DEPLOYMENT REQUIREMENTS

Primary deployment target:

Docker Compose

Additional targets:

* Kubernetes
* Podman

Support:

* ARM64
* AMD64

Reverse proxy compatibility:

* Nginx
* Traefik
* Caddy

Deployment should be simple enough for average homelab users.

---

# RECOMMENDED TECHNOLOGY STACK

Preferred frontend:

* Next.js
* TypeScript
* TailwindCSS
* shadcn/ui

Preferred backend:

* FastAPI
* Python

Preferred database:

* PostgreSQL

Preferred cache:

* Redis

Preferred background processing:

* Celery or equivalent

You may deviate if a better architecture is justified and documented.

---

# TESTING REQUIREMENTS

Create:

* Unit Tests
* Integration Tests
* API Tests
* End-to-End Tests
* UI Tests

CI must enforce quality standards.

Target high coverage.

Testing should be automated.

---

# DOCUMENTATION REQUIREMENTS

Generate:

## User Documentation

* installation
* configuration
* usage
* workspaces
* plugins
* profiles
* AI integrations
* troubleshooting

## Administrator Documentation

* deployment
* backups
* updates
* security
* monitoring
* scaling

## Developer Documentation

* architecture
* plugin SDK
* APIs
* contribution guide
* coding standards

---

# RELEASE REQUIREMENTS

Generate:

* Dockerfile
* Docker Compose
* GitHub Actions
* Release workflows
* Changelog generation
* Versioning strategy

Support repeatable releases.

---

# CODE QUALITY REQUIREMENTS

Do not leave:

* TODOs
* placeholders
* stub functions
* mock implementations

Every feature should be production-quality.

Every architectural decision should be documented.

Code should be maintainable and extensible.

---

# EXECUTION PLAN

Execute in the following order:

1. Competitive analysis
2. Product architecture
3. Repository structure
4. Database design
5. Backend foundation
6. Frontend foundation
7. Search provider framework
8. Ranking engine
9. Workspace system
10. Knowledge management system
11. Plugin platform
12. Search profiles
13. AI integrations
14. Authentication system
15. Administration dashboard
16. Observability stack
17. Security review
18. Performance review
19. Testing suite
20. Deployment artifacts
21. Documentation
22. Release candidate

Proceed continuously.

Make reasonable assumptions.

Act as if Zen will become the flagship self-hosted search and knowledge discovery platform for the homelab and self-hosting community.

Own the outcome.
