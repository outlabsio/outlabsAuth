# OutlabsAuth Security Guide

**Status:** Production reference
**Last verified:** 2026-08-02
**Applies to:** `0.1.0a27` and later

This document describes controls implemented by the current code. Historical
findings and their verification evidence live in
[`SECURITY_AUDIT_2026-08-02.md`](./SECURITY_AUDIT_2026-08-02.md).

## Security model

OutlabsAuth is an authentication and authorization library. The consuming
application remains responsible for TLS, trusted reverse-proxy configuration,
network policy, secret storage, database access, and security monitoring.

The core trust boundaries are:

- PostgreSQL is the durable source of truth for users, sessions, roles,
  memberships, API keys, OAuth state, and audit history.
- Redis provides shared caching, API-key enforcement, and cross-worker request
  rate limits. Where a local fallback exists, it is not a distributed control.
- Permission-bearing operations are contained: an actor cannot grant a
  permission they do not effectively hold at the target entity.
- Public endpoints expose capability flags, not the permission catalog or
  account lock state.

## Required deployment controls

1. Terminate TLS before requests reach the application.
2. Generate `SECRET_KEY` with at least 48 random bytes and store it in a secret
   manager. Known placeholders are rejected at startup.
3. Configure the ASGI server's trusted-proxy support. OutlabsAuth uses
   `request.client.host`; it deliberately does not trust raw
   `X-Forwarded-For` values.
4. Use Redis for multi-worker or multi-instance deployments. In-memory request
   limiting is a per-process fallback and therefore multiplies with workers.
5. Keep `/metrics` on an internal listener or protect it with network policy or
   gateway authentication. The optional metrics router has no application-level
   authentication.
6. Run the Alembic upgrade before serving the new application version.

## Password login and account protection

- Passwords are hashed with Argon2id through `pwdlib`.
- Unknown users execute a dummy password verification to reduce timing-based
  enumeration.
- Password login is rate-limited by the ASGI-resolved client IP. Redis provides
  shared counters and fails closed by default when configured but unavailable;
  `local_fallback` is an explicit availability-over-consistency option.
- Failed-password counters and lock expiration are recorded internally but are
  not returned to clients. Unknown accounts, bad passwords, and locked accounts
  receive the same invalid-credentials response.
- Default policy: 20 attempts per IP per five minutes, five failed attempts per
  account, and a 30-minute account lock. Tune these values for the deployment.

## JWTs and sessions

- Access and refresh tokens include an explicit token type and audience.
- Access tokens default to 15 minutes.
- Refresh tokens default to a 30-day rolling inactivity window.
- Session families have a 90-day absolute lifetime by default. Rotation keeps
  the original family expiration in both the signed token and the database.
- Refresh tokens are single-use when storage is enabled. Reuse of a rotated
  token revokes the affected user's sessions.
- Password changes invalidate older tokens. Logout and administrative session
  revocation mark stored refresh tokens unusable.
- Frontend-bound sessions preserve and revalidate their `azp` profile through
  refresh rotation.

## Authorization and tenant isolation

- Role creation, permission addition, direct role assignment, invitations, and
  membership role assignment apply delegation containment.
- Containment is evaluated with the actor's effective permissions at the target
  entity. A permission held in one tenant cannot be delegated in another.
- Role changes that widen reach—reactivation, hierarchy scope, automatic
  assignment, global availability, or broader assignable entity types—require
  containment for the role's effective grants.
- ABAC condition mutations require the actor to be able to delegate the role's
  grants because removing or changing a condition may broaden access.
- Removing permissions or disabling a role remains possible during incident
  response even when the responder does not hold the removed grant.

## API keys

- API keys contain high-entropy random material. PostgreSQL stores only a
  SHA-256 digest; this is appropriate for unguessable API-key material and is
  not the password-hashing policy.
- Raw keys are returned once and must never be logged.
- Owner and actor permissions bound the scopes that may be delegated.
- IP allow-list entries accept individual IPv4/IPv6 addresses or CIDR ranges.
  Inputs are validated and canonicalized on create/update; invalid legacy rows
  are ignored fail-closed.
- A configured allow-list requires a resolvable client address. Missing client
  metadata does not bypass the list.
- API-key rate limiting uses Redis. The configured failure mode determines
  whether authorization fails closed or open during an enforcement outage.
- API keys do not have failure-count lockouts: high-entropy credentials are not
  password guesses. Use IP/network restrictions, least-privilege scopes,
  expiration, rate limits, and rotation.

## OAuth and OpenID Connect

- Router factories use the asynchronous `httpx-oauth` client contract supplied
  by `outlabs_auth.oauth.provider_factories`.
- Authorization requests use PKCE S256. The verifier is stored in the one-time
  OAuth-state record and supplied during authorization-code exchange.
- State is signed, stored, bound to an HttpOnly SameSite cookie, locked during
  consumption, and burned before account work.
- OIDC clients receive a random nonce. The callback cryptographically validates
  the ID token's signature, issuer, audience, required claims, and nonce before
  using provider identity data.
- Provider access/refresh tokens are stored only when explicitly enabled and
  only through the configured token cipher.

## Invitations and public configuration

- `enable_invitations=False` disables invite, accept-invite, and resend-invite
  endpoints; disabled routes return 404.
- `/auth/config` is public and returns only preset, feature, and enabled auth
  method flags.
- `/auth/config/permissions` requires `permission:read` and returns the active
  permission catalog for authenticated administration UIs.

## Observability and sensitive data

- Security events log identifiers, key prefixes, reasons, and timing—not raw
  passwords, tokens, API keys, or signing secrets.
- `/metrics` is intended for Prometheus scraping on a trusted network. Mounting
  is opt-in via `include_metrics=True`.
- Audit and login-history tables may contain IP addresses and user agents;
  protect and retain them according to applicable privacy requirements.

## Dependency and release gates

Release CI separately audits the exact locked dependency graphs for:

- core runtime;
- OAuth, notifications, and Redis runtime extras;
- development and test tooling;
- stress/benchmark tooling.

The release gate also runs migration rehearsal, the complete PostgreSQL and
Redis test suite, packaging checks, and the black-box example API checks.

## Incident response

For suspected credential or privilege compromise:

1. Revoke affected sessions and API keys.
2. Disable or narrow implicated roles and memberships.
3. Rotate the signing key if JWT forgery or secret exposure is possible; this
   invalidates existing signed tokens.
4. Review user audit events, login history, application logs, and gateway logs.
5. Preserve evidence before retention or cleanup jobs remove transient state.
6. Patch, migrate, run the release-readiness workflow, then document the event.
