# OutlabsAuth Security Remediation and Release Closeout Report

**Audit opened:** 2026-08-02

**Closeout updated:** 2026-08-03

**Audited release:** `outlabs-auth==0.1.0a28` (`056194f`)

**Security baseline:** `0.1.0a27` (`8be0699`)

**Companion release:** `outlabs-taskq==0.1.0a21` (`a0511ce`)

**Status:** **GO for the library release; HOLD for full operational closeout**

**Scope:** library controls, migrations, release workflow, supported consumers, and deployment evidence

## Executive decision

The six security workstreams identified on 2026-08-02 are implemented, tested,
and released. The library code has no unresolved Critical, High, Medium, or Low
finding in that remediation scope. `0.1.0a28` is the release that consumers
should install: it contains the complete a27 security baseline plus the router
startup lifecycle correction described below.

The code release is green. The complete operational rollout is not yet eligible
to be called done for two explicit reasons:

1. one LAN-only supported consumer was unreachable from the release network,
   so its fresh backup, owner migration confirmation, a28/a21 deployment, and
   live canary remain unexecuted; and
2. one hosted consumer requires confidential deployment-credential rotation.
   New builds are contained, but the prior values must still be revoked.

This report is the sole authoritative security audit for this release line.
Obsolete security drafts were removed. The performance audits and user-audit
strategy remain because they cover different subjects.

## Published artifacts

| Artifact | State | Evidence |
|---|---|---|
| OutlabsAuth `0.1.0a28` | Published to PyPI; tag present | wheel `800630d722b31145a6c8dd8ae5bc83999414fcefa1cacfdebbcf69d598b14047`; sdist `ba49e4a6aebed35fa022f0a4a71f0c380295e28a0bf5117e619be5c83fa52040` |
| OutlabsAuth release readiness | Passed | [GitHub Actions run 30804328115](https://github.com/outlabsio/outlabsAuth/actions/runs/30804328115) |
| TaskQ `0.1.0a21` | GitHub prerelease published | wheel `0793bff12c4973865f58db6ddeb31e790e2a35a8712de27ba69cf404a9adc81a`; sdist `e32eabeea73212c2eb4524201f16fa6c9a44c2dfc8eb4b6a7a22881c58445b19` |
| TaskQ CI | Passed | [GitHub Actions run 30805158877](https://github.com/outlabsio/outlabs-taskq/actions/runs/30805158877) |

TaskQ a21 replaces the former exact Auth a27 adapter pin with the bounded range
`outlabs-auth>=0.1.0a27,<0.2.0`. Consumer lockfiles still select and hash exact
artifacts. This lets consumers take compatible 0.1 security patches without a
new TaskQ release for every patch.

## Resolution of the six security workstreams

### 1. Authorization and delegation containment — resolved

- Every invite, membership, role, entity override, auto-assignment, and ABAC
  grant path enforces that a caller cannot grant authority they do not hold.
- Entity membership creation requires `membership:create_tree` in context.
- Only a superuser may invite another superuser.
- Regression tests cover direct, implicit, and authority-widening paths.

### 2. Password-login hardening — resolved

- Login uses IP-keyed sliding-window throttling with distributed Redis
  enforcement and fail-closed production defaults.
- Unknown users, wrong passwords, and locked accounts share one external
  credential response; attempt budgets and lock timing remain internal.
- The library trusts the ASGI peer address, not arbitrary forwarding headers.

### 3. OAuth PKCE and OIDC nonce binding — resolved

- Authorization-code flows require PKCE S256.
- OAuth state is single-use, browser-bound, row-locked, and consumed before
  token exchange.
- Browser binding and OIDC nonce are stored separately.
- ID tokens are verified for signature, algorithm, key ID, issuer, audience,
  time claims, subject, and constant-time nonce equality.

### 4. Dependencies and release gates — resolved

- Exact core, runtime-extra, development/test, and stress graphs are audited
  independently with strict dependency auditing.
- Release CI gates the complete PostgreSQL + Redis suite, both live examples,
  migration rehearsals, artifact metadata, lock validation, and package builds.
- The original draft's `cryptography>=48.0.1` finding was incorrect: the
  official advisory marks versions before 48.0.1 affected. Reproducible audits,
  not manual version inference, are authoritative.

### 5. Feature boundaries, CIDR handling, and operator guidance — resolved

- Disabling invitations removes invite, accept, and resend routes with 404.
- Public `/auth/config` is pre-auth UI data only; the permission catalog is
  protected by `permission:read`.
- IPv4/IPv6 addresses and CIDR networks are validated and canonicalized in
  database and cached API-key paths; invalid rules fail closed.
- Metrics, proxies, Redis, invitation flags, session policy, and secret
  responsibilities are documented.

### 6. Absolute sessions and placeholder-secret rejection — resolved

- Refresh families have a default 90-day absolute lifetime, and access and
  refresh tokens cannot outlive the signed and persisted family deadline.
- Legacy families derive the deadline from their creation time.
- Known placeholder secrets are rejected even when long enough; runnable
  examples load generated secrets from the environment.

## Post-baseline defects and corrections

### Transaction teardown race — closed in a27

The EnterpriseRBAC live run exposed a race between FastAPI dependency teardown
and response-start commit/rollback. Unit-of-work finalization is now serialized,
cancellation and `GeneratorExit` are handled, and the live run plus a dedicated
concurrency regression test pass without unhandled session-state errors.

### Primed router startup lifecycle — closed in a28

`prime_fastapi_routing()` prepared services that mounted routers captured, but
startup rebuilt those services. Mounted dependencies could therefore retain a
stale, never-connected Redis-backed API-key service while direct host
dependencies used the connected replacement. a28 preserves and initializes the
primed session factory, services, authentication backends, and dependency
container. It has no database migration.

### Managed-PostgreSQL CLI DSN normalization — open, consumer-contained

The standalone migration CLI forwards libpq-only parameters such as
`sslmode=require` and `channel_binding=require` to asyncpg, which raises
`TypeError: connect() got an unexpected keyword argument 'sslmode'` for a
standard Neon-shaped URL. The real issue is tracked as
[outlabsAuth#10](https://github.com/outlabsio/outlabsAuth/issues/10). The
affected consumer passes its tested application-normalized URL to the CLI, so
its current staging and production migrations succeed. The library CLI should
own this normalization in a future compatible patch.

## Migration verification

Alembic head remains `20260802_0025`; a28 adds no migration.

The verified library paths include empty database to head, downgrade from head
to `20260729_0023` and re-upgrade, populated pre-release upgrade, legacy OAuth
binding preservation, idempotent retry, and packaged-wheel CLI execution.

## Consumer rollout evidence

| Consumer | Source and tests | Database/deployment | Decision |
|---|---|---|---|
| Self-hosted API consumer | PostgreSQL 16 + PostGIS 3.5: **1,431 passed**; Ruff clean; mypy clean across 223 app files. Exact locks select a28/a21. | Production is LAN-only and was unreachable from the release network. No production mutation was attempted without access. | **HOLD** |
| Hosted data API consumer | **1,404 passed**, 13 environment-dependent skipped; Ruff and mypy clean. | A fresh pre-migration schema backup was captured. Auth head is `20260802_0025`. Production runs a28, is healthy with zero restarts, returns 200 internally and publicly, and rejects bad credentials with 401 `INVALID_CREDENTIALS`. | **GO** |
| Hosted intake BFF consumer | **85 passed**, 83 environment-dependent skipped; Ruff and mypy clean. | Staging and production deploys succeeded. Both run migrations to head and complete application startup. Production health returns 200 and the bad-credential canary returns 401 `INVALID_CREDENTIALS`. | **Runtime GO; confidential security closeout pending** |

## Deployment-security finding

Every staging and production variable for the affected hosted consumer is now
runtime-only. Fresh builds no longer inject the environment set as Docker build
arguments. Confidential rotation and revocation are tracked in the consumer's
private operations repository; no credential class or value is recorded here.

Named per-host commits, infrastructure identifiers, backups, and unrelated
consumer operational debt are retained privately by the maintainer. This public
report records only the consumer-agnostic evidence relevant to the library
release contract.

## Final operational closeout gate

The release may be called fully done only after both rows below are green:

- [ ] The LAN-only consumer is reachable; a fresh production backup is
  captured; owner application and OutlabsAuth migrations are confirmed; the
  a28/a21 image is deployed; and installed versions, health, environment,
  restart count, and a live auth canary pass.
- [ ] The confidential hosted-consumer credential rotation is complete,
  staging and production are redeployed, prior values are revoked, and the
  private rotation issue is closed without exposing values.

Until those checks are complete, the accurate verdict is: **library release
ready and published; consumer rollout materially complete but not operationally
closed**.

## Scope boundary

This decision covers the repository release and the named consumer deployment
evidence. It does not substitute for an independent penetration test, a live
external-provider OAuth exercise, a consumer-specific authorization-policy
review, or future changes after the recorded revisions.
