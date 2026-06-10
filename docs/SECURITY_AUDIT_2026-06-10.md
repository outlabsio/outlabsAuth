# OutlabsAuth — Security Audit

**Date:** 2026-06-10
**Scope:** Full library security review — authentication, tokens & secrets, authorization & privilege boundaries, multi-tenant isolation, transport/HTTP, input handling, dependency risk.
**Method:** Source review of `outlabs_auth/` (services, routers, dependencies, authentication strategies, oauth, utils, schemas, config). The three Critical findings and the fail-open scope default were re-verified directly against the code.

> **Confidence key:** ✅ = verified directly during this audit · ◑ = code-cited, high confidence · ⚠️ = flagged with an open question (see the finding).

---

## Executive summary

The library is **well-built on the cryptographic primitives** — Argon2id passwords, `secrets`-based token generation, constant-time comparisons in the sensitive spots, SHA-256 over high-entropy API keys, PyJWT (not the CVE-prone `python-jose`), encrypted OAuth tokens at rest, mass-assignment systematically prevented, and response schemas that don't leak secrets. That floor is solid.

The serious problems are at the **authorization boundary**, not the crypto. Three Critical issues form a **single privilege-escalation chain**: a non-superuser admin with ordinary grants can define or assign a role carrying `*:*`, attach it to their own account, and — because user-management endpoints don't scope the target to the caller's tenant — reach across tenants. The same root cause underlies all three: **missing delegation containment** (no check that a grantor already holds what they hand out). Notably, *the API-key subsystem already implements this control correctly* (`api_key_policy.calculate_grantable_scopes` intersects owner∩actor scopes) — the fix is to extend that same pattern to role/permission grants and user targeting.

Separately, the **primary bearer-auth path accepts 30-day refresh tokens as access tokens**, collapsing the 15-minute access-token window.

| Severity | Count | Findings |
|---|---|---|
| 🔴 Critical | 3 | SEC-1, SEC-2, SEC-3 |
| 🟠 High | 5 | SEC-4 … SEC-8 |
| 🟡 Medium | 5 | SEC-9 … SEC-13 |
| ⚪ Low / Info | 7 | SEC-14 … SEC-20 |

---

## Remediation status (updated 2026-06-10)

| Finding | Status | Notes |
|---|---|---|
| SEC-1 (refresh-as-access) | ✅ Fixed | `type=="access"` enforced in `JWTStrategy.authenticate` |
| SEC-2 (role-assign escalation) | ✅ Fixed | Delegation-containment guard (`routers/_authz_utils.py`) |
| SEC-3 (role-permission escalation) | ✅ Fixed | Same guard on role create/update/add-permissions |
| SEC-4 (cross-tenant user access) | ⏸ Deferred | Design question — see `docs/SEC-4_TENANT_ISOLATION_INVESTIGATION.md` |
| SEC-5 (API-key lockout) | ✅ Fixed | Posture made honest — 32-byte keys need no lockout; a per-IP throttle would harm legit high-TPS workers (gateway's job) |
| SEC-6 (require `exp`) | ✅ Fixed | `options={"require":["exp"]}` on all decode paths |
| SEC-7 (login timing) | ✅ Fixed | Dummy Argon2 verify on user-not-found |
| SEC-8 (422 echoes password) | ✅ Fixed | `input`/`ctx` scrubbed from validation errors |
| SEC-9 (weak secret) | ✅ Fixed | `AuthConfig` rejects HS* secrets < 32 chars |
| SEC-10 (OAuth nonce) | ⏸ Deferred | Live flow uses httpx-oauth; OIDC nonce binding is a focused follow-up |
| SEC-11 (Apple verify) | ✅ Fixed | `parse_id_token(verify=True)` is now the default |
| SEC-12 (`python-multipart`) | ✅ Fixed | Floor raised to `>=0.0.18` |
| SEC-13 (empty-scope fail-open) | ✅ Fixed | Narrowed to integration principals — `principal_scopes_allow_permission` fails closed on empty allowed-scopes; user/worker keys unchanged (owner-bounded). Service tokens were already fail-closed. |
| SEC-14 (unverified-decode helpers) | ✅ Fixed | Warned + confirmed unused in any auth decision |
| SEC-15 (passwordless enumeration) | ✅ OK | Endpoint already returns uniformly; per-process rate-limiter Redis caveat documented |
| SEC-17 (no password max_length) | ✅ Fixed | `max_length=128` on all password fields |
| SEC-18 (CookieTransport CSRF) | ✅ Documented | Warning added — host must add CSRF + `Secure`/`HttpOnly`/`SameSite` |
| SEC-19 (swallowed backend errors) | ✅ Fixed | Unexpected backend exceptions now logged (still fail-closed) |
| SEC-20 (QueryParamTransport) | ✅ OK | Already warns; not wired by default |

SEC-16 (hardcoded bootstrap secret) was also resolved alongside SEC-9 — `build_bootstrap_config`
now generates an ephemeral secret. Regression tests for the fixed items live in
`tests/unit/test_security_patches.py` and `tests/integration/test_authorization_security.py`.

---

## 🔴 Critical

### SEC-1 ✅ Refresh tokens are accepted as access tokens (missing `type` check on the primary auth path)
- **Location:** `outlabs_auth/authentication/strategy.py:91-149` (`JWTStrategy.authenticate`). Contrast `outlabs_auth/utils/jwt.py` and `services/auth.py:678-684`, which *do* pass `expected_type="access"`.
- **Evidence:** The strategy decodes with `algorithms=[self.algorithm]`, `audience=self.audience` (default `"outlabs-auth"`) and `verify_exp` — then checks `sub`, blacklist, password-staleness and `can_authenticate()`. It **never checks `payload.get("type") == "access"`**. Refresh tokens are minted with the same `aud="outlabs-auth"` and a 30-day TTL. `auth.deps` is wired to this strategy, so every `Depends(auth.deps.require_auth/require_permission(...))` route uses it.
- **Impact:** A 30-day refresh token presented as `Authorization: Bearer <refresh>` authenticates on all protected endpoints, defeating the short access-token lifetime. A leaked/logged refresh token becomes a long-lived API credential. Logout blacklists the access-token `jti`, not the refresh `jti` used this way.
- **Fix:** In `JWTStrategy.authenticate`, after decode: `if payload.get("type") != "access": return None`. For defense-in-depth, give refresh tokens a distinct audience (e.g. `outlabs-auth:refresh`).

### SEC-2 ✅ Any `user:update` holder can grant any role (including superuser-equivalent) to anyone
- **Location:** `outlabs_auth/routers/users.py:1091-1131` (`assign_role_to_user_endpoint`) → `outlabs_auth/services/role.py:1758-1897` (`assign_role_to_user`).
- **Evidence:** The endpoint is gated only by `require_permission("user:update")`. `assign_role_to_user` validates that the user and role exist and that the role is active/non-entity-local — then assigns it. `assigned_by_id` is used **only** for the audit event (role.py:1845, 1862, 1892). There is **no check** that the actor holds the role's permissions, outranks the target, or shares the target's scope.
- **Impact:** A non-superuser with `user:update` (a common admin grant) can assign a global role carrying `*:*` / `role:*` / `user:*` to their own account → effective superuser. Vertical privilege escalation.
- **Fix:** Before assignment, require the actor's effective permission set to be a superset of the target role's permissions (grantor-contains-grantee). Introduce a dedicated `role:assign` permission distinct from `user:update`. Add a scope check on the target user (see SEC-4).

### SEC-3 ✅ Any `role:update` holder can attach arbitrary permissions (including `*:*`) to a role they can see
- **Location:** `outlabs_auth/routers/roles.py:402-448` (`add_permissions` / `remove_permissions`) → `outlabs_auth/services/role.py:1359-1414` (`add_permissions_by_name`); same gap in `set_permissions_by_name` and the `update_role(update_permissions=True)` path.
- **Evidence:** These endpoints require `role:update` and call `_require_role_visibility` — a **scope/visibility** check only. `add_permissions_by_name` resolves the permission names and links them with **no check that the actor possesses those permissions**. A scoped admin who can edit a role in their scope can add `*:*` to it.
- **Impact:** Horizontal-to-vertical escalation: a limited admin mints permissions they were never granted by editing a role's permission set, then (auto-)assigns it. Chains with SEC-2.
- **Fix:** In `add_permissions_by_name` / `set_permissions_by_name` / `update_role`, require the actor to currently hold every permission being added (delegation containment). Forbid non-superusers from adding `*:*`. This mirrors the API-key path's existing `calculate_grantable_scopes` intersection — reuse that pattern.

> **The chain:** SEC-2 + SEC-3 + SEC-4 combine into *define/assign a `*:*` role → self-assign → act across tenants*. One root cause: **no delegation containment.** Fix this pattern once and apply it to all three grant surfaces.

---

## 🟠 High

### SEC-4 ◑ Cross-tenant IDOR on user-management endpoints
- **Location:** `outlabs_auth/routers/users.py:111-123` (`_get_target_user_or_404`) and all mutation callers (update/delete/role-assign/status: lines ~491, 543, 615, 903, 1116, 1186).
- **Evidence:** `_get_target_user_or_404` loads the target purely by id; `actor_user` is passed but unused. No endpoint constrains the target to the actor's `root_entity_id`/entity scope — authorization is a flat `require_permission("user:*")` with no entity context.
- **Impact:** In EnterpriseRBAC, an org-scoped admin can read/modify/deactivate/delete users in **other tenants**. Breaks multi-tenant isolation; amplifies SEC-2.
- **Fix:** Resolve actor scope (`access_scope_service.resolve_for_auth_result`) and assert the target's entity falls within it (superuser bypass). Apply uniformly to user mutation routes.

### SEC-5 ◑ No brute-force protection / lockout on API-key verification (a documented feature that isn't implemented)
- **Location:** `outlabs_auth/services/api_key.py:316-476` (`verify_api_key`); config `api_key_temporary_lock_minutes` (`core/config.py:187`); docstrings claiming "temporary locks / tracks failures" (`api_key.py:60-69`, `strategy.py:208-213`).
- **Evidence:** No code increments a failure counter or sets a temporary lock. A wrong key returns `None` with no throttle. The Redis rate-limit is keyed by the *matched* `api_key.id`, so it never runs for keys that don't match a row, and there is no per-IP throttle on the API-key path.
- **Impact:** Unlimited un-throttled online guessing and a DoS amplifier (each attempt is a DB lookup). The 32-byte keyspace makes guessing infeasible (hence High, not Critical), but the advertised control is absent — a false sense of security.
- **Fix:** Implement the documented per-key/per-IP failure counter + temporary lock (Redis `INCR` with TTL keyed on prefix and/or source IP), **or** remove the setting and the docstring claims so the posture is represented honestly.

### SEC-6 ◑ `verify_token` does not require `exp`; a token minted without `exp` never expires
- **Location:** `outlabs_auth/utils/jwt.py:153-160`; `authentication/strategy.py:94-100`; `services/service_token.py:150-155`.
- **Evidence:** Decode calls pass only `algorithms`/`audience`(+`verify_exp`). PyJWT's `verify_exp` only checks `exp` *if present* — it does not require it. None pass `options={"require": [...]}`.
- **Impact:** Defense-in-depth gap; real risk if any path (custom `additional_claims`, future code, or a forged token after secret compromise) omits `exp` — it can't be aged out. No `iat`/`nbf` requirement either.
- **Fix:** Add `options={"require": ["exp", "iat"], "verify_exp": True}` (and verify `aud`) across `verify_token`, both strategies, and `validate_service_token`.

### SEC-7 ◑ Login user-enumeration via timing (no dummy hash when the user is absent)
- **Location:** `outlabs_auth/services/auth.py:148-175`.
- **Evidence:** When the user is not found, the function raises immediately without hashing. Only the existing-user path runs the deliberately expensive Argon2 verify. The error string is identical, but response time differs by tens of ms.
- **Impact:** Remote account enumeration by timing despite the generic message — feeds credential-stuffing/phishing lists.
- **Fix:** When the user is missing, verify the supplied password against a fixed dummy Argon2 hash before raising, so both paths do equal work.

### SEC-8 ◑ Rejected passwords are reflected back in 422 validation responses
- **Location:** `outlabs_auth/fastapi.py:80-89` (`_handle_validation_error`); password fields in `schemas/auth.py` and `schemas/user.py`.
- **Evidence:** The handler returns `exc.errors()`, which in Pydantic v2 includes the offending `input` value. The reviewing agent confirmed empirically that a too-short `password` is echoed as `"input": "<cleartext>"` for `/auth/login`, `/auth/register`, `/auth/reset-password`, `/me/change-password`, etc. Installed by default via `instrument_fastapi(..., exception_handler_mode="global")`.
- **Impact:** The cleartext password lands in the response body and from there into devtools, client-side error logging/Sentry, and proxy/access logs. Near-miss reuse makes even rejected attempts sensitive.
- **Fix:** Scrub `input` (and input-bearing `ctx`) from each error before returning — e.g. `[{k: v for k, v in e.items() if k != "input"} for e in exc.errors()]`, or redact for fields named like `password`/`token`/`secret`/`code`.

---

## 🟡 Medium

### SEC-9 ◑ No minimum length / strength check on `secret_key`; one symmetric secret signs all token types
- **Location:** `outlabs_auth/core/auth.py:173-174` (non-empty check only); `core/config.py:39` (no validator); reuse at `core/auth.py:625-664`, `service_token.py:113`.
- **Evidence:** A 4-character HS256 secret is accepted. The same `secret_key` signs user access tokens, refresh tokens, and 365-day service tokens (separated only by `aud`/`type`).
- **Impact:** Weak secret → offline brute-force of the signing key → full token forgery (including service tokens with arbitrary embedded permissions). One leaked secret compromises every token class.
- **Fix:** Enforce ≥32-byte HS256 secrets via a validator; reject obvious placeholders; allow/recommend a distinct service-token signing key. Replace `"your-secret-key-here"` in the presets.

### SEC-10 ◑ OAuth: the ID-token `nonce` is generated but never validated; state is not session-bound
- **Location:** `outlabs_auth/oauth/security.py:19-28`, `oauth/provider.py:121-145`, `routers/oauth.py:126-220`, `routers/oauth_utils.py:22-33`.
- **Evidence:** The callback validates the signed state JWT (good for tamper/expiry) but `state_data` is empty, so state isn't bound to the initiating session; and the `nonce` placed in the auth request is never stored or compared against the returned `id_token`'s `nonce`.
- **Impact:** The OIDC replay control (nonce) is absent; weaker login-CSRF protection. (Apple id-token signature/iss/aud *is* verified, limiting forgery → Medium.)
- **Fix:** Persist the `nonce` (e.g. inside the signed state) and compare it to the `id_token` claim; bind state to the browser via an HttpOnly cookie value hashed into the state.

### SEC-11 ◑ Apple `parse_id_token` defaults to `verify=False` with an unsigned-decode fallback
- **Location:** `outlabs_auth/oauth/providers/apple.py:270-302`.
- **Evidence:** Signature default is `verify: bool = False`; the `else` branch does `jwt.decode(..., options={"verify_signature": False})`. The in-tree caller passes `verify=True` (safe), but any other caller using the default gets an attacker-controllable payload (`sub`/`email` used for account linking).
- **Impact:** If invoked with the default, an attacker-supplied id_token authenticates as any Apple `sub`/email → account takeover. A footgun even though the current path is safe.
- **Fix:** Default `verify=True`; gate the unsigned branch behind an explicit debug flag; never return identity from an unverified token.

### SEC-12 ⚠️ `python-multipart` floor `>=0.0.6` permits known DoS/ReDoS CVEs
- **Location:** `pyproject.toml` (`python-multipart>=0.0.6`, also `fastapi>=0.104.0`).
- **Evidence:** The lower bound allows 0.0.6–0.0.9, affected by CVE-2024-24762 (ReDoS in `Content-Type` parsing) and CVE-2024-53981 (malformed-multipart DoS). The *resolved* dev env has 0.0.20 (safe), but a fresh downstream install could pull a vulnerable version.
- **Impact:** A consumer could receive a vulnerable parser → unauthenticated DoS against form endpoints (e.g. form-based `/auth/login`).
- **Fix:** Raise floors (`python-multipart>=0.0.18`; consider `fastapi>=0.115`/explicit `starlette>=0.40`). **Open question:** applicability depends on the consumer's resolved versions — confirm exact safe versions against your advisory DB.

### SEC-13 ✅ Empty scope list grants all permissions (fail-open default)
- **Location:** `outlabs_auth/services/api_key.py:479-487` (`scopes_allow_permission`); same pattern in `services/service_token.py:177-205`.
- **Evidence:** `if not normalized: return True` — an empty/missing scope set passes every permission. For API keys the owner's own permission check still applies on the non-snapshot path; for service tokens and the snapshot fast-path the scope list may be the primary constraint.
- **Impact:** A key created with `scopes=[]` is as powerful as its owner; a service token without a `permissions` claim passes all checks. Easy to create an over-privileged credential by omission.
- **Fix:** Treat empty scopes as deny-all (fail-closed) and require explicit scopes — **or** prove and document that the empty-scope path always still runs the owner permission check (never authorizes via a scope-only snapshot). **Open question:** end-to-end exploitability of the snapshot path wasn't fully closed; confirm the snapshot can't authorize beyond the owner.

---

## ⚪ Low / Info

- **SEC-14 ◑** `decode_token_without_verification` / `get_token_expiration` / `is_token_expired` are exported and trust unverified claims (`utils/jwt.py:185-263`). No current auth decision uses them; risk is a future misuse. Prefix with `_` or move to an `unsafe` namespace.
- **SEC-15 ◑** Passwordless request endpoints can leak account existence (generation only runs for existing users), and the in-memory rate limiter (`utils/rate_limit.py:78`) is per-process — N× the intended limit across instances without Redis. Ensure identical responses regardless of account existence; require Redis-backed limiting for multi-instance.
- **SEC-16 ◑** `build_bootstrap_config(secret_key="outlabs-auth-bootstrap")` hardcodes a default secret (`bootstrap.py:184`). Low impact (CLI bootstrap only; core still rejects empty secrets), but dangerous if reused to serve live token-issuing traffic. Require it explicitly or generate ephemerally.
- **SEC-17 ◑** No `max_length` on password/free-text inputs (`schemas/auth.py`, `schemas/user.py`) → unbounded Argon2 work per request (CPU DoS). Add `max_length` (128–256).
- **SEC-18 ◑** `CookieTransport` ships no CSRF mechanism and doesn't set cookie flags (`authentication/transport.py:120-141`). Not wired by default (default auth is bearer in the body), so no library-shipped cookie is at risk — but document that opting into cookie auth requires host-side CSRF + `Secure`/`HttpOnly`/`SameSite`.
- **SEC-19 ◑** `AuthDeps._authenticate_request` swallows all backend exceptions with `except Exception: continue` (`dependencies/__init__.py:544-574`). Fail-closed for the decision, but masks backend bugs. Catch only expected auth exceptions; log the rest.
- **SEC-20 ◑** `QueryParamTransport` reads credentials from the URL (`authentication/transport.py:144-166`). Already carries a "not for production" warning and isn't default. Keep dev-gated.

---

## Verified safe (coverage — implemented correctly)

- **No `alg=none` / HS↔RS confusion** anywhere — every `jwt.decode` pins `algorithms=[self.algorithm]`; the token header is never trusted for algorithm selection.
- **Constant-time comparisons** where they matter: superuser token, access-code HMAC, PKCE, OAuth state (`secrets.compare_digest` / `hmac.compare_digest`).
- **Password hashing:** Argon2id via `pwdlib` with OWASP-2023 params (m≈19 MiB, t=2, p=1), bcrypt legacy-verify only, thread-offloaded, with legacy-hash upgrade on login.
- **Secrets hashed at rest:** refresh/reset/magic-link tokens and API keys are SHA-256 in the DB, never plaintext. SHA-256 for high-entropy 32-byte keys is the appropriate (fast, no-salt-needed) choice.
- **Access codes** use a nonce-prefixed HMAC keyed by `secret_key`, generated with `secrets.randbelow` — a DB leak alone can't brute-force the 6-digit code.
- **All security values use the `secrets` module** (no `random`); JWTs carry a `jti` for blacklisting.
- **Password-login lockout works** (failure counter + `locked_until`, honored on magic-link/access-code verify too).
- **Password-change invalidates old tokens** (compares token `iat` to `last_password_change`; reset revokes all refresh tokens).
- **Service-token vs user-token confusion is blocked by audience** (`outlabs-auth` vs `outlabs-auth:service` + `type=="service"`).
- **OAuth provider tokens encrypted at rest** (Fernet); config rejects enabling storage without a key. OAuth `state` is a signed JWT pinning HS256 with `exp`/`iat`/`aud` required.
- **ABAC has no code execution** — explicit operator dispatch, no `eval`/`exec`/`getattr` on attacker data; bad input fails closed.
- **Permission matching is fail-closed** — anonymous/null → `False`; `_tree`/`_all` propagation is correctly restricted; no sibling-subtree leak observed in closure queries.
- **Integration-principal & API-key scope confinement is enforced** via owner∩actor intersection (the pattern SEC-2/SEC-3 should adopt).
- **No request-reachable SQL injection** — `order_by` uses column objects, search uses parameterized `.ilike`; the only `text()` f-strings are operator-supplied schema names in `cli.py`/`migrations`.
- **Mass assignment prevented** — `create_user` uses explicit typed params; privilege fields (`is_superuser`, status) are gated behind superuser checks; update schemas carry no privilege fields.
- **Response schemas don't leak secrets** — no `hashed_password`; API-key hash never exposed; full key returned only once on create/rotate.
- **No insecure shipped defaults** — empty `secret_key` rejected, `debug=False`, no library-injected `CORS *`, no `python-jose`.
- **Sensitive data not logged** — observability captures ids/jti/prefix/email/error-class only; no bodies, headers, passwords, or tokens.

---

## Prioritized remediation plan

**P0 — close the escalation chain (one shared fix):** Implement **delegation containment** and reuse the existing `api_key_policy.calculate_grantable_scopes` pattern across (a) `assign_role_to_user` [SEC-2], (b) `add_permissions_by_name`/`set_permissions_by_name`/`update_role` [SEC-3], and (c) the user-targeting helper for tenant scope [SEC-4]. Add the `type == "access"` check to `JWTStrategy.authenticate` [SEC-1].

**P1 — token & enumeration hardening:** `require: [exp, iat]` on all decodes [SEC-6]; dummy-hash on missing-user login [SEC-7]; scrub `input` from 422 responses [SEC-8]; implement or remove the API-key lockout claim [SEC-5].

**P2 — config & OAuth:** enforce min `secret_key` length + distinct service key [SEC-9]; validate OAuth nonce + bind state [SEC-10]; default Apple `verify=True` [SEC-11]; raise `python-multipart` floor [SEC-12]; make empty scopes fail-closed [SEC-13].

**P3 — hygiene:** SEC-14 … SEC-20 as capacity allows.
