# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| Latest release (0.9.x) | ✅ |
| Older | ❌ — upgrade first |

## Reporting a vulnerability

**Do not open public issues for security problems.**

Report privately via GitHub Security Advisories
(*Security → Report a vulnerability* on the repository), including:

- Affected version and deployment shape (compose/k8s, proxy in front?)
- Reproduction steps or proof of concept
- Impact assessment as you see it

You will receive an acknowledgement within 72 hours and a status update at
least every 7 days. Coordinated disclosure: we ask for up to 90 days to ship
a fix before publication; critical issues are prioritized for immediate
patch releases.

## Scope notes

- Plugins execute with full process privileges **by documented design**
  (see [ADR-0007](docs/architecture/decisions/0007-plugin-trust-model.md));
  reports that "a malicious plugin can do X" are out of scope unless they
  bypass the checksum/permission/admin-only controls themselves.
- Issues requiring a hostile reverse proxy inside `ZEN_TRUSTED_PROXIES` are
  out of scope (that list is explicitly trusted).

## Hall of fame

Reporters of accepted vulnerabilities are credited in release notes unless
anonymity is requested.
