# Multi-Frontend Support — Seam Audit and Design

**Date**: 2026-07-29 (r2 — revised after an independent second audit and maintainer review; r1 same day)
**Status**: Companion to DD-059 (Accepted; shipped in 0.1.0a25). Audit + design, with implementation notes in section 10.1.
**Scope**: Every place the library decides or delegates "where does this user land" — transactional mail, OAuth redirects, magic links, invites, access codes — audited against four production consumer deployments plus their frontends.
**Note on evidence**: This public document keeps the audit's findings and design in consumer-agnostic form. The named per-host evidence (repos, commits, file:line citations) is maintained privately by the maintainer and is not part of the library contract.

## 1. The problem

One FastAPI host mounts outlabsAuth once, but serves users of more than one frontend. A password-reset email, an invite link, a magic link, or an OAuth success redirect must land on the frontend the recipient's account actually belongs to. The library has no concept that ties these flows together: the destination seams bind at incompatible times with incompatible context — mail URLs freeze per process at composer construction, OAuth landing URLs freeze per router mount, and the challenge seam accepts an arbitrary per-request `redirect_url` from any caller. "Which frontend?" is re-discovered independently, and differently, at every seam.

This is not hypothetical — it was live in two audited production stacks and latent in a third:

- One host shipped a subclass of the composed mail service that resolves the recipient's audience per send with fresh DB queries — re-buying root-entity data the library had in hand when it built the intent — and still ships wrong per-audience paths.
- A second host *lost* the per-audience mail routing its pre-library stack had: its portal base-URL setting is configured but unread, so portal invites land on the admin console, whose own guard then rejects those users. Adopting the library caused a regression.
- A third host serves three SPA origins and opted out of the composer entirely, hand-rolling per-flow URLs from separate origin settings — the shape a host takes when the library seam cannot express its routing.

### 1.1 Scope: what multi-frontend means here — and what it does not

The intended model, stated as a first-class commitment rather than an emergent property:

- **One outlabsAuth deployment serves one platform**: one user pool, one entity universe, one credential domain — with **N first-party frontends** as a named, registered concept. Multi-frontend is the default documented integration shape; a single-frontend host is the one-profile degenerate case, not the other way around.
- **Running several unrelated SaaS products off one deployment is explicitly out of scope.** Frontend profiles are a routing, branding, and **authentication-policy** surface: they decide where links land, how mail is branded, and which users may authenticate through which app. They do not create separate credential domains.
- **Three honest levels of separation** (adopted from the second audit; a host must know which level it is buying):
  1. **Routing/UX** — profile selection for links, branding, landings, and frontend guards. No credential isolation.
  2. **Shared-platform policy** — an `azp`/app claim bound to sessions plus server-side checks: sign-in gating at every token-minting path, and enforced app checks on endpoint families declared app-scoped. Still one issuer, one key, one user realm; RBAC and root-entity isolation (DD-056) remain the data boundary.
  3. **Credential-domain isolation** — distinct issuer/keys/user namespace/OAuth trust. Only separate deployments (or a deliberate identity-provider architecture with confidential clients/BFFs) provide this.
- **Partitioned and shared frontends are both first-class — multi-frontend works both ways.** Each profile declares the audiences it serves. An exclusive frontend (an internal admin console) rejects off-audience authentication server-side; a shared set of frontends accepts overlapping audiences and behaves like SSO within the platform. Both modes are configuration.
- **A hosted customer-facing product sharing a mount with an internal console requires an explicit platform classification.** The audited Q-004 case was resolved on 2026-08-04: the host accepts one credential domain and classifies the customer frontend as part of the same platform, while placing its users in a disjoint top-level entity tree. Internal operators remain in their own root and cross the tree only through explicit system-wide/cross-root authority on console-scoped sessions. That is a deliberate level-2 design; a separate deployment remains the answer if independent identity, keys, issuer, admin plane, or incident radius becomes required.

## 2. Seam inventory — where "where does this user land" is decided

| # | Flow | Seam | Landing decision | Context available at the decision point | State |
|---|---|---|---|---|---|
| 1 | Invite | `transactional_mail_service` → composer | `invite_url_builder(token)` — fixed at construction | Builder: token only. Intent: recipient, token, expiry, metadata | Host-owned, frozen per process |
| 2 | Forgot password | same | `password_reset_url_builder(token)` — fixed | same | Host-owned, frozen per process |
| 3 | Reset confirmation | same | no URL (notice only) | — | n/a (branding still fixed) |
| 4 | Access granted | same | `login_url_builder()` — fixed, not even a token | — | Host-owned, frozen per process; **no library production call site exists** — host-only today |
| 5 | Magic link | `transactional_messaging_service` (`AuthChallengeDeliveryIntent`) | Host composes the email; intent carries client-supplied `redirect_url` | recipient, secret, expiry, `redirect_url`, `request_base_url` | Host-owned, **per-request** |
| 6 | Access code / OTP | same | same (code, not link; `redirect_url` still present) | same | Host-owned, per-request |
| 7 | Phone verify | same | n/a (code) | same | Host-owned |
| 8 | Email verify | `on_after_request_verify` hook only | no intent, no composer, no request/confirm router | hook args | Host-owned, no library support at all |
| 9 | OAuth login | `get_oauth_router(...)` | `success_redirect_url` / `error_redirect_url` — constructor params | none at runtime | Host-owned, frozen **per router mount** |
| 10 | OAuth associate | `oauth_associate.py`, same construction shape | fixed success URL | — | same defects as login OAuth (route name, cookie, fixed landing) |

Key structural facts behind the table:

- **The composer interface is already context-rich; the default composer's builders are not.** `AuthMailComposer.compose_*` receives full intents (`mail/types.py`), and host workarounds prove per-recipient routing is possible at that layer. The bottleneck is narrower than "the mail seam": it is (a) `TokenUrlBuilder = Callable[[str], str]` (`mail/composer.py:18`) receiving only the token, and (b) `ComposedAuthMailService` holding exactly one composer for all four send methods (`mail/service.py:17-42`).
- **The intents omit the audience data the library was holding when it built them.** `_build_mail_recipient` (`services/user.py:1608`) copies user id/email/names/phone and drops `user.root_entity_id` — which is sitting on the same ORM row. On the invite path the ordering is decisive: `invite_user` adds the entity membership (which pins `root_entity_id`) *before* firing `on_after_invite` (`routers/auth.py:740` vs `:759`). Host workarounds' per-send DB lookups re-buy information the library discarded.
- **`request_base_url` is a half-measure.** Every intent carries it, but it is the API origin (`str(request.base_url)`, `services/user.py:1630`), not a frontend origin — and the bundled routers only thread `request` on the magic-link/access-code paths; `forgot_password` and `invite_user` fire their hooks without it (`routers/auth.py:361`, `:759`), so it is `None` exactly where reset links get built.
- **Advertised invite metadata has no producer.** `DefaultAuthMailComposer.compose_invite` reads `target_entity_name`, `inviter_email`, `role_names` from `intent.metadata`; no library call site populates any of them (repo-wide grep). Every default invite email says "your organization" unless the host overrides the hook.

## 3. Inconsistencies between the seams

The seams answer the same question three different ways, and the differences are where the bugs live:

1. **Three routing models coexist.** OAuth: frozen per router mount. Composer mail: frozen per process. Challenges: routed per request by a client-supplied `redirect_url`. A host wanting coherent multi-frontend behavior must solve the problem three times in three shapes.
2. **The challenge seam's `redirect_url` is an unvalidated pass-through that is stored but never enforced or returned.** `MagicLinkRequest.redirect_url` / `AccessCodeRequest.redirect_url` (`schemas/auth.py:90,119`) accept any string up to 2048 chars from any unauthenticated caller; the value is persisted on the challenge row and handed to the host's delivery hook — and at verification the API returns only `LoginResponse` tokens, never the stored redirect (`routers/auth.py:473-509,616-676`). So the frontend navigates from a *second copy* of the value in its own URL query — two copies, neither canonical, no library allowlist. A host that embeds the stored value in email can be induced to send a victim a legitimate product email whose link points at an attacker origin.
3. **No token-placement contract.** Audited frontends split evenly between `?token=` query placement and path-segment placement (`/recovery/:token`). The library docs and examples never state a contract, and hosts have shipped two dead-link defect classes over exactly this — including one where every reset link a host ever generated pointed at a route that did not exist, unnoticed because no environment had a mail provider configured.
4. **Request threading is inconsistent per flow** (see `request_base_url` above).
5. **Email verify has no delivery seam at all** — hooks exist as no-ops, with no request/confirm router or mail intent — while one audited frontend ships a `/verify-email/:token` route with no library flow behind it.
6. **`get_oauth_router` is not exported** from `outlabs_auth.routers` (`routers/__init__.py`); consumers must import the private-looking module path, and no audited production host uses it (examples/tests only).
7. **Hooks are a parallel, probe-able extension surface.** Hosts can monkey-patch `user_service.on_after_*` (a documented pattern) — but a host endpoint can also probe the *wrong object* for a hook and silently no-op. That is not theoretical: one audited host's customer-facing forgot-password facade probed a nonexistent `auth.hooks` attribute, so its reset mail was never sent in production. There is no single canonical "invoke the delivery pipeline" entry point a custom endpoint can be pointed at.

## 4. OAuth: is mounting the router twice actually supported?

Construction-time `success_redirect_url`/`error_redirect_url` means multi-frontend OAuth implies either one mount per frontend or per-flow routing that does not exist today. Verdict from reading `routers/oauth.py`, `routers/oauth_associate.py`, and the test suite — corroborated by the second audit's in-process probe: **same-provider double-mounting is structurally broken today, and nothing tests it.**

- `callback_route_name = f"oauth:{oauth_client.name}.callback"` (`routers/oauth.py:152`) depends only on the provider name, not the prefix. Two mounts of the same provider register two routes with the same name; Starlette's `url_for` returns the first match, so mount B's `/authorize` builds its provider redirect against mount A's callback path and the user completes the flow through mount A's `success_redirect_url` — a silent cross-frontend misroute. (OpenAPI operation ids do **not** collide — the prefixed paths make them distinct; route reversal is the real defect.)
- The one-time state cookie is provider+flow scoped, not mount or profile scoped (`oauth_state_cookie_name`, `routers/oauth_state_store.py:18-22`): two concurrent flows for the same provider from two frontends in one browser clobber each other's binding cookie, and the login state payload carries no frontend identity at all (`routers/oauth.py:182-190`).
- `oauth_associate.py` has the same shape throughout: provider-only route name, fixed success URL, provider+flow cookie. Any repair must cover association, not just login.
- Mitigating context: no audited production consumer mounts OAuth today, so this is a forward-looking defect, not a live incident — which is exactly why the model should be corrected before social sign-in ships on any frontend.

**Long-term model (r2, adopted from the second audit)**: not one-router-per-frontend. One provider callback per host/provider; `/authorize` accepts a registered profile id; the signed *and persisted* state binds `profile_id` + a unique flow nonce; the browser cookie binding supports concurrent flows; the callback consumes state and resolves success/error destinations from the bound profile.

## 5. Host evidence

The named per-host audit evidence (four production consumers, two frontends, with repo/commit/file:line citations) is maintained privately. The patterns it established, in consumer-agnostic form, are what sections 1, 3, and 6 state: one host built an audience-routing mail subclass with per-send DB queries and a fail-open default; one host regressed portal routing on adoption because the library could only hold one composer; one host bypassed the composer for three origins and routes by flow, not by any user attribute; and one greenfield adopter plans a shared-root hierarchy where root identity cannot distinguish user classes at all. Two shipped dead-link defect classes and one silently dead production reset-mail path came out of the same audits.

## 6. Is root entity the natural audience key?

`MembershipService.add_member` pins `user.root_entity_id` on first membership and refuses cross-tree membership (`services/membership.py:173-187`), which makes the root a durable, one-indexed-read input. But the observed audience keys across the four audited hosts were: root entity **slug** (two static roots, disjoint user sets); canonical internal slug **plus explicit external root types**, with null/fallback/unknown roots needing an unresolved outcome (N dynamic roots per audience); **flow / user class** (same population, three frontends, SimpleRBAC — no roots at all); and **role / membership scope** (several user classes under one shared root, planned).

Conclusion: root entity is a *good default input* — but it is not *the* key, and "which app initiated this request" is request context no user attribute can carry. Baking `audience := root_entity` into the library would misroute two of four hosts and leave two more unroutable. The design must therefore (a) put root-entity context — id, slug, and type — onto the intents, (b) leave the mapping from context to profile in a host-supplied resolver that may also use roles, memberships, and the requested profile, and (c) accept "unresolved" as a first-class outcome.

## 7. Options

### Option A — pass context to the URL builders

Extend `TokenUrlBuilder` to receive the intent (or a context object) alongside the token; everything else stays host-owned.

- Blast radius: the builder callables' signature. Existing single-frontend builders break, or the library grows arity-sniffing (alpha status favors a clean break over arity magic).
- What it fixes: a host can vary the *URL* per recipient.
- What it does not fix: `app_name`, subjects, support address stay frozen per composer; every host still writes imperative routing; no allowlist appears for `redirect_url`; the challenge and OAuth seams are untouched; the shared-paths defect class remains.
- Verdict: the right *information flow* at the wrong layer. Routing above the composer achieves strictly more with no signature break. Subsumed by option B.

### Option B — frontend profiles + host-supplied resolver (recommended)

The library gains a declarative, flow-wide `FrontendProfile` registry and a resolution component that every destination-bearing flow consults, with a host-supplied resolver over typed context. Detail in section 8.

- Blast radius: additive for the library API (single-composer construction keeps working; intents gain optional fields), but adoption is honestly more than additive — challenge storage gains `profile_id` + canonical-target columns, session/token records gain an `azp` field (Alembic migrations), OAuth state changes shape, and hosts with custom mail services rewire onto the selector.
- Fixes: per-audience URLs *and* branding *and* route templates; deletes the workaround subclass pattern and its per-send queries; gives `redirect_url` a registered-destination model; one concept spans mail, challenges, OAuth, and session provenance.
- Costs: one more configuration surface; the resolver is host code that can be wrong (pure/testable, but real); schema migrations; per-frontend route-contract tests to keep declared templates honest.
- Fit: expresses all four observed hosts and stays config-level, per DD-025's philosophy.

### Option C — first-class application/client registry (OAuth-provider style)

An `application` SQL model: client ids, per-client redirect allowlists, per-client token policy, dynamic administration.

- Costs: migrations for every consumer, admin CRUD + UI surface, a writable high-value control plane (redirect URIs in the database), availability coupling of every login to the registry, and a second identity axis overlapping the entity tree.
- What it buys over B: dynamic registration, third-party clients, consent, client credentials.
- Verdict: do not build now. Keep profile ids stable and non-secret so a future persisted registry can coexist. Revisit triggers: third-party client apps, per-client token trust domains, runtime-provisioned frontends.

### Option D — do nothing; document the host-side pattern

Rejected on the evidence: three hosts diverged three ways, two dead-link defect classes shipped, one host regressed behavior it had before adopting the library, one customer-facing reset flow silently sends nothing today, and email is the least-observable channel in the stack. Documenting the pattern would spread its per-send DB queries and exception policy as gospel.

### Option E — separate deployments (the boundary option)

Not a competing feature — the required guidance for genuinely distinct products: independent user namespace, keys, issuer, OAuth trust, admin plane, and incident radius. Costs operational duplication. This is the standing answer wherever level-3 separation (section 1.1) is actually required; Q-004 explicitly accepted level 2 for its same-platform hosted frontend.

## 8. Recommended design (detail for DD-059, r2)

Four contract layers, shipped as vertical slices per flow with their schema migrations called out — not "purely additive" sprinkling.

### 8.1 The profile registry — flow-wide, immutable, declared at construction

```python
FrontendProfile(
    key="member-portal",                       # stable, unique, non-secret
    app_name="ACME Member Portal",             # branding for subjects/bodies
    public_origins=("https://portal.acme.example",),
    routes=FrontendRoutes(                     # typed per flow; token placement explicit;
        login="/login",                        # None = flow unsupported by this frontend
        password_reset="/recovery/{token}",
        accept_invite=None,                    # portal has no invite page today
        magic_link="/auth/magic-link?token={token}",
        oauth_callback=None,
    ),
    redirect_policy=RedirectPolicy(...),       # relative paths and/or origins allowlist
    support_email="support@acme.example",
)
```

Invariants: profiles are immutable after startup; a profile — not the resolver, not the caller — owns URL construction and branding; selecting a profile for a flow whose route is `None` is a validation failure at wiring time or a fail-closed delivery error at send time, never a guessed link. Both token placements (`?token={token}`, `/recovery/{token}`) are first-class, closing the shipped dead-link defect class.

### 8.2 Resolution — one component, every flow, resolved once

- The host supplies a resolver over a typed `FrontendResolutionContext`: flow kind; recipient identity; `root_entity_id/slug/type` when present; actor and target entity for invites; the **requested profile key** for frontend-originated operations (`app`, a registered key — never a URL); request origin as evidence, not authority. The resolver may be **async** and may query host data (preferably inside the caller's existing session/UoW), but returns only a registered key.
- Resolution happens **once per operation**; the resolved `profile_id` is then persisted through everything downstream: mail/messaging intents, the challenge row, OAuth state, session records, audit events. Downstream code consumes the resolved profile; it never re-resolves.
- The selector is a standalone component consumed by `ComposedAuthMailService` — and equally callable by host-custom mail services and host facade endpoints. There is one canonical, documented pipeline entry point for custom endpoints, so nothing probes for hooks on the wrong object again (section 3, item 7).
- Library convenience resolvers cover the observed cases declaratively (`route_by_root_entity_slug`, `route_by_root_entity_type` composed with slug overrides and an explicit-unresolved default posture); a real production predicate (canonical internal slug + explicit external types + unresolved fallback + an explicit home profile for privileged accounts) is expressible in one small host function.

### 8.3 Failure policy — fail closed (r2 reversal)

r1 proposed resolver-failure → default profile, logged. The second audit is right that this standardizes wrong-brand links minted during outages, and the repo's own precedent (`token_blacklist_failure_mode`, `api_key_rate_limit_failure_mode`) is fail-closed defaults. r2:

- Unknown profile, unsupported flow, resolver exception, or user/profile mismatch → **fail closed internally**: no message is sent, a structured delivery-failure result and audit/metric record is emitted. Enumeration-resistant endpoints keep their opaque 204/202 outward response.
- A declared default profile is valid only for genuinely unambiguous contexts (the single-frontend host; a no-root SimpleRBAC population by explicit declaration) — never as an exception fallback.
- Post-change security confirmations may fall back to a separately declared **neutral, link-free** notice so the security signal still reaches the user without navigation.

### 8.4 Challenges and redirects — registered destinations, canonical `next_url`

- Magic-link/access-code requests name a registered `app` and a return target that is a relative path or normalizes into the resolved profile's allowlist. The library validates at request time, persists `profile_id` + the canonical target on the challenge row (schema migration), and delivery receives the resolved profile.
- **Verification returns the canonical `next_url`** (alongside tokens), so the frontend stops making a security decision from an untrusted copy of the redirect in its own URL query. The raw stored-but-never-returned `redirect_url` of today is retired after a compatibility window.

### 8.5 OAuth — profile-bound state, single callback per provider

As section 4: one provider callback per host/provider; `/authorize` takes a registered profile key; signed + persisted state carries `profile_id` and a unique nonce; cookie binding supports concurrent flows; the callback consumes state, then resolves that profile's registered success/error destinations. Applied to **login and association both**. Route-name prefix-awareness and exporting `get_oauth_router` land as hygiene. Tests must cover concurrent same-provider flows.

### 8.6 Sessions and tokens — `azp` provenance, honest semantics

- Every minted session/token records the resolved profile key as an **`azp`-style claim** (authorized party), bound to the refresh/session row (schema migration) and re-validated at rotation. `aud` stays the platform/resource audience — the frontend is the authorized party, not the audience; per-profile `aud` is explicitly rejected as the default model.
- **Sign-in gating**: each profile's `accepted_audiences` (host classification via the same resolver inputs) is enforced at every minting path — password login, magic-link verify, access-code verify, OAuth callback, invite-accept auto-login, refresh — rejecting with a stable `wrong_application` code. Default (no list) accepts everyone: the shared/SSO mode. Partitioned and shared frontends are both plain configuration.
- **What this is, honestly**: level-2 separation (section 1.1). Given correct RBAC + DD-056, a cross-audience session was never a data breach — the gate is defense in depth (an authorization bug on a console endpoint stops being reachable by the external population), consistency (per-frontend JS guards stop being load-bearing and stop drifting), and signal (server-side rejections are visible; client-side ones are not). A public SPA cannot authenticate its `app` selector, so an external user can still obtain a *portal* token and replay it at the shared API — which yields exactly their own privileges. Where an endpoint family must never serve another app's sessions, the host must declare it app-scoped and the `azp` check there is **enforced, not advisory**. Anything stronger is level 3: separate deployments or a confidential-client/BFF architecture.

### 8.7 CORS and browser posture

Profiles expose the union of registered origins to the host with a startup validation helper; the library does not mutate host middleware. Documented invariants: redirect allowlists and CORS lists are separate controls that should agree; CORS is not a bearer-token boundary; `Origin` is evidence, never an authorization credential.

### Testing obligations

Unit: profile → URL rendering for both token placements and `None`-route rejection; resolver outcomes (requested-key valid / unknown / identity-derived / no-root / exception → fail closed); single-composer construction byte-identical behavior. Integration: end-to-end forgot-password producing per-audience links from one mount; fail-closed delivery on unresolved audiences with opaque outward responses; challenge `next_url` round-trip; audience gating across every minting path in partitioned and shared configurations (`wrong_application` contract); OAuth concurrent same-provider flows for two profiles, login and association. Cross-repo: route-contract fixtures per frontend per flow (declared template ↔ actual route) — the `outlabs_auth.frontend.contract` helpers exist so each consumer runs these against its own frontend checkouts, in its own private test suite. Example: the enterprise example becomes two-profile so the documented recipe is the multi-frontend one.

## 9. Long-term direction — the maturity ladder

Where this sits in the library's trajectory as a general-purpose auth foundation (maintainer-reviewed framing):

1. **Anonymous frontends** (today): the user is the only subject. Remains fully supported — the smallest three-router integration must stay this small.
2. **Named frontends** (profiles, layers 8.1–8.4): declared configuration for routing, branding, landing correctness.
3. **Frontends as policy subjects** (layers 8.5–8.6): sign-in gating and `azp` provenance — as far as enforcement can go for public browser clients, which is acceptable because identity + entitlements (RBAC/ABAC/entities) remain the library's center of gravity and the real boundary.
4. **Frontends as principals** (the deferred registry): client ids/secrets, confidential clients, per-client trust — only rung where "which app is calling" becomes cryptographically true, and only for clients that can hold secrets (the audited fleet already contains one first-party BFF). Climbed when a consumer demonstrates the need, not before.

Standing posture: every rung is opt-in; single-frontend hosts pay nothing; and outlabsAuth does not become a third-party identity provider — that is a different product with a different threat model, and it would fight the library-first, host-owned philosophy (DD-025) that makes this adoptable.

## 10. Explicit non-goals of this pass

- **No multi-product tenancy.** One deployment = one platform = one user pool (section 1.1). Distinct SaaS products get distinct deployments. Audience gating partitions *sign-in within one platform*; it is not a substitute for separate deployments between products.
- No `application` SQL model, no client ids or secrets, no third-party or dynamically-registered clients (option C triggers in section 7). The *audience/provenance* slice of option C — `accepted_audiences` at authentication plus the `azp` claim — is deliberately pulled forward; the registry machinery is not.
- No per-profile JWT `aud`; `aud` remains the resource audience (section 8.6).
- No library-owned email templates beyond the existing default composer, and no provider changes (DD-025 stands).
- No change to hook signatures — but a canonical pipeline entry point is added so custom endpoints stop depending on hook-probing.

## 10.1 Implementation notes — Slice 1 (2026-07-29)

Slice 1 (profiles, resolution, mail) is implemented on `feat/dd-059-multi-frontend`: the `outlabs_auth.frontend` package (`FrontendProfile`/`FrontendRoutes`/`RedirectPolicy`, `FrontendProfileRegistry`, `FrontendProfileResolver` + `route_by_root_entity_slug`/`route_by_root_entity_type`), intent enrichment, invite-metadata population, `DefaultAuthMailComposer.from_profile`, and the dual-form `ComposedAuthMailService` with fail-closed `_select_composer`. Deviations and conscious simplifications to carry forward:

- **`profile_id` on mail intents currently carries the *requested* key** (the Phase-3 `app` hint, once routers thread it), not the resolved profile — intents are frozen and resolution happens in the mail service after intent construction. The resolved key is persisted downstream from Slice 2 onward (challenge rows, sessions, audit); if this dual meaning proves confusing, rename the intent field to `requested_profile_key` before beta.
- **Reset-confirmation fallback uses the declared default profile's composer** (link-free by construction, but default-branded) rather than a separately declared neutral notice profile. Acceptable v1; revisit if wrong-brand confirmations matter in practice.
- **Enrichment cold-loads open sessions from an internal factory** (`UserService._session_factory`, wired by `OutlabsAuth` service construction) guarded by the request-scoped cache — hook signatures are frozen and receive no session, so the caller's UoW is not reachable from the send sites. Cost is at most one root-entity load per request per root. Hosts constructing `UserService` directly get `None` and enrichment degrades to `root_entity_id`-only.
- `request_origin` on the resolution context is fed from `request_base_url` (the API origin, and `None` on the bundled forgot/invite paths) — evidence only, as specified.

### Slice 2 notes (2026-07-29)

Slice 2 (challenges + canonical `next_url`) is implemented: `app` on the forgot-password/magic-link/access-code request schemas; request-time resolution in the bundled routers via `frontend.flows.prepare_challenge_dispatch` (fail closed on unknown apps, mismatches, disallowed return targets, and magic-link profiles with no landing route — access codes tolerate a missing route since codes are typed, not followed); migration `20260729_0021` adds `profile_id` + `next_url` to `auth_challenges`; verification returns the canonical `next_url` on `LoginResponse`. Mechanism notes:

- **Request-scoped carriers, not hook changes**: values that travel router → send site (requested/resolved profile, canonical target) or verify → response (`next_url`) ride consume-once entries in the request cache, keeping hook signatures and `verify_*` return shapes frozen. `frontend.consume_verified_challenge()` is public so host facades calling `verify_magic_link`/`verify_access_code` directly can read the canonical `next_url` the same way the bundled routers do.
- `OutlabsAuth` accepts `frontend_resolver=`, and adopts the mail service's resolver when not given — routers and mail routing share one registry by default.
- The raw `redirect_url` remains accepted for the compat window: unvalidated passthrough on hosts without profiles; on hosts with profiles it must normalize into the resolved profile's policy or the request fails closed, and hook overriders now receive the canonical target instead of the raw value.

### Slice 3 notes (2026-07-29)

Slice 3 (profile-bound OAuth state) is implemented: `/authorize` on both the login and association routers accepts `app` (a registered profile key, validated up front — unknown keys, absent registry, or profiles with no declared landing route for the flow are loud 400s, since authorize is developer-facing and not enumeration-sensitive). The key rides in the **signed** state token and is **persisted** on the `oauth_states` row (migration `20260729_0022`); consume cross-checks the persisted value so a signed state cannot be replayed under a different profile. The binding cookie name gains a per-profile segment, so concurrent same-provider flows from two frontends coexist. Callbacks upgrade success/error targets to the bound profile's declared routes immediately after the state signature verifies (an untrusted/undecodable state only ever lands on the construction-time error URL), with construction-time URLs remaining the single-profile/legacy path. Callback route names are prefix-aware (`oauth:github:v1.oauth.github.callback`) so duplicate same-provider mounts stop colliding in `url_for` — historical names are preserved for empty prefixes. `get_oauth_router` and `get_oauth_associate_router` are exported from `outlabs_auth.routers`. Phase-4 note: the OAuth callback is a minting path; its `accepted_audiences` gate lands in Slice 4 with the others.

### Slice 4 notes (2026-07-29)

Slice 4 (azp provenance + audience-gated sign-in) is implemented. Sessions carry the bound profile key as an `azp` claim in both tokens and on the refresh-token row (migration `20260729_0023`), preserved and **re-gated** at rotation. `enforce_sign_in_gate` is the one gate every minting path consults — password login and refresh inline, and magic-link verify, access-code verify, OAuth callback, and invite-accept auto-login via `create_tokens_for_user` (which now gates internally, so future minting paths that use it are covered by construction; its docstring carries the standing-obligation marker). Semantics: no resolver / no bound app → legacy app-less session; empty `accepted_audiences` → shared/SSO mode, no resolver call; partitioned profiles run the resolver with the requested key and the resolved audience (explicit `FrontendResolution.audience`, else the resolved profile key) must be accepted. Rejections are `WrongApplicationError` → stable 403 with code `wrong_application` (under `register_exception_handlers` the code surfaces at `details.code`); the OAuth callback maps it onto the profile-bound error redirect. `require_app(auth, "console")` enforces app-scoped endpoint families from the already-verified auth context's `azp`, avoiding a second Bearer-token decode. Implementation-forced fix: the request cache stores root-entity slug/type as plain values — caching live ORM instances raised `DetachedInstanceError` once the loading session closed. The two-profile `examples/enterprise_rbac` recipe and the `CURRENT_IMPLEMENTATION_STATUS.md` reconciliation completed the definition of done on 2026-08-04.

## 11. Reconciliation record (r2)

An independent second audit (maintained privately) re-derived the ground and critiqued r1. Both audits converge on the core diagnosis and the profiles + host-resolver direction. r2 adopted from it: the flow-wide `FrontendProfile` (was mail-first); resolution as a standalone async-capable component resolved once and persisted; the **fail-closed** failure policy (r1's default-fallback endorsement reversed); registered-destination redirects with verification-time canonical `next_url`; OAuth single-callback profile-bound state including association and concurrency tests; the `azp` claim with `aud` kept as resource audience; the honest three-level separation framing; and the requirement that the Q-004 platform boundary be decided explicitly. Q-004 was resolved on 2026-08-04 in favor of a shared credential domain plus disjoint top-level entity roots and explicit cross-root operator authority. The audit's single most valuable find: a production host's customer-facing reset-mail path was silently dead because a facade endpoint probed a hook surface that does not exist — the concrete case for the canonical pipeline entry point and fail-closed delivery. One of its claims did not survive re-verification (a host flow it reported absent exists at that host's `origin/main`); its adjacent point — that host validates the *need* for per-flow profiles rather than the mail design — stands and is incorporated in section 6. Maintainer review contributed the security classification in 8.6, the maturity ladder in section 9, and the requirement that partitioned and shared frontends both be first-class.
