# Current Implementation Status

**Updated**: 2026-03-19
**Purpose**: Record what is already implemented in code, where implementation intentionally differs in small ways from earlier strategy docs, and which known gaps still remain.

This document is a reality check for maintainers. It is not a roadmap and it is not a full changelog. When this document conflicts with older planning docs, the code and tests should be treated as the source of truth.

## Completed Slices

### User Lifecycle and Access Revocation

- User deletion is retained delete, not physical delete.
- Deleted users are marked with `UserStatus.DELETED` and `deleted_at`.
- Deleted-user emails remain permanently reserved for create and invite flows.
- User delete runs as one service-centric workflow:
  - revoke active entity memberships
  - revoke exceptional direct user-role memberships
  - revoke refresh tokens in place
  - revoke user-owned API keys in place
- Deleted users cannot authenticate.
- Restore exists and is identity-only:
  - restores user status and clears `deleted_at`
  - does not restore memberships, direct roles, refresh tokens, or API keys

### OAuth and Human-User Identity Rules

- Human users require email.
- OAuth-backed human users also require a usable email for new user completion.
- If an OAuth provider does not provide a usable email, the system does not auto-complete a new active user.
- Existing mapped social accounts remain usable even if the provider later omits email on a subsequent callback, because the identity is already linked to a retained local user.
- Apple ID tokens are now parsed through verified JWKS-based validation in the shared OAuth helper path.
- Invalid provider ID tokens are rejected instead of falling back to unverified parsing.
- Locked users cannot obtain new local tokens through OAuth callback login or invite-accept auto-login.

### User Audit and Membership History

- User status changes, delete, restore, direct-role assignment, and direct-role revocation are recorded in typed `user_audit_events`.
- Profile updates, email changes, password changes, invite lifecycle events, login events, and password-reset lifecycle events are also recorded in the same user-centric audit timeline.
- Entity membership lifecycle events are mirrored into the same user-centric audit timeline.
- Entity membership history remains append-only and independently queryable.

### Role and Permission Definition History

- Role definition history exists and records CRUD, permission-set changes, and ABAC condition-group/condition changes.
- Permission definition history exists and records CRUD, tag changes, and ABAC condition-group/condition changes.
- Both history models now store dedicated lifecycle snapshot columns (`status_snapshot`) rather than relying only on `before`/`after` JSON.

### Role and Permission Lifecycle Enforcement

- Roles and permissions are retained with lifecycle status instead of being physically deleted.
- Delete operations archive definitions.
- Archived or otherwise non-active roles and permissions no longer grant permissions.
- Archived or otherwise non-active roles cannot be assigned through memberships or direct user-role assignment.
- Normal reads hide archived role and permission definitions.

## Accepted Implementation Nuances

These are intentional implementation details that are slightly more specific than the original strategy notes.

### OAuth Existing-Link Behavior

- The strict email requirement is enforced for new OAuth-backed user completion.
- A previously linked social account can still authenticate without a fresh provider email on a later callback.
- Reason: the identity is already bound to a retained local user with a reserved email, so denying that flow would create an avoidable lockout without improving identity integrity.

### Permission `status` and `is_active`

- Permission lifecycle truth now lives in `status`.
- `is_active` is retained as a compatibility shim and mirrors the active/inactive part of lifecycle state.
- Reason: existing API and client contracts already used `is_active`, so compatibility was preserved while moving lifecycle enforcement to the more explicit `status` model.

### Delete Endpoint Naming vs Runtime Semantics

- Some API surfaces still use `DELETE` verbs or “delete” names for actions that now archive or revoke.
- This currently applies to user delete, role delete, permission delete, and API key delete/revoke behavior.
- Reason: the runtime semantics were changed first to preserve client compatibility. Renaming those contracts would be a separate API-compatibility decision.

### Config Empty-Root Validation

- `PUT /entity-types` defensively checks that `allowed_root_types` is not empty.
- In normal HTTP use, the request schema rejects an empty list before the route-level guard runs.
- Reason: the route still protects the merged-config invariant even if data reaches it outside normal request validation.

### OAuth Provider Factory Exports

- The documented `outlabs_auth.oauth.providers` import path now exposes both the concrete provider classes and the `httpx-oauth` factory helpers.
- The factory implementation lives in `outlabs_auth.oauth.provider_factories`.
- Reason: the earlier sibling module name `oauth/providers.py` was shadowed by the `oauth/providers/` package, which made the documented factory-helper import path effectively unreachable.

### Admin UI Repository Boundary

- The Nuxt admin UI no longer lives inside this Python repository.
- The active frontend codebase now lives in the sibling repository `../OutlabsAuthUI` (local workspace `/Users/macbookm3/Documents/projects/OutlabsAuthUI`).
- Reason: backend and frontend lifecycle now move independently, and keeping the UI in its own repository removes stale in-repo build/release assumptions from this package.

## Known Remaining Gaps

### Runtime / Product Gaps

- The bundled provider set no longer has an Apple-style fail-open ID-token path; Google, GitHub, and Facebook currently use provider userinfo/email APIs instead of local ID-token parsing.
- A broader provider-by-provider hardening review still remains for semantics and operational guidance, especially where provider metadata does not perfectly map to local identity policy.
- The next concrete OAuth follow-up is provider-semantic hardening: define and codify exactly when bundled-provider email/verification metadata is trusted for auto-link and auto-create flows.
- Some legacy API naming still suggests hard delete even where the implementation is now retained lifecycle.

### Test Coverage Gaps

- A full-suite coverage audit on 2026-03-19 now passes with `664` tests green, `85%` total Python line coverage, and no warning output.
- The recent lifecycle and auth-hardening slices are in comparatively good shape:
  - `services/user.py`
  - `routers/users.py`
  - `routers/oauth.py`
  - `services/user_audit.py`
  - `services/cache.py`
  - `services/policy_engine.py`
  - `services/notification.py`
- A focused management-coverage pass also now exists for role, permission, membership, and API-key management flows:
  - router callback/error-path coverage for `routers/api_keys.py`, `routers/permissions.py`, and `routers/roles.py`
  - service-management coverage for `services/api_key.py`, `services/permission.py`, `services/role.py`, and `services/membership.py`
- In the current post-pass full-suite coverage run on 2026-03-19, these management modules now sit at:
  - `routers/api_keys.py`: `90%`
  - `routers/permissions.py`: `95%`
  - `routers/roles.py`: `95%`
  - `services/api_key.py`: `89%`
  - `services/role.py`: `94%`
  - `services/membership.py`: `86%`
  - `services/permission.py`: `95%`
- The auth/OAuth follow-up slice now has direct shared-layer and provider-internal coverage, with the current full-suite coverage run placing:
  - `services/auth.py`: `100%`
  - `authentication/strategy.py`: `100%`
  - `authentication/transport.py`: `100%`
  - `oauth/provider.py`: `97%`
  - `oauth/provider_factories.py`: `81%`
  - `routers/oauth.py`: `86%`
  - `routers/oauth_associate.py`: `100%`
  - `routers/oauth_utils.py`: `100%`
  - `oauth/providers/google.py`: `100%`
  - `oauth/providers/github.py`: `100%`
  - `oauth/providers/facebook.py`: `100%`
  - `oauth/providers/apple.py`: `100%`
- The shared auth/JWT/config handler slice now has direct utility and handler coverage, with the current full-suite coverage run placing:
  - `utils/jwt.py`: `100%`
  - `fastapi.py`: `100%`
  - `services/config.py`: `100%`
  - `routers/config.py`: `100%`
- The auth core/dependency wiring follow-up slice now has direct lifecycle and guard coverage, with the current full-suite coverage run placing:
  - `core/auth.py`: `100%`
  - `dependencies/__init__.py`: `99%`
- The observability integration follow-up slice now has direct request-context, middleware, and metrics-router coverage, with the current full-suite coverage run placing:
  - `observability/dependencies.py`: `100%`
  - `observability/middleware.py`: `100%`
  - `observability/router.py`: `100%`
- The database plumbing slice now has direct configuration, factory, session-generator, and registry coverage, with the current full-suite coverage run placing:
  - `database/engine.py`: `100%`
  - `database/registry.py`: `100%`
- The entity follow-up slice now has direct service-management/cache coverage and router callback-path coverage, with the current full-suite coverage run placing:
  - `services/entity.py`: `95%`
  - `routers/entities.py`: `99%`
- The remaining meaningful coverage gaps are now mostly broader infrastructure and operational surfaces rather than missing auth or lifecycle product slices:
  - medium-priority observability and platform internals such as `observability/service.py`, `services/activity_tracker.py`, `middleware/resource_context.py`, and some remaining router/service breadth like `routers/memberships.py`
  - lower-priority low-coverage areas still exist in CLI, workers, optional notification channel adapters, Redis client plumbing, and migration bootstrap glue

### Documentation Gaps

- Several major docs have now been reconciled (`CURRENT_IMPLEMENTATION_STATUS.md`, `USER_AUDIT_LOG_STRATEGY.md`, `SECURITY.md`, `LIBRARY_ARCHITECTURE.md`, `COMPARISON_MATRIX.md`, `API_DESIGN.md`, `DESIGN_DECISIONS.md`, `DEPENDENCY_PATTERNS.md`, `ENTITY_DELETION_AND_MEMBERSHIP_HISTORY.md`).
- The in-repo `auth-ui/` subtree has been removed and the repo now documents the external admin UI boundary through `README.md`, `AUTH_UI.md`, `AUTH_UI_PARITY_GAPS.md`, and related release/maintainer docs.
- Remaining stale content is mostly in broader roadmap/design collections rather than the operational and lifecycle docs.
- The docs index now includes this status file, but the broader planning docs are not yet fully reconciled with current retained-lifecycle behavior.

## Newly Added Coverage In This Slice

- OAuth router callback-path coverage for authorize, callback success, invalid state, associate-state binding, and association-collision branches.
- Config router API coverage for public reads, superuser-only updates, merge/persist behavior, and empty-root rejection at the request layer.
- Direct policy-engine unit coverage for the operator matrix, grouped SQL-condition semantics, and context helper methods.
- Direct cache-service unit coverage for key generation, get/set helpers, targeted invalidation, publish helpers, listener dispatch, and Redis-unavailable no-op behavior.
- Entity and membership read-route integration coverage for `/children`, `/path`, entity-member pagination, `/memberships/entity/{id}/details`, and `/memberships/user/{id}` include-inactive behavior.
- History pagination and filter-combination coverage for user audit events, user membership history, and role/permission definition history list surfaces.
- Notification-service unit coverage for channel filtering, fire-and-forget dispatch, delivery failure isolation, and pre-dispatch exception handling.
- User-audit integration coverage for profile/email changes, admin password changes, login failures, successful login, password reset request/completion, invite create/resend/accept, and invite-accept auto-login audit metadata.
- Apple provider unit coverage for verified ID-token parsing and provider-error wrapping, plus shared OAuth-helper coverage that rejects invalid verified ID tokens.
- OAuth callback coverage that rejects locked existing users before issuing local tokens.
- Bundled OAuth provider coverage for Google, GitHub, and Facebook user-info mapping, plus shared-helper coverage that prefers access-token userinfo when available.
- Shared auth strategy coverage for JWT blacklist/staleness handling, API-key owner lookup, service-token validation, superuser fallback, and anonymous access.
- OAuth security-helper coverage for state, nonce, PKCE generation/verification, URL building, and constant-time comparison.
- OAuth provider-base coverage for authorization URL generation, HTTP-client lifecycle, default refresh behavior, and unsupported revoke behavior.
- Bundled-provider flow coverage for Google/GitHub/Facebook/Apple exchange, refresh, revoke, and provider-specific authorization behavior.
- Public OAuth factory-helper coverage, plus the package-export fix that makes `from outlabs_auth.oauth.providers import get_google_client` resolve to the documented helper path again.
- Direct `OutlabsAuth` lifecycle coverage for configuration validation, initialize/startup orchestration, backend/dependency wiring, session and unit-of-work helpers, shutdown cleanup, and FastAPI instrumentation warning behavior.
- Direct `AuthDeps` guard coverage for inactive/unverified auth fallback, optional auth, activity tracking dispatch, missing/invalid auth-result identities, ABAC context merge, missing service/session failures, source and superuser enforcement, and dynamic dependency signatures.
- Permission, role, and API-key router callback-path coverage for validation, ownership/visibility, scoped-create rules, generic 500 logging, and ABAC error translation.
- API-key service coverage for scope/IP helpers, rate-limit enforcement, tree access checks, hard delete, and usage-counter sync behavior.
- Direct `AuthService` lifecycle coverage for login failure/lockout, login success notifications and hash upgrade, stateless/stateful logout blacklisting, refresh-token invalid/stale/revoked handling, current-user stale-token enforcement, reset/invite credential flows, and helper methods, taking `services/auth.py` to `100%` in the full-suite run.
- Permission service coverage for list/search/tag/bulk-create management helpers.
- Role service coverage for scoped list visibility, entity-available role resolution, auto-assigned role discovery, and entity availability checks.
- Membership service coverage for user/entity query helpers, orphan discovery, and retroactive auto-assigned role application.
- Entity service coverage for create/update lookup paths, hierarchy validation, cache reads/writes/invalidation helpers, suggested-type discovery, ancestor traversal, and retained-archive delete orchestration.
- Entities router callback-path coverage for list filters, CRUD responses, move permission checks, descendants, path, children, and paginated member response shaping.
- Permission service lifecycle coverage for status/cache helpers, require-any/all enforcement, tag replacement/clearing, archived lookup behavior, and system-permission guards.
- Role service lifecycle coverage for scoped/global creation guards, update/delete constraints, entity-type permission overrides, direct-role reactivation semantics, and archived-entity direct-role revocation.
- Membership service lifecycle coverage for add-member validation, in-place membership updates, remove/suspend/reactivate paths, user-wide revocation, entity-archive revocation, and membership-history reads.
- A runtime bugfix landed with this slice: `permission_service.delete_permission()` now reloads the archived permission with tags before building the post-delete history snapshot, avoiding an async lazy-load failure on tagged permission archive.
- Direct permission and role service ABAC-definition coverage now exists for mutable-definition guards, condition-group and condition CRUD, user-permission helper paths, cache invalidation, and audit snapshot helpers.
- Expanded permission and role router callback-path coverage now includes list/read/update/delete success paths, ABAC condition-group and condition list responses, scoped-create rejection, runtime-error logging, and invalid-input translation branches.
- Provider edge-case coverage for Apple, GitHub, and Google now covers private-key/JWKS setup, client-secret generation, PKCE exchange branches, network/provider error wrapping, fallback email handling, and revoke/refresh error paths.
- OAuth associate router helper/callback coverage now includes state-token decoding failures, invalid authenticated-user IDs, missing-user handling, route-name callback URL generation, existing-link refresh paths, and same-provider collision handling.
- OAuth utility coverage now includes `get_id_email` fallback, missing-email rejection, unsupported-provider rejection, and provider-token encryption failure/success paths.
- Facebook provider coverage now includes successful code exchange plus network/non-200 failure handling for code exchange, user-info reads, long-lived token exchange, and unsupported refresh semantics.
- Role and permission helper coverage now includes permission-name parsing, wildcard/scope grant helpers, entity-local grant rules, context-aware permission selection, cache-eligibility helpers, assignable-type normalization, and snapshot/delta helper behavior.
- The deprecated `HTTP_422_UNPROCESSABLE_ENTITY` usage in the API-key router was updated to `HTTP_422_UNPROCESSABLE_CONTENT`, and the full suite no longer emits that warning.
- Shared auth strategy coverage now includes missing-user-service fallback, expired/invalid token handling, API-key empty/error branches, service-token invalid-type and validator-failure handling, and superuser fallback/error branches, taking `authentication/strategy.py` to `100%`.
- Transport coverage now includes real request extraction for bearer, API-key, header-prefix mismatch, cookie, and query-param delivery paths, taking `authentication/transport.py` to `100%`.
- JWT utility coverage now includes no-audience verification, token-type mismatch, expired/invalid decode paths, expiration helpers, and access-vs-refresh token-pair claim behavior, taking `utils/jwt.py` to `100%`.
- Config service and router coverage now includes direct CRUD/default/seed behavior, direct route-handler merge and route-level guard paths, audit-actor propagation, and observability logging, taking `services/config.py` and `routers/config.py` to `100%`.
- FastAPI exception-handler coverage now includes nested HTTP detail extraction, invalid-mode validation, validation/integrity/value/http error responses, and unexpected-exception logging/fallback behavior, taking `fastapi.py` to `100%`.
- Database engine coverage now includes URL normalization, preset defaults, pooled vs serverless engine creation, session-factory defaults, and commit/rollback behavior in the shared session dependency, taking `database/engine.py` to `100%`.
- Database registry coverage now includes preset-specific model/table sets and explicit metadata registration, and a runtime fix landed with this slice: `ModelRegistry.get_models()` now includes `SocialAccount`, `OAuthState`, and `ActivityMetric` so the registry contract matches its documented core model list and table expectations.
- Core auth wiring coverage now includes direct migration handoff, Redis/cache/entity/activity service initialization, activity-tracking guardrails, token-cleanup and activity-sync scheduler loops, and the unexpected middleware-runtime branch in `instrument_fastapi()`, taking `core/auth.py` to `100%`.
- Observability dependency coverage now includes request-context capture, structured log forwarding, auth-wrapped context helpers, dependency-factory guardrails, correlation-ID middleware passthrough/generation/cleanup, and the metrics router enablement and response path, taking `observability/dependencies.py`, `observability/middleware.py`, and `observability/router.py` to `100%` and `dependencies/__init__.py` to `99%`.
