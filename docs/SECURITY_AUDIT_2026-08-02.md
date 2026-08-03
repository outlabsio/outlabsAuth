# OutlabsAuth Security Remediation and Release-Readiness Report

**Date:** 2026-08-02
**Base revision:** `main` at `7d54919`
**Candidate version:** `0.1.0a27`
**Status:** GO for commit, remote CI, and release
**Scope:** OutlabsAuth library, database migrations, examples, documentation, dependency graphs, and release workflow

## Executive decision

The six security workstreams identified during the 2026-08-02 review are implemented and locally verified. There are no unresolved Critical, High, Medium, or Low code findings in this remediation scope.

The candidate passed the complete test suite against isolated PostgreSQL 16 and Redis 7 services, both live example applications, fresh and seeded migration rehearsals, four exact dependency audits, formatting/lint checks, lock validation, release-metadata validation, and package builds.

This report replaces the earlier draft audit and is the authoritative security status for this release candidate. The obsolete historical security reports were removed. Performance reports and the user-audit-log strategy remain because they cover different subjects.

## Correction to the original draft

The original draft mixed confirmed issues with an incorrect supply-chain interpretation. In particular, it described `cryptography>=48.0.1` as admitting a version affected by `GHSA-537c-gmf6-5ccf`. The official advisory identifies versions **before 48.0.1** as affected and 48.0.1 as the patched version. The declared floor is therefore correct; the candidate lock resolves 50.0.0. See the [official GitHub advisory](https://github.com/advisories/GHSA-537c-gmf6-5ccf).

Supply-chain readiness is now based on reproducible `pip-audit --strict` checks of every exact locked graph, not manual inference from version numbers.

## Resolution of the six workstreams

### 1. Authorization and delegation containment — resolved

All runtime grant paths now enforce “a caller cannot grant authority they do not hold.”

- Invite-time direct roles, entity memberships, explicit entity roles, and implicit auto-assigned roles are checked before a user is created.
- Entity membership creation requires `membership:create_tree` in the target entity context.
- Membership add/update paths include entity-aware containment and implicit-role evaluation.
- Role create, permission replacement, permission attachment, activation, global/scope widening, hierarchy widening, auto-assignment, assignable entity-type widening, and ABAC condition mutations are contained.
- Entity-type permission overrides are included when calculating the effective authority carried by a role.
- Only a superuser may invite another superuser.
- Regression tests prove that a limited actor cannot grant a powerful global role or smuggle authority through an implicit auto-assigned role.

**Disposition:** closed.

### 2. Password-login hardening — resolved

- Login has an IP-keyed sliding-window limiter.
- Redis provides distributed enforcement when configured.
- The default Redis failure mode is `fail_closed`; a local fallback requires explicit configuration.
- In-memory limiter namespaces prevent unrelated OutlabsAuth instances in one process from sharing counters.
- The trusted peer address is taken from ASGI `request.client`; raw forwarding headers are not trusted by the library.
- Unknown users, wrong passwords, and locked accounts return the same credential response.
- Attempt counters and lock timing remain in internal audit data and are no longer disclosed to the caller.
- Rate-limit responses return HTTP 429 with retry details; unavailable required authentication infrastructure returns HTTP 503.

**Disposition:** closed.

### 3. OAuth 2.0 PKCE and OIDC nonce binding — resolved

- OAuth authorization-code flows use PKCE S256 and persist the verifier server-side.
- The callback uses the persisted verifier during token exchange.
- OAuth state is single-use, browser-bound, row-locked, and consumed before external token exchange or account work.
- Browser binding and OIDC nonce are separate persisted values.
- OIDC providers receive a cryptographic nonce in the authorization request.
- Returned ID tokens are signature-verified and checked for algorithm, key ID, issuer, audience, expiry, issued-at time, subject, and constant-time nonce equality.
- Google receives stable discovery/JWKS metadata when OpenID scopes are active; Apple’s ID-token path remains verification-enabled.
- A nonce mismatch rejects the callback after consuming the state, preventing replay retries.

Migration `20260802_0024` adds `oauth_states.browser_binding`, preserves legacy browser-binding data, and clears the legacy overloaded nonce value.

**Disposition:** closed.

### 4. Dependencies and CI release gates — resolved

- The lock was regenerated and upgraded; the candidate resolves `cryptography 50.0.0` and `werkzeug 3.1.6`.
- `werkzeug>=3.1.6` is an explicit floor for notification and aggregate dependency graphs.
- CI audits four exact locked graphs independently: core, runtime extras, development/test, and stress.
- Audits run with `pip-audit --strict --no-deps --disable-pip` and a bounded network timeout.
- CI now release-gates the full PostgreSQL + Redis suite, package/CLI checks, a populated-schema upgrade rehearsal, and live EnterpriseRBAC and SimpleRBAC examples.

**Disposition:** closed.

### 5. Feature boundaries, CIDR handling, and deployment documentation — resolved

- `enable_invitations=False` disables invite, accept-invite, and resend-invite routes with HTTP 404.
- Public `/auth/config` exposes only pre-authentication UI configuration and performs no permission-catalog database query.
- The permission catalog moved to protected `/auth/config/permissions` and requires `permission:read`.
- API-key IP allowlists now validate, canonicalize, and match IPv4/IPv6 addresses and CIDR networks in both database and cached-snapshot paths.
- Invalid stored IP rules fail closed, as does a whitelist check without a client address.
- Metrics documentation requires network restriction or host-level authentication.
- Security documentation now accurately describes API-key controls, Redis-backed and per-process rate limiting, invitation flags, public configuration, session policy, secret generation, and deployment responsibilities.

**Disposition:** closed.

### 6. Absolute sessions and secret-placeholder rejection — resolved

- Refresh-token families have an optional absolute lifetime, defaulting to 90 days.
- Access and refresh expiry are capped at the family deadline even while tokens rotate.
- The signed `session_exp` claim and persisted `family_expires_at` prevent an active family from extending indefinitely.
- Legacy stored families derive an absolute deadline from the family creation time; expired families are revoked and rejected.
- Migration `20260802_0025` adds the nullable family deadline without hard-coding a deployment-specific backfill policy.
- Known placeholder markers such as `change-me`, `generate-with-secrets`, and `your-secret-key` are rejected even when they meet the length requirement.
- `.env.example` no longer contains a secret-shaped placeholder, and runnable examples require `SECRET_KEY` from the environment.

**Disposition:** closed.

## Additional release-gate defect found and fixed

The live EnterpriseRBAC run exposed a transaction teardown race that ordinary exit-code checks did not catch: a denied request could start FastAPI dependency teardown while response-start middleware was still committing, allowing SQLAlchemy’s session context to close mid-commit and emit an unhandled `IllegalStateChangeError` task.

Unit-of-work finalization is now serialized with a per-state async lock. Dependency teardown handles `GeneratorExit` and cancellation, waits for a middleware-owned commit/rollback to finish, and never finalizes the same session twice. A dedicated concurrency regression test reproduces this ordering. The Enterprise live run was then repeated with log scanning and completed without unhandled task errors.

**Disposition:** closed.

## Migration verification

Alembic head is `20260802_0025`.

The following paths passed:

- empty database to head;
- head downgrade to `20260729_0023`, then upgrade back to head;
- populated pre-release schema to head;
- legacy OAuth state data preserved into `browser_binding` while `nonce` is cleared;
- repeated migration invocation is idempotent;
- migration through the built wheel/CLI path.

Consumers must run `outlabs-auth migrate` before directing traffic to the new package.

## Verification evidence

| Gate | Result |
|---|---|
| Complete pytest suite, PostgreSQL 16 + Redis 7 | **1,080 passed**, 0 failed |
| EnterpriseRBAC live HTTP integration | **47/47 passed**, clean server log |
| SimpleRBAC live HTTP integration | **passed** |
| Seeded pre-release upgrade rehearsal | **passed** |
| Packaged CLI migration flow | **passed** |
| Dependency audit: core | **0 known vulnerabilities** |
| Dependency audit: runtime extras | **0 known vulnerabilities** |
| Dependency audit: development/test | **0 known vulnerabilities** |
| Dependency audit: stress | **0 known vulnerabilities** |
| Black on changed Python files | **passed** |
| Ruff repository check | **passed** |
| `git diff --check` | **passed** |
| `uv lock --check` | **passed** |
| Release metadata synchronization | **0.1.0a27 in sync** |
| Source distribution and wheel build | **passed** |
| CLI version command | **0.1.0a27** |

The pytest run emitted 139 non-failing warnings, chiefly intentionally short signing keys in legacy test fixtures and upstream/deprecation notices. Production HS* secrets remain subject to the library’s strength and placeholder validation. These warnings do not represent a failed security control, but the deprecation warnings should be removed during routine maintenance before their upstream removal dates.

Repository-wide mypy is not a configured release gate and still reports 34 pre-existing baseline errors. Targeted checks of the changed authentication, JWT, and OAuth modules passed after their newly introduced errors were corrected. Making the entire historical mypy baseline strict should be tracked as a separate quality project rather than represented as completed by this security remediation.

## Release decision and operator requirements

The code is ready to commit and send through remote CI. Publishing was not performed as part of this remediation.

Before deployment, each consumer must:

1. apply migrations through `20260802_0025`;
2. provide a unique generated `SECRET_KEY` and never reuse an example or placeholder value;
3. configure reachable Redis for distributed login limits and other fail-closed controls in multi-worker/production deployments;
4. ensure the ASGI peer address is normalized by a trusted proxy layer rather than passing arbitrary forwarding headers through as trusted client identity;
5. restrict `/metrics` at the network or host-auth layer;
6. validate real OAuth provider credentials, redirect URIs, issuer/audience values, and JWKS reachability in the deployment environment.

## Scope boundary

This decision covers the repository candidate and local release infrastructure. It does not substitute for a third-party penetration test, a live external-provider OAuth exercise, consumer-specific authorization policy review, secret management review, or the remote CI result on the eventual commit. Any code or dependency change after this report invalidates the recorded test evidence and requires rerunning the applicable gates.
