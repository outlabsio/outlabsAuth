# Multi-Frontend Support — Seam Audit and Design

**Date**: 2026-07-29 (r2 — revised after the independent second audit and maintainer review; r1 same day)
**Status**: Companion to DD-059 (Proposed, r2). Audit + design only — no implementation in this pass.
**Scope**: Every place the library decides or delegates "where does this user land" — transactional mail, OAuth redirects, magic links, invites, access codes — audited against the four production consumers, plus the design options and the recommended contract.
**Reconciliation**: An independent second audit ([`MULTI_FRONTEND_SECOND_AUDIT.md`](./MULTI_FRONTEND_SECOND_AUDIT.md)) re-derived this ground and critiqued r1. Section 11 records what was accepted, what was rejected with evidence, and what changed. Its largest single contribution: the Referral Collection password-reset mail path is dead in production today (section 5.1).

## Sources audited

| Codebase | Ref | Role |
|---|---|---|
| outlabsAuth (this repo) | `main` @ a979661, 0.1.0a24 | The library |
| diverse-data-api | `origin/main` @ d09eb10 | One mount, two frontends (OutlabsAuthUI console at auth-data.meetdiverse.com + Referral Collection at staging.referralcollection.com). Carries the host workaround this design absorbs. |
| DiverseAPI-postgres | `postgres` @ e6d652f6, pins 0.1.0a23 | One mount, two frontends (DiverseAdminPanel console + agentPanel portal, both on their `postgres` branches) |
| qdarte-intake | `main` (verified against `origin/main`) | One mount, three frontend origins (subir/socios/admin.qdarte.com); bypasses the composer entirely |
| qdarteAPI | `main`, resolves 0.1.0a24 | Baseline: no auth mail, no OAuth |
| OutlabsAuthUI | `main` | The shared console: one build, many backends via deploy-time `app-config.json` |
| creditos-del-norte-api | `main` | EnterpriseRBAC franchise multi-tenant; no mail wiring yet — likely next N-audience consumer |

## 1. The problem

One FastAPI host mounts outlabsAuth once, but serves users of more than one frontend. A password-reset email, an invite link, a magic link, or an OAuth success redirect must land on the frontend the recipient's account actually belongs to. The library has no concept that ties these flows together: the destination seams bind at incompatible times with incompatible context — mail URLs freeze per process at composer construction, OAuth landing URLs freeze per router mount, and the challenge seam accepts an arbitrary per-request `redirect_url` from any caller. "Which frontend?" is re-discovered independently, and differently, at every seam.

This is not hypothetical — it is live in two stacks and latent in a third:

- **diverse-data-api** shipped `AudienceRoutingAuthMailService` (d09eb10, 2026-07-29) to stop Referral Collection customers from receiving reset links into the Diverse admin console — and the customer-facing RC reset flow still sends no mail at all (section 5.1).
- **DiverseAPI-postgres** lost multi-frontend mail in the outlabsAuth cutover: the legacy Mongo branch routed by audience (`main` `src/api/routes/users.py:603-607`: `AGENT_PORTAL_URL if user.is_agent else FRONTEND_URL`), but the `postgres` branch builds one composer from `OUTLABS_AUTH_UI_URL or FRONTEND_URL` (`src/services/auth/transactional_mail.py:58-62`). `AGENT_PORTAL_URL` still exists in config (`src/core/config.py:143`) and in the README's documented intent, but nothing reads it. Net effect today: an agent's invite email lands on the admin console, they set a password there, and the console's own guard rejects their `agent_practice` root with `LOGIN_WRONG_PORTAL`. Adopting the library caused a regression.
- **qdarte-intake** serves three SPA origins and opted out of the composer entirely, hand-rolling per-flow URLs from separate origin settings (`socios_base_url`, `magic_link_email_base_url`, `public_base_url`) — the shape a host takes when the library seam cannot express its routing.

### 1.1 Scope: what multi-frontend means here — and what it does not

The intended model, stated as a first-class commitment rather than an emergent property:

- **One outlabsAuth deployment serves one platform**: one user pool, one entity universe, one credential domain — with **N first-party frontends** as a named, registered concept. Multi-frontend is the default documented integration shape; a single-frontend host is the one-profile degenerate case, not the other way around.
- **Running several unrelated SaaS products off one deployment is explicitly out of scope.** Frontend profiles are a routing, branding, and **authentication-policy** surface: they decide where links land, how mail is branded, and which users may authenticate through which app. They do not create separate credential domains.
- **Three honest levels of separation** (adopted from the second audit; a host must know which level it is buying):
  1. **Routing/UX** — profile selection for links, branding, landings, and frontend guards. No credential isolation.
  2. **Shared-platform policy** — an `azp`/app claim bound to sessions plus server-side checks: sign-in gating at every token-minting path, and enforced app checks on endpoint families declared app-scoped. Still one issuer, one key, one user realm; RBAC and root-entity isolation (DD-056) remain the data boundary.
  3. **Credential-domain isolation** — distinct issuer/keys/user namespace/OAuth trust. Only separate deployments (or a deliberate identity-provider architecture with confidential clients/BFFs) provide this.
- **Partitioned and shared frontends are both first-class — multi-frontend works both ways.** Each profile declares the audiences it serves. An exclusive frontend (the Diverse internal admin console) rejects off-audience authentication server-side; a shared set of frontends accepts overlapping audiences and behaves like SSO within the platform. Both modes are configuration.
- **Referral Collection is the contested case.** r1 called it the outer edge of the supported model; the second audit argues it is over the line — the host's own source calls it "a different product", it has its own domain, brand, and bespoke signup/sign-in/reset endpoints. This is now an explicit open product decision (DD-059 Q-004): either RC is declared part of the one Diverse identity/operations realm, or it graduates to its own deployment. Until decided, the shared-mount profile treatment is labeled **transitional**, not the flagship validation of the model.

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

- **The composer interface is already context-rich; the default composer's builders are not.** `AuthMailComposer.compose_*` receives full intents (`mail/types.py`), and the host workaround proves per-recipient routing is possible at that layer. The bottleneck is narrower than "the mail seam": it is (a) `TokenUrlBuilder = Callable[[str], str]` (`mail/composer.py:18`) receiving only the token, and (b) `ComposedAuthMailService` holding exactly one composer for all four send methods (`mail/service.py:17-42`).
- **The intents omit the audience data the library was holding when it built them.** `_build_mail_recipient` (`services/user.py:1608`) copies user id/email/names/phone and drops `user.root_entity_id` — which is sitting on the same ORM row. On the invite path the ordering is decisive: `invite_user` adds the entity membership (which pins `root_entity_id`) *before* firing `on_after_invite` (`routers/auth.py:740` vs `:759`). The workaround's per-send DB lookups re-buy information the library discarded.
- **`request_base_url` is a half-measure.** Every intent carries it, but it is the API origin (`str(request.base_url)`, `services/user.py:1630`), not a frontend origin — and the bundled routers only thread `request` on the magic-link/access-code paths; `forgot_password` and `invite_user` fire their hooks without it (`routers/auth.py:361`, `:759`), so it is `None` exactly where reset links get built.
- **Advertised invite metadata has no producer.** `DefaultAuthMailComposer.compose_invite` reads `target_entity_name`, `inviter_email`, `role_names` from `intent.metadata`; no library call site populates any of them (repo-wide grep). Every default invite email says "your organization" unless the host overrides the hook. (DiverseAPI-postgres populates them manually from its own invitation service.)

## 3. Inconsistencies between the seams

The seams answer the same question three different ways, and the differences are where the bugs live:

1. **Three routing models coexist.** OAuth: frozen per router mount. Composer mail: frozen per process. Challenges: routed per request by a client-supplied `redirect_url`. A host wanting coherent multi-frontend behavior must solve the problem three times in three shapes.
2. **The challenge seam's `redirect_url` is an unvalidated pass-through that is stored but never enforced or returned.** `MagicLinkRequest.redirect_url` / `AccessCodeRequest.redirect_url` (`schemas/auth.py:90,119`) accept any string up to 2048 chars from any unauthenticated caller; the value is persisted on the challenge row and handed to the host's delivery hook — and at verification the API returns only `LoginResponse` tokens, never the stored redirect (`routers/auth.py:473-509,616-676`; it resurfaces only in audit metadata). So the frontend navigates from a *second copy* of the value in its own URL query — two copies, neither canonical, no library allowlist. A host that embeds the stored value in email (the natural reading) can be induced to send a victim a legitimate product email whose link points at an attacker origin. OutlabsAuthUI defends itself (same-origin/relative-path checks in its magic-link and access-code pages), but that is frontend policy, not a library contract.
3. **No token-placement contract.** OutlabsAuthUI and the RC frontend read reset tokens from `?token=` (TanStack `validateSearch`); both Diverse panels read them from a path segment (`/recovery/:token`). The library docs and examples never state a contract, and hosts have now shipped two dead-link defects over exactly this: the d09eb10 commit records that every reset link ever generated by diverse-data-api pointed at a route that did not exist (unnoticed because no environment had a mail provider configured), and DiverseAPI-postgres mixes both forms in one file (`/accept-invite?token=` and `/recovery/{token}`).
4. **Request threading is inconsistent per flow** (see `request_base_url` above).
5. **Email verify has no delivery seam at all** — hooks exist as no-ops, with no request/confirm router or mail intent — while the agent portal ships a `/verify-email/:token` route (agentPanel only; DiverseAdminPanel has none).
6. **`get_oauth_router` is not exported** from `outlabs_auth.routers` (`routers/__init__.py`); consumers must import the private-looking module path, and none of the four production hosts uses it (examples/tests only).
7. **Hooks are a parallel, probe-able extension surface.** Hosts can monkey-patch `user_service.on_after_*` (qdarte-intake does, by documented pattern) — but a host endpoint can also probe the *wrong object* for a hook and silently no-op. That is not theoretical: it is exactly the RC production bug in section 5.1. There is no single canonical "invoke the delivery pipeline" entry point a custom endpoint can be pointed at.

## 4. OAuth: is mounting the router twice actually supported?

Construction-time `success_redirect_url`/`error_redirect_url` means multi-frontend OAuth implies either one mount per frontend or per-flow routing that does not exist today. Verdict from reading `routers/oauth.py`, `routers/oauth_associate.py`, and the test suite — corroborated by the second audit's in-process probe: **same-provider double-mounting is structurally broken today, and nothing tests it.**

- `callback_route_name = f"oauth:{oauth_client.name}.callback"` (`routers/oauth.py:152`) depends only on the provider name, not the prefix. Two mounts of the same provider register two routes with the same name; Starlette's `url_for` returns the first match, so mount B's `/authorize` builds its provider redirect against mount A's callback path and the user completes the flow through mount A's `success_redirect_url` — a silent cross-frontend misroute. (The second audit reproduced this with a live probe. Its probe also showed OpenAPI operation ids do **not** collide — the prefixed paths make them distinct — correcting an r1 subclaim; route reversal is the real defect.)
- The one-time state cookie is provider+flow scoped, not mount or profile scoped (`oauth_state_cookie_name`, `routers/oauth_state_store.py:18-22`): two concurrent flows for the same provider from two frontends in one browser clobber each other's binding cookie, and the login state payload carries no frontend identity at all (`routers/oauth.py:182-190` — the state data dict is empty).
- `oauth_associate.py` has the same shape throughout: provider-only route name, fixed success URL, provider+flow cookie. Any repair must cover association, not just login.
- Explicit per-mount `redirect_url` bypasses `url_for` and makes two mounts *workable*, but it fixes only the reverse-routing defect — not the cookie collision, not the absent per-flow frontend identity.
- Mitigating context: no production consumer mounts OAuth at all today, so this is a forward-looking defect, not a live incident — which is exactly why the model should be corrected now, before Google/Apple sign-in ships on any of these frontends.

**Long-term model (r2, adopted from the second audit)**: not one-router-per-frontend. One provider callback per host/provider; `/authorize` accepts a registered profile id; the signed *and persisted* state binds `profile_id` + a unique flow nonce; the browser cookie binding supports concurrent flows; the callback consumes state and resolves success/error destinations from the bound profile. Prefix-aware route names and exporting `get_oauth_router` remain worth doing as hygiene, but they are not the fix.

## 5. Host evidence

### 5.1 diverse-data-api — the workaround under critique, and a dead production mail path

`src/diverse_data_api/iam/transactional_mail.py` @ d09eb10 subclasses `ComposedAuthMailService` as `AudienceRoutingAuthMailService`: two `DefaultAuthMailComposer` instances (console, Referral Collection), and per send it resolves the recipient's audience by opening a fresh session, fetching the RC root entity by slug, fetching the user, and comparing `root_entity_id`.

What it gets right, and the design keeps:

- Routing by **durable account identity**, not by which endpoint was called — an RC customer who hits `/iam/auth/forgot-password` directly is still an RC customer.
- One immutable composer per audience rather than mutating a shared composer's builders per call — correct under concurrency.

What the library forces it into, which the library should absorb:

- **All four `send_*` methods overridden** to change one decision — pure dispatch duplication.
- **Two DB queries per send in a fresh session** (`SessionLocal` via a late-import seam) to recover `root_entity_id` — data the library had loaded on the `User` row when it built the intent. The late imports exist only to dodge a circular dependency, itself a smell of wiring at the wrong layer.
- **A broad `except Exception: return False`** that silently routes to the console on any failure. r1 endorsed absorbing this fail-open-to-default policy into the library; **r2 reverses that** — see section 8, failure policy. A database outage is not evidence that a user belongs to the default app, and it must not mint valid tokens into wrong-brand emails.
- **Shared path constants across audiences — and they are already wrong.** `LOGIN_PATH = "/auth/login"` and `ACCEPT_INVITE_PATH = "/auth/accept-invite"` are used for both apps, but the RC frontend's login route is `/auth/sign-in` and it has no accept-invite route at all (RC is self-serve signup). Per-audience URLs must include per-audience *paths and route templates*, not just a swapped origin.

**The dead path (second-audit finding, verified in this repo's working session).** The RC SPA does not call `/iam/auth/forgot-password`; it calls the host facade `POST /lead-audit/portal/forgot-password`. That endpoint generates and commits a reset token, then probes `getattr(auth, "hooks", None)` for `on_after_forgot_password` (`src/diverse_data_api/domains/lead_audit_portal/api.py:216-220`) — **no `hooks` attribute exists anywhere in the library** (the real surface is `auth.user_service.on_after_forgot_password`). The probe returns `None`, the guard skips the call, and the endpoint returns `{"status": "accepted"}`. Net: **Referral Collection password-reset emails are never sent in production today**, and the d09eb10 audience-routing service is never reached by the flow it was built for. r1 saw the `getattr` chain, called it fragile, and failed to chase it to ground — this is the second audit's single most valuable catch. Two lessons for the design: (a) there must be one canonical, documented pipeline entry point for custom endpoints, not a hook surface to guess at; (b) silent no-op on a missing extension is exactly the failure mode a fail-closed delivery layer surfaces.

Adjacent host observations for follow-up: `staging.referralcollection.com` is absent from `ALLOWED_ORIGINS` in both code defaults and `.env.example`; the RC route tree has forgot/reset/sign-in only.

### 5.2 DiverseAPI-postgres + DiverseAdminPanel + agentPanel — the audience key is not root entity identity

- Backend: EnterpriseRBAC, single mount at `/iam` (`src/core/outlabs_auth_config.py:206-251`, ten routers), `import-linter` contract forbidding domain imports of `outlabs_auth`. Mail: `DiverseAuthMailComposer(DefaultAuthMailComposer)` + a host-custom `LoggedAuthMailService` that is **not** `ComposedAuthMailService` (`src/services/auth/transactional_mail.py:180-225`) — so any routing added only inside the library's service class does not reach this host without a reusable lower-level selector. One base URL; paths `/accept-invite?token=`, `/login`, `/recovery/{token}`.
- Audience structure: admins/staff live under the canonical internal org root **`diverse-internal`** (`postgres_migration/scripts/migrate_outlabs_users.py:91-97`), departments beneath; agents live under **many** roots (`agent_practice`, `franchise`, `brokerage`, `lender_company` — seed and migration data show 6+ distinct agent-side roots, with new practice roots created at runtime). The migration also creates a fallback **`diverse-general`** root that is *also* `entity_type="organization"` (`migrate_outlabs_users.py:504-509`) — so **root entity type alone is not a safe internal-side predicate**; the canonical internal slug is.
- **Both frontends already discriminate by root entity type**: each fetches `/iam/entities/{root_entity_id}` after login and applies a blocklist — agentPanel rejects `organization|internal_org|department`, DiverseAdminPanel rejects `agent_practice|brokerage|lender_company|franchise|region` (`app/stores/auth.store.ts` in each). The server-side predicate this stack needs (r2, refined per the second audit): canonical slug `diverse-internal` → console; explicit external root types → portal; `root_entity_id=None`, `diverse-general`, and unknown types → **fail unresolved**, not guess; superusers get an explicit home-profile policy rather than copying the frontends' bypass.
- Live breakage: agent invites and resets all point at the console (section 1); agentPanel has no accept-invite page at all, so even a correctly-routed invite link has nowhere to land until the portal adds one — routing design and frontend route contracts have to be stated together. agentPanel does ship a legacy `/verify-email/:token` page (admin panel has none) with no library delivery flow behind it.

### 5.3 qdarte-intake — one user population, three frontends, composer bypassed

Three origins (`subir`, `socios`, `admin`) with per-flow origin settings and hand-built links: library-token invites mailed to `{socios}/aceptar-invitacion?token=` (`services/owner_setup.py:163`, host-rendered Postmark template around a `user_service.invite_user` token), welcome mail to `{socios}/panel/login`, and OutlabsAuth magic links built from a process-wide `magic_link_email_base_url` (default `admin.qdarte.com`) via the documented hook-assignment pattern (`user_service.on_after_magic_link_requested = send_magic_link_email`). It also runs a second, fully custom owner-login magic-link system (`/l/owner/{token}`) unrelated to the library. It re-hard-codes `ttl_days: 7` "matches AuthConfig.invite_token_expire_days" — drift the intents' `expires_at` field already solves. Routing here is by *flow and user class*, not by root entity anything (SimpleRBAC — users have no roots): evidence that the audience key must be host-defined. *(Reconciliation note: the second audit reported the invite/welcome flows "not present at the state of record"; that claim did not survive verification — `services/owner_setup.py` exists at `origin/main` with the cited content. Its adjacent observation stands and matters: `socios.qdarte.com` has no OutlabsAuthUI magic-link landing route today, so this host validates the *need* for per-flow profiles, not the Phase-2 mail design — treat it as a later migration and contract-test case.)*

### 5.4 Baselines

qdarteAPI: SimpleRBAC, three routers at `/iam`, no mail, no OAuth — untouched by any change to the mail seam; profiles must stay optional so this integration stays small. creditos-del-norte-api: EnterpriseRBAC "franchise multi-tenant", no mail wiring yet — and its planned hierarchy (platform root → franchise → client) means platform operators, franchise admins, and clients can share one root, so **root fields alone cannot route it**; it is the acceptance test for a general, async-capable resolver (role/membership/home-profile inputs). OutlabsAuthUI: deliberately one build for many backends via deploy-time `app-config.json`; multi-deployment of the console is an existing, working pattern the design leaves alone.

## 6. Is root entity the natural audience key? (finding 5)

`MembershipService.add_member` pins `user.root_entity_id` on first membership and refuses cross-tree membership (`services/membership.py:173-187`). Observed audience keys across hosts:

| Host | Audience key actually needed |
|---|---|
| diverse-data-api | root entity **slug** (`referral-collection` vs `diverse`) — 2 static roots, disjoint user sets |
| DiverseAPI-postgres | canonical internal **slug** + explicit external root **types**, with unresolved for null/fallback/unknown — N dynamic roots per audience |
| qdarte-intake | **flow / user class** — same population, three frontends; SimpleRBAC, no roots at all |
| creditos-del-norte-api (planned) | **role / membership scope** — several user classes under one shared root |

Conclusion: root entity is a *good default input* — durable, pinned, one indexed read — but it is not *the* key, and "which app initiated this request" is request context no user attribute can carry. Baking `audience := root_entity` into the library would misroute two of four hosts and leave two more unroutable. The design must therefore (a) put root-entity context — id, slug, and type — onto the intents, (b) leave the mapping from context to profile in a host-supplied resolver that may also use roles, memberships, and the requested profile, and (c) accept "unresolved" as a first-class outcome.

## 7. Options

### Option A — pass context to the URL builders

Extend `TokenUrlBuilder` to receive the intent (or a context object) alongside the token; everything else stays host-owned.

- Blast radius: the builder callables' signature. Existing single-frontend builders break, or the library grows arity-sniffing (alpha status favors a clean break over arity magic).
- What it fixes: a host can vary the *URL* per recipient.
- What it does not fix: `app_name`, subjects, support address stay frozen per composer; every host still writes imperative routing; no allowlist appears for `redirect_url`; the challenge and OAuth seams are untouched; the shared-paths defect class remains.
- Verdict: the right *information flow* at the wrong layer. Routing above the composer achieves strictly more with no signature break. Subsumed by option B.

### Option B — frontend profiles + host-supplied resolver (recommended)

The library gains a declarative, flow-wide `FrontendProfile` registry and a resolution component that every destination-bearing flow consults, with a host-supplied resolver over typed context. Detail in section 8.

- Blast radius: additive for the library API (single-composer construction keeps working; intents gain optional fields), but adoption is honestly more than additive — challenge storage gains `profile_id` + canonical-target columns, session/token records gain an `azp` field (Alembic migrations), OAuth state changes shape, and hosts with custom mail services (DiverseAPI-postgres) rewire onto the selector.
- Fixes: per-audience URLs *and* branding *and* route templates; deletes the workaround's subclass and per-send queries; gives `redirect_url` a registered-destination model; one concept spans mail, challenges, OAuth, and session provenance.
- Costs: one more configuration surface; the resolver is host code that can be wrong (pure/testable, but real); schema migrations; per-frontend route-contract tests to keep declared templates honest.
- Fit: expresses all four observed hosts and stays config-level, per DD-025's philosophy.

### Option C — first-class application/client registry (OAuth-provider style)

An `application` SQL model: client ids, per-client redirect allowlists, per-client token policy, dynamic administration.

- Costs: migrations for every consumer, admin CRUD + UI surface, a writable high-value control plane (redirect URIs in the database), availability coupling of every login to the registry, and a second identity axis overlapping the entity tree.
- What it buys over B: dynamic registration, third-party clients, consent, client credentials.
- Verdict: do not build now. Keep profile ids stable and non-secret so a future persisted registry can coexist without pretending it is the same concept. Revisit triggers: third-party client apps, per-client token trust domains, runtime-provisioned frontends.

### Option D — do nothing; document the host-side pattern

Rejected on the evidence: three hosts diverged three ways, two dead-link defect classes shipped, one host regressed behavior it had before adopting the library, one customer-facing reset flow silently sends nothing today, and email is the least-observable channel in the stack. Documenting the pattern would spread its per-send DB queries and exception policy as gospel.

### Option E — separate deployments (the boundary option)

Not a competing feature — the required guidance for genuinely distinct products: independent user namespace, keys, issuer, OAuth trust, admin plane, and incident radius. Costs operational duplication. This is the standing answer wherever level-3 separation (section 1.1) is actually required, and the likely destination for Referral Collection (Q-004).

## 8. Recommended design (detail for DD-059, r2)

Four contract layers, shipped as vertical slices per flow with their schema migrations called out — not "purely additive" sprinkling.

### 8.1 The profile registry — flow-wide, immutable, declared at construction

```python
FrontendProfile(
    key="agent-portal",                        # stable, unique, non-secret
    app_name="Diverse Agent Portal",           # branding for subjects/bodies
    public_origins=("https://portal.meetdiverse.com",),
    routes=FrontendRoutes(                     # typed per flow; token placement explicit;
        login="/login",                        # None = flow unsupported by this frontend
        password_reset="/recovery/{token}",
        accept_invite=None,                    # portal has no invite page today
        magic_link="/auth/magic-link?token={token}",
        oauth_callback=None,
    ),
    redirect_policy=RedirectPolicy(...),       # relative paths and/or origins allowlist
    support_email="support@meetdiverse.com",
)
```

Invariants: profiles are immutable after startup; a profile — not the resolver, not the caller — owns URL construction and branding; selecting a profile for a flow whose route is `None` is a validation failure at wiring time or a fail-closed delivery error at send time, never a guessed link. Both token placements (`?token={token}`, `/recovery/{token}`) are first-class, closing the shipped dead-link defect class.

### 8.2 Resolution — one component, every flow, resolved once

- The host supplies a resolver over a typed `FrontendResolutionContext`: flow kind; recipient identity; `root_entity_id/slug/type` when present; actor and target entity for invites; the **requested profile key** for frontend-originated operations (`app`, a registered key — never a URL); request origin as evidence, not authority. The resolver may be **async** and may query host data (preferably inside the caller's existing session/UoW), but returns only a registered key.
- Resolution happens **once per operation**; the resolved `profile_id` is then persisted through everything downstream: mail/messaging intents, the challenge row, OAuth state, session records, audit events. Downstream code consumes the resolved profile; it never re-resolves.
- The selector is a standalone component consumed by `ComposedAuthMailService` — and equally callable by host-custom mail services (DiverseAPI-postgres's `LoggedAuthMailService`) and host facade endpoints. There is one canonical, documented pipeline entry point for custom endpoints, so nothing probes for hooks on the wrong object again (section 5.1).
- Library convenience resolvers cover the observed cases declaratively (`route_by_root_entity_slug`, `route_by_root_entity_type` composed with slug overrides and an explicit-unresolved default posture); Diverse's real predicate (canonical slug + explicit types + unresolved fallback + superuser home profile) is expressible in one small host function.

### 8.3 Failure policy — fail closed (r2 reversal)

r1 proposed resolver-failure → default profile, logged. The second audit is right that this standardizes wrong-brand links minted during outages, and the repo's own precedent (`token_blacklist_failure_mode`, `api_key_rate_limit_failure_mode`) is fail-closed defaults. r2:

- Unknown profile, unsupported flow, resolver exception, or user/profile mismatch → **fail closed internally**: no message is sent, a structured delivery-failure result and audit/metric record is emitted. Enumeration-resistant endpoints keep their opaque 204/202 outward response.
- A declared default profile is valid only for genuinely unambiguous contexts (the single-frontend host; a no-root SimpleRBAC population by explicit declaration) — never as an exception fallback.
- Post-change security confirmations may fall back to a separately declared **neutral, link-free** notice so the security signal still reaches the user without navigation.

### 8.4 Challenges and redirects — registered destinations, canonical `next_url`

- Magic-link/access-code requests name a registered `app` and a return target that is a relative path or normalizes into the resolved profile's allowlist. The library validates at request time, persists `profile_id` + the canonical target on the challenge row (schema migration), and delivery receives the resolved profile.
- **Verification returns the canonical `next_url`** (alongside tokens), so the frontend stops making a security decision from an untrusted copy of the redirect in its own URL query. The raw stored-but-never-returned `redirect_url` of today — two copies, neither canonical — is retired after a compatibility window.

### 8.5 OAuth — profile-bound state, single callback per provider

As section 4: one provider callback per host/provider; `/authorize` takes a registered profile key; signed + persisted state carries `profile_id` and a unique nonce; cookie binding supports concurrent flows; the callback consumes state, then resolves that profile's registered success/error destinations. Applied to **login and association both**. Route-name prefix-awareness and exporting `get_oauth_router` land as hygiene. Tests must cover concurrent same-provider flows for two profiles, association included.

### 8.6 Sessions and tokens — `azp` provenance, honest semantics

- Every minted session/token records the resolved profile key as an **`azp`-style claim** (authorized party), bound to the refresh/session row (schema migration) and re-validated at rotation. `aud` stays the platform/resource audience — the frontend is the authorized party, not the audience; per-profile `aud` is explicitly rejected as the default model.
- **Sign-in gating**: each profile's `accepted_audiences` (host classification via the same resolver inputs) is enforced at every minting path — password login, magic-link verify, access-code verify, OAuth callback, invite-accept auto-login, refresh — rejecting with a stable `wrong_application` code. Default (no list) accepts everyone: the shared/SSO mode. Partitioned and shared frontends are both plain configuration.
- **What this is, honestly**: level-2 separation (section 1.1). Given correct RBAC + DD-056, a cross-audience session was never a data breach — the gate is defense in depth (an authorization bug on a console endpoint stops being reachable by the external agent population), consistency (the per-frontend JS guards stop being load-bearing and stop drifting), and signal (server-side rejections are visible; client-side ones are not). A public SPA cannot authenticate its `app` selector, so an agent can still obtain a *portal* token and replay it at the shared API — which yields exactly their own privileges. Where an endpoint family must never serve another app's sessions, the host must declare it app-scoped and the `azp` check there is **enforced, not advisory**. Anything stronger — "agent credentials must be inert in the admin trust domain, period" — is level 3: separate deployments or a confidential-client/BFF architecture.

### 8.7 CORS and browser posture

Profiles expose the union of registered origins to the host with a startup validation helper; the library does not mutate host middleware. Documented invariants: redirect allowlists and CORS lists are separate controls that should agree; CORS is not a bearer-token boundary; `Origin` is evidence, never an authorization credential.

### Consumer migration sketch

| Consumer | Change | Direction |
|---|---|---|
| diverse-data-api | **Step 0, independent of this design: fix the dead RC reset path** — the facade must invoke the canonical pipeline (today: `auth.user_service.on_after_forgot_password`), not probe nonexistent `auth.hooks`; add the RC origin to `ALLOWED_ORIGINS`. Then: replace `AudienceRoutingAuthMailService` + `_is_referral_collection_user` + the late-import session seam with two profiles and a slug resolver — RC's profile with corrected routes (`/auth/sign-in`, `accept_invite=None`) — **labeled transitional pending Q-004** (RC may graduate to its own deployment). | Fixes a live bug, deletes code |
| DiverseAPI-postgres | Bump 0.1.0a23 → new release; declare console + portal profiles (`/recovery/{token}` templates); resolver = canonical `diverse-internal` slug + explicit external types, unresolved for null/`diverse-general`/unknown, explicit superuser home profile; wire the selector into `LoggedAuthMailService` (it is not `ComposedAuthMailService` — adoption is a rewiring, not a version bump); `accepted_audiences` replaces both panels' load-bearing JS blocklists. `AGENT_PORTAL_URL` finally gets read. Agent invites stay console-routed or blocked until agentPanel ships an accept-invite route. | Restores lost behavior + closes the cross-portal sign-in hole |
| qdarte-intake / qdarteAPI | qdarteAPI: none. qdarte-intake: none required now; treat as a later migration + contract-test case (its three-origin, per-flow routing and dual magic-link systems are the stress test for profiles, not proof of them). Hook signatures stay frozen so its assignment pattern keeps working. | Optional, later |
| creditos-del-norte-api | Greenfield adopter; its shared-root hierarchy is the acceptance test for the async resolver (role/membership inputs). | New |

### Testing obligations

Unit: profile → URL rendering for both token placements and `None`-route rejection; resolver outcomes (requested-key valid / unknown / identity-derived / no-root / exception → fail closed); single-composer construction byte-identical behavior. Integration: end-to-end forgot-password producing per-audience links from one mount; fail-closed delivery on unresolved audiences with opaque outward responses; challenge `next_url` round-trip; audience gating across every minting path in partitioned and shared configurations (`wrong_application` contract); OAuth concurrent same-provider flows for two profiles, login and association. Cross-repo: route-contract fixtures per frontend per flow (declared template ↔ actual route), including the RC facade endpoints. Example: the enterprise example becomes two-profile so the documented recipe is the multi-frontend one.

## 9. Long-term direction — the maturity ladder

Where this sits in the library's trajectory as a general-purpose auth foundation (maintainer-reviewed framing):

1. **Anonymous frontends** (today): the user is the only subject. Remains fully supported — qdarteAPI's three-router integration must stay this small.
2. **Named frontends** (profiles, layers 8.1–8.4): declared configuration for routing, branding, landing correctness.
3. **Frontends as policy subjects** (layers 8.5–8.6): sign-in gating and `azp` provenance — as far as enforcement can go for public browser clients, which is acceptable because identity + entitlements (RBAC/ABAC/entities) remain the library's center of gravity and the real boundary.
4. **Frontends as principals** (the deferred registry): client ids/secrets, confidential clients, per-client trust — only rung where "which app is calling" becomes cryptographically true, and only for clients that can hold secrets (the fleet already contains one first-party BFF: qdarte-intake). Climbed when a consumer demonstrates the need, not before.

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

## 11. Reconciliation record (r2)

Independent second audit: [`MULTI_FRONTEND_SECOND_AUDIT.md`](./MULTI_FRONTEND_SECOND_AUDIT.md). Both audits converge on the core diagnosis and the profiles + host-resolver direction. Disposition of its material deltas:

**Adopted into r2** — flow-wide `FrontendProfile` (was mail-first); resolution as a standalone component below all mail services, async-capable, resolved once and persisted; **fail-closed** failure policy (r1's default-fallback endorsement reversed); registered-destination redirects with verification-time canonical `next_url`; OAuth single-callback profile-bound state including association and concurrency tests (replacing one-router-per-frontend); `azp` claim with `aud` kept as resource audience (replacing r1's "optionally per-profile aud"); honest three-level separation framing with enforced-not-advisory checks on declared app-scoped endpoints; migration characterized with explicit schema migrations; Diverse resolver predicate hardened (canonical slug, `diverse-general`, unresolved posture, superuser policy); Referral Collection reframed as open product decision Q-004 with the shared-mount profile labeled transitional.

**Second-audit corrections of r1, verified and accepted** — the RC facade's dead `auth.hooks` reset-mail path (its most valuable find); duplicate-OpenAPI-id subclaim withdrawn (route reversal is the defect); "both panels ship verify-email" corrected to agentPanel only; "every URL-producing seam is fixed at wiring time" corrected to binding-time inconsistency; access-granted flow labeled host-only (no library production call site); `oauth_associate` carried through the repair; "additive" blast-radius language corrected (custom `LoggedAuthMailService` adoption, schema migrations).

**Second-audit claims rejected on re-verification** — its report states the qdarte-intake invite/welcome flows are "not present at the state of record"; they are: `apps/api/qdarte_intake/services/owner_setup.py` exists at `origin/main` with `aceptar-invitacion?token=` link construction (line 163) around a library `invite_user` token, and the welcome-mail path beside it. Its adjacent point — that qdarte-intake validates the need for per-flow profiles rather than the mail design — stands and is incorporated in 5.3.

**From maintainer review (same day)** — the security classification in 8.6 (cross-audience sessions were never a data breach given RBAC; the gate is depth/consistency/signal); the maturity ladder and not-an-IdP posture in section 9; and the requirement that partitioned and shared frontends both be first-class.
