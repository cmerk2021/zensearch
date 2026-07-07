# Administration guide

Everything in this guide is instance-wide (Layer 2 configuration): changes
apply to all users immediately, no restarts needed.

## The admin dashboard

`/admin` (admin role required):

| Tab | Purpose |
|---|---|
| Overview | Health of database/cache, provider circuit states, usage counters |
| Providers | Enable/disable, weights, timeouts, API keys, live test |
| Profiles | Create/edit search profiles users select from |
| Ranking | Instance-wide domain rules (boost/lower/pin/block) |
| Users | Create accounts, roles, disable, reset passwords, grant AI access |
| Plugins | Repositories, install/update/rollback/remove |
| AI | Backend, model, key, connectivity test |
| Settings | Branding, auth policy, privacy, search defaults |
| Audit | Security-relevant action log |

## Providers

- **Weights** (0–10) scale a provider's influence in ranking. Default weights
  favor Google/Kagi/Brave quality.
- **API keys** unlock or stabilize providers: Kagi (required), Brave
  (recommended — free tier), GitHub (higher rate limits), Stack Overflow
  (higher quota). Keys are encrypted at rest.
- **Test** runs a live query and shows sample results or the exact error.
- **Health** shows circuit state. Circuits open automatically after 5
  consecutive failures and recover via half-open probes; you can reset
  manually. A scheduled probe checks degraded/stale providers every 15 min.

## Search profiles

Profiles bundle: provider subset, domain weight overrides, blocked domains,
AI behavior, workspace defaults, and UI hints. Users pick a profile; admins
define them. One profile is the **default** for everyone who hasn't chosen.

Seeded profiles: Balanced (default), Engineering, Research, Homelab,
Academic, Privacy. Edit or delete them freely (set a new default first).

## Ranking rules

Domain rules apply to every search:

- **Boost** ×N — quality sources (docs sites, wikis)
- **Lower** ×0.N — content farms
- **Pin** — always on top (your internal wiki)
- **Block** — never shown (spam)

Rules match subdomains automatically (`example.com` matches
`docs.example.com`).

## Authentication

### Local accounts
Argon2id-hashed passwords, minimum 10 chars. Registration is **closed** by
default — open it in Settings → Authentication.

### OIDC (Authentik, Authelia, Keycloak, …)
1. Create an OAuth2/OIDC provider in your IdP with redirect URI
   `https://zen.example.com/api/v1/auth/oidc/callback`.
2. In Zen Settings → Authentication: enable OIDC, set issuer URL, client ID,
   client secret.
3. Optionally set `auth.oidc.admin_groups` (via CLI or settings API) so IdP
   group membership maps to the Zen admin role.
4. `ZEN_BASE_URL` must be set for redirects to work.

Authentik issuer example: `https://auth.example.com/application/o/zen/`
Authelia issuer example: `https://auth.example.com`

### LDAP
Enable in settings and set `auth.ldap.server` plus
`auth.ldap.bind_dn_template`, e.g. `uid={username},ou=people,dc=example,dc=com`.
Requires the `ldap` extra in custom images (included in official images).

### Roles
- **admin** — everything
- **user** — full personal usage
- **readonly** — can search and browse own data, cannot create/modify

The instance always keeps at least one active admin; the API refuses changes
that would violate that.

### AI access
AI is disabled per account by default. In **Users**, toggle **AI** on a user
(or the *AI access* switch when creating one) to let them use AI features. The
instance-level AI switch (Admin → AI) must also be on. Both layers are required.

## Privacy controls

| Setting | Effect |
|---|---|
| `privacy.search_history_enabled` | Master switch for history recording |
| `privacy.search_history_retention_days` | Auto-deletion window (0 = keep) |
| `privacy.click_tracking_enabled` | Click-through ranking signal |

Privacy-mode searches bypass all of this unconditionally.

## CLI

Inside the server container (or any shell with the package installed):

```bash
zen doctor                      # connectivity diagnosis
zen users create-admin          # interactive admin creation
zen users list
zen users set-password <name>
zen users set-role <name> admin|user|readonly
zen settings list               # secrets redacted
zen settings set instance.name '"My Zen"'
zen plugins list / install / remove
zen db upgrade                  # apply migrations
```

## Audit log

Logins, settings changes, user/plugin/profile management, and domain-rule
changes are recorded with actor, IP, and timestamp. Toggle with
`security.audit_enabled`.
