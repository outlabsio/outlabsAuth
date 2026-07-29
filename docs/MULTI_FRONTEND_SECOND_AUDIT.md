# Independent Second Audit: Multi-Frontend Support

**Audit date:** 2026-07-29

**Library state of record:** `outlabsAuth@main` `a979661` (`outlabs-auth` 0.1.0a24)

**Scope:** one FastAPI host, one OutlabsAuth mount/security realm, multiple first-party frontends

**Method:** repository and test-suite inspection only; no implementation or consumer changes

## Executive conclusion

OutlabsAuth does not currently have multi-frontend support as a coherent concept. It has several individually useful delegation seams, but they bind at incompatible times and carry incompatible context:

- the abstract mail composer receives a rich per-send intent, while the built-in URL builders receive only a token;
- the composed mail service owns one process-wide composer;
- magic-link and access-code requests carry an arbitrary caller-provided `redirect_url`, but the library neither validates it as a URL nor returns it after verification;
- OAuth landing URLs bind when the router is constructed, and duplicate same-provider mounts collide in route reversal and browser-cookie state;
- lifecycle hooks are another parallel host extension surface, including two unused email-verification hooks;
- no application, client, frontend, profile, or redirect-allowlist model ties these flows together.

The cheapest change is to pass the complete intent to mail URL builders. That would fix only mail and would preserve the architectural fragmentation. The right alpha-stage change is an immutable, host-declared **frontend profile registry**, combined with a **trusted, host-supplied resolver** for server-originated flows and an explicit registered profile identifier for frontend-originated flows. Every destination-bearing flow should resolve to a profile key, never an arbitrary base URL.

Profiles should guarantee destination routing, route shape, redirect validation, and branding selection. They must not be described as tenants or as data/credential isolation. The default security realm still shares users, signing keys, issuer/audience, OAuth identities, database, and operational fate. Server-side RBAC/ABAC remains the data boundary. A deployment that needs an independent user namespace, data perimeter, credential blast radius, OAuth trust configuration, compliance lifecycle, or administrative control plane needs a separate OutlabsAuth deployment.

I recommend carrying a stable `app_id`/authorized-party claim in newly issued sessions now, while the library is alpha, but **not** overloading JWT `aud`: the audience is the resource/API, whereas the browser application is the authorized party. Merely adding that claim does not isolate credentials. Hard per-application token acceptance must be an explicit API policy; independently secured products still require separate deployments.

---

# Part A — Independent audit

This Part A was completed and written before opening the quarantined first audit, DD-059, or DD-059-related vault material.

## 1. Scope, coordinates, and evidentiary limits

I audited the states named in the brief:

| Repository | Audited state |
|---|---|
| `outlabsAuth` | `main` at `a979661` |
| `diverse-data-api` | exact commit `d09eb10` (the recorded `origin/main` state) |
| `DiverseAPI-postgres` | `postgres` at `e6d652f6`, plus legacy `main` |
| `agentPanel` | `postgres` |
| `DiverseAdminPanel` | `origin/postgres` |
| `diverse-referral-collection` | `main` |
| `OutlabsAuthUI` | `main` |
| `qdarteAPI` | `main` |
| `qdarte-intake` | `main` at `e7c25ee` |
| `creditos-del-norte-api` | `main` at `3a81525` |

“Not found” statements below mean a repository-wide source/test search at the named state, not a claim about untracked files or live infrastructure. I did not inspect or quote untracked environment files. CORS conclusions are therefore about tracked defaults/examples; a live deployment can override them.

## 2. Core model: no frontend/application concept

The first hypothesis is correct. `AuthConfig` contains database settings and a single process-wide `jwt_audience`, but no frontend/application registry, public-client ID, landing routes, branding profile, or redirect allowlist (`outlabsAuth@main outlabs_auth/core/config.py:16-61`). A source-tree inspection of `outlabs_auth/models/sql/` found no application/client/frontend SQL model.

The single `jwt_audience` is described as cross-application security, but it identifies the one token audience for the whole mount; it does not identify which frontend initiated a session (`outlabsAuth@main outlabs_auth/core/config.py:55-61`).

This absence matters because “which frontend?” is currently rediscovered independently by mail composers, request hooks, OAuth router construction, frontend query strings, and host-specific database lookups. There is no shared identifier whose meaning can survive a flow from request, to stored challenge/state, to delivery, to verification, to issued session.

## 3. Destination seam inventory

| Flow / seam | Current decision owner | Binding time | Context at decision point | Audit result |
|---|---|---|---|---|
| Invite email | Host `AuthMailComposer`; built-in builder | Composer construction for built-in URL; per-send for a custom composer | Full `InviteMailIntent`: recipient, token, expiry, request base, metadata | Abstract seam is capable; built-in builder is token-only and profile-blind |
| Forgot-password email | Same | Same | Full `ForgotPasswordMailIntent` | Same limitation |
| Reset confirmation | Same | Composer construction | Recipient, change time, request base, metadata; no token | Login URL builder receives no context |
| Access-granted email | Same | Composer construction | Recipient, request base, metadata | Login URL builder receives no context; no library production call site found |
| Mail service dispatch | Host/library | Process construction | Each complete intent reaches the service | `ComposedAuthMailService` has one composer for all four methods |
| Lifecycle hooks | Host override/monkey patch | Process construction; invoked per request | User, sometimes token/request/redirect | Parallel extension surface; easy to bypass the mail service accidentally |
| Email verification | Host hook in theory | Process construction/per request | User, token, request | Hooks exist, but no request/confirm router or mail integration was found |
| Magic-link delivery | Host messaging service | Per request | Challenge type, recipient, secret, expiry, channel, raw redirect, request base, metadata | Rich seam; no profile concept and redirect is unvalidated |
| Access-code/OTP delivery | Host messaging service | Per request | Same, with email/SMS/WhatsApp channel | Rich seam; no profile concept and redirect is unvalidated |
| Phone verification delivery | Host messaging service | Per authenticated request | User, code, channel, request base, metadata | No landing destination today; should still carry profile context for branding |
| Magic/access verification landing | Frontend | Before request and after verification | URL query chosen by frontend | API returns tokens only; stored redirect is not returned |
| OAuth provider callback URL | Library router factory / host argument | Router construction | Provider, fixed callback or reverse-route name | One fixed callback per router instance |
| OAuth success/error destination | Host router arguments | Router construction | Fixed URLs only | No per-request/user/profile choice |
| OAuth association success | Host router argument | Router construction | Fixed success URL only | Same multi-mount defects as login OAuth |
| OAuth state/cookie | Library | Per authorize request | Provider and flow; association also has user ID | No frontend/mount identity; same-provider mounts collide |
| Password/invite token placement in a browser URL | Host URL builder/frontend | Composer construction and frontend route design | Token only in built-in composer | Library deliberately has no route-shape contract |
| Login/register/logout/session endpoints | Frontend/host after API response | Per request | Tokens or normal HTTP response | No library destination decision |

### 3.1 Mail has enough context at the abstract seam, but not at the convenience seam

The mail intent types carry the useful raw material: recipient identity, request base URL, flow-specific token/timestamps, and metadata (`outlabsAuth@main outlabs_auth/mail/types.py:102-140`). The abstract `AuthMailComposer` receives the entire typed intent for each operation (`outlabsAuth@main outlabs_auth/mail/composer.py:22-42`).

The built-in convenience API discards that advantage:

> `TokenUrlBuilder = Callable[[str], str]`
>
> `SimpleUrlBuilder = Callable[[], str]`

(`outlabsAuth@main outlabs_auth/mail/composer.py:18-19`)

`DefaultAuthMailComposer` stores one `app_name` and fixed invite/reset/login builders at construction (`outlabsAuth@main outlabs_auth/mail/composer.py:45-61`). It invokes invite and reset builders with only the token, and the login builder with no arguments (`outlabsAuth@main outlabs_auth/mail/composer.py:63-64,107-108,158-160`). Thus the abstract interface can route per intent, but the built-in composer—the API consumers are encouraged to instantiate—cannot.

The orchestration layer compounds this: `ComposedAuthMailService` stores one provider and one composer, and all four send methods call that composer (`outlabsAuth@main outlabs_auth/mail/service.py:17-42`). A host wanting per-user routing while retaining the default composer must replace/override all four methods or build a more capable composer.

The `diverse-data-api` workaround demonstrates exactly that blast radius. It constructs two fixed composers and subclasses the service to override invite, forgot-password, reset-confirmation, and access-granted delivery (`diverse-data-api@d09eb10 src/diverse_data_api/iam/transactional_mail.py:151-159,215-267`). Its decision requires a fresh host database session to load the user and the `referral-collection` root (`…/transactional_mail.py:182-212`). This works around the API shape, but it is not a safe pattern to bless:

- every flow must be remembered;
- the resolver is outside the library's transaction/context;
- resolver failure silently selects the console (`…/transactional_mail.py:195-212`);
- any new mail method will default incorrectly unless every host subclass is updated;
- profile selection and brand selection are inseparable custom code.

The host correctly avoids mutating one shared composer during an async send because that would create a cross-recipient concurrency race (`diverse-data-api@d09eb10 src/diverse_data_api/iam/transactional_mail.py:223-227`).

### 3.2 Metadata exists but the library does not populate its own default keys

The default composer reads `target_entity_name`, `inviter_email`, `role_names`, and `is_resend` (`outlabsAuth@main outlabs_auth/mail/composer.py:66-78,160-168`). The user-service helpers accept metadata and copy it into intents (`outlabsAuth@main outlabs_auth/services/user.py:340-420,1640-1647`).

However, the library's normal production router calls do not supply any of those keys:

- forgot password calls `on_after_forgot_password(user, token)` (`outlabsAuth@main outlabs_auth/routers/auth.py:350-362`);
- reset confirmation calls `on_after_reset_password(user)` (`…/routers/auth.py:386-392`);
- invite and resend call `on_after_invite(user, token)` (`…/routers/auth.py:723-759`; `outlabsAuth@main outlabs_auth/routers/users.py:1391-1398`).

No library production call to `send_entity_access_granted_email` was found. The useful metadata path is therefore host-only today. `DiverseAPI-postgres` manually supplies these keys from its invitation service (`DiverseAPI-postgres@postgres src/services/invitations/invitation_service.py:269-286`; `…/src/services/auth/invitation_hooks.py:20-100`).

The recipient object itself contains `user_id`, email/name, and phone information, but not `root_entity_id` or any application/audience value (`outlabsAuth@main outlabs_auth/mail/types.py:10-24`; `…/services/user.py:1607-1616`). A generic resolver cannot make the same root-based decision as the Diverse host without another query.

### 3.3 Lifecycle hooks are a separate, fragile integration surface

`UserService` exposes no-op registration, verification, and OAuth hooks, while forgot/reset/invite hooks delegate to the mail helpers and magic/access hooks delegate to messaging (`outlabsAuth@main outlabs_auth/services/user.py:96-182`). Hosts can and do monkey-patch these methods.

This creates two correctness hazards:

1. A host can implement a custom endpoint and call the wrong extension object.
2. A host can bypass profile resolution by replacing a hook directly.

There is a concrete instance of the first hazard. Referral Collection calls its custom `/lead-audit/portal/forgot-password` endpoint, not `/iam/auth/forgot-password` (`diverse-referral-collection@main src/features/auth/api/request-password-reset.ts:21-26`). The backend generates and commits a reset token, then looks for `auth.hooks.on_after_forgot_password` (`diverse-data-api@d09eb10 src/diverse_data_api/domains/lead_audit_portal/api.py:207-219`). No `auth.hooks` API exists in the audited library. As written at the state of record, the lookup returns `None` and no message is sent. The newly added audience-routing mail service is never reached for the customer-facing forgot-password flow.

Email verification is another incomplete seam. `on_after_request_verify` and `on_after_verify` exist as no-ops (`outlabsAuth@main outlabs_auth/services/user.py:116-120`), and `UserService.verify_email` exists, but I found no library request-verification/confirm-verification router or transactional mail intent. Access-code verification can mark an email verified, but that is authentication challenge behavior, not a destination-bearing email-verification flow. Any future verification feature must use the same profile/destination pipeline rather than adding a third bespoke mail path.

## 4. Magic links and access codes: lifecycle and security

### 4.1 Current lifecycle

Both request schemas accept `redirect_url` as an optional plain string with only a 2048-character maximum (`outlabsAuth@main outlabs_auth/schemas/auth.py:86-94,103-123`). There is no URL parsing, allowed scheme, registered origin, or relative-path constraint.

For magic links:

1. The router passes the caller value into token generation and the delivery hook (`outlabsAuth@main outlabs_auth/routers/auth.py:446-466`).
2. The auth service stores it on the challenge row and includes it in audit metadata (`outlabsAuth@main outlabs_auth/services/auth.py:967-1009`).
3. The SQL model persists it verbatim in `VARCHAR(2048)` (`outlabsAuth@main outlabs_auth/models/sql/auth_challenge.py:65-69`).
4. The messaging intent receives the same value (`outlabsAuth@main outlabs_auth/services/user.py:185-212`).
5. Verification consumes the token and returns only the normal `LoginResponse` tokens (`outlabsAuth@main outlabs_auth/routers/auth.py:473-509`).

Access codes follow the same path: request value to stored challenge and messaging intent (`outlabsAuth@main outlabs_auth/routers/auth.py:588-604`; `…/services/auth.py:1081-1126`; `…/services/user.py:214-245`), then a token-only `LoginResponse` after verification (`…/routers/auth.py:616-676`). Verification uses the stored value only in internal audit-event metadata (`outlabsAuth@main outlabs_auth/services/auth.py:1471-1491`; magic link: `…/services/auth.py:1696-1712`), not in the API result.

Therefore the library currently stores a navigation decision that it never enforces or returns. In practice the frontend carries a second copy in its own URL and follows that.

OutlabsAuthUI mitigates the immediate open-redirect risk in its own implementation: magic-link and access-code pages accept relative paths or same-origin absolute URLs and otherwise fall back to the dashboard (`OutlabsAuthUI@main src/features/auth/components/magic-link-page.tsx:45-64`; `…/access-code-page.tsx:60-80`). It also sends an absolute URL on its own origin when requesting the challenge (`…/magic-link-page.tsx:235-239`; `…/access-code-page.tsx:82-106`). That frontend defense is good, but it is not a library contract and another host composer can place the arbitrary value in a trusted-brand email.

### 4.2 Security assessment

As-is, `redirect_url` is a host-facing sharp edge:

- a client can cause the server to persist an arbitrary scheme/string;
- a host messaging implementation may embed it directly and create a trusted-brand phishing or open-redirect path;
- delivery and verification do not agree on a canonical value;
- the same value is duplicated in challenge storage and in a browser query parameter;
- an `Origin` header, if used by a host as a profile selector, is not an authorization credential and is absent from non-browser clients.

The correct API is not “accept any redirect URL and ask every host to be careful.” A request should name a registered `app_id` and supply either a relative path or a URL that normalizes into that profile's allowlist. The library should persist the resolved profile and canonical return target. Verification should return the canonical `next_url` (or a one-time handoff that resolves to it), so the frontend does not make its own security decision from an untrusted email query parameter. A compatibility period can accept `redirect_url`, but it must be validated at request time against the selected profile.

The `app_id` of a browser public client is not secret. It is safe as a selector only because it can select from host-declared destinations; it must never grant data access. Where a user is not permitted to use the requested profile, the trusted resolver must reject the `(user, requested_profile, flow)` combination.

## 5. OAuth: duplicate mounting is not supported

The OAuth login router fixes provider callback configuration plus `success_redirect_url` and `error_redirect_url` when the router is constructed (`outlabsAuth@main outlabs_auth/routers/oauth.py:127-147`). Its callback route name is only `oauth:{provider}.callback`, regardless of prefix or frontend (`…/routers/oauth.py:150-163`). When no explicit provider callback is supplied, `/authorize` uses `request.url_for` with that non-unique name (`…/routers/oauth.py:171-183`). Login state contains an empty application payload (`…/routers/oauth.py:182-190`), and callback success/error always uses the construction-fixed destinations (`…/routers/oauth.py:253-260,321-327`).

The state cookie is keyed only by flow and provider:

> `outlabs_auth_oauth_{flow}_{provider}`

(`outlabsAuth@main outlabs_auth/routers/oauth_state_store.py:18-22`)

It is set for path `/`, and the persisted record lookup checks state and provider, not frontend/mount (`…/routers/oauth_state_store.py:48-56,70-89`). Two concurrent Google login flows for two frontends overwrite the same binding cookie; the first callback then fails browser binding. Even without concurrency, the state does not carry the intended frontend.

I mounted the same provider twice under distinct prefixes in a temporary in-process FastAPI probe. OpenAPI generated distinct operation IDs because the paths differ, so OpenAPI ID collision is **not** the blocker. However, `app.url_path_for("oauth:google.callback")` resolved the first mount's callback. Consequently the second mount's default callback URL points to the first mount. Explicit `redirect_url` avoids that one reverse-routing defect, but not the shared cookie or fixed landing policy.

The integration suite constructs one OAuth router at a time; no same-provider multi-mount test was found (`outlabsAuth@main tests/integration/test_oauth_router_callback_paths.py:138,226,271,600`).

OAuth account association has the same shape: callback route name `oauth-associate:{provider}.callback`, fixed success URL, and state/cookie flow `associate` keyed without frontend/mount (`outlabsAuth@main outlabs_auth/routers/oauth_associate.py:65-104,121-143,153-182,258-263,316-323`).

The long-term fix is not “mount the same provider N times.” Use one provider callback per host/provider, put the registered profile ID and a unique flow/mount nonce in signed and persisted state, bind the browser cookie to that identity, and resolve success/error destinations from the profile after consuming state. If multiple physical router mounts remain supported, route names, state rows, and cookie names must include a stable mount/profile ID and tests must cover concurrent flows.

## 6. Root entities are useful host data, not a universal frontend identity

`MembershipService.add_member` finds the root of the target entity tree, assigns `user.root_entity_id` on the first membership, and rejects a later membership from a different tree (`outlabsAuth@main outlabs_auth/services/membership.py:157-187`). This makes root identity a durable security-realm/organization discriminator in some EnterpriseRBAC deployments.

It is not a general frontend discriminator:

- SimpleRBAC users may have no entity or root.
- An invite without `entity_id` explicitly creates the invitee with `root_entity_id=None`; direct roles do not change that (`outlabsAuth@main outlabs_auth/routers/auth.py:723-759`).
- Several frontends can legitimately serve users in the same root.
- A single frontend can serve many roots.
- In a hierarchy such as platform → franchise → client, every member can share the platform root while needing different interfaces.
- “Which app initiated this login?” is request context, not a stable property of the user.

The correct abstraction is a host resolver that may use root identity, memberships, roles, actor context, and requested profile, rather than teaching the library that root ID equals application.

## 7. Consumer findings

### 7.1 `diverse-data-api`: workaround is incomplete, and Referral Collection is likely beyond the boundary

There is one EnterpriseRBAC instance and one `/iam` router family (`diverse-data-api@d09eb10 src/diverse_data_api/iam/auth.py:185-202,241-266`). Commit `d09eb10` added a root-based two-composer mail router because the Referral Collection app was sending customers to the Diverse console (`…/transactional_mail.py:34-38,215-227`).

The root-slug predicate is technically reasonable for accounts that have the expected membership: first membership pins the root, and `referral-collection` is a stable host-controlled slug. But its exception policy is unsafe for correctness: any lookup failure silently selects the console (`…/transactional_mail.py:195-212`). A database outage should not generate a valid token and email it under the wrong product. The anonymous HTTP response may remain opaque, but the internal operation should fail closed and emit an observable delivery failure.

More importantly, the actual Referral Collection SPA bypasses `/iam` for password reset (`diverse-referral-collection@main src/features/auth/api/request-password-reset.ts:8-26`; `…/reset-password.ts:18-25`). The custom backend endpoint fails to call the real `user_service` hook, as described in §3.3. Thus the recorded workaround does not fix the user-facing reset flow.

The proposed RC invitation URL is also not currently viable. The host builds `/auth/accept-invite?token=…` for both profiles (`diverse-data-api@d09eb10 src/diverse_data_api/iam/transactional_mail.py:29-38,67-85`), but the RC route tree contains forgot-password, reset-password, and sign-in only; no accept-invite route was found (`diverse-referral-collection@main src/app/router/routes/`). Its reset route does correctly read `?token=` (`…/auth.reset-password.tsx:7-22`).

Tracked CORS does not cover the RC origin. The code default is localhost-only (`diverse-data-api@d09eb10 src/diverse_data_api/platform/config.py:88-99`); `.env.example` adds `auth-data.meetdiverse.com` and `data.meetdiverse.com`, but not `staging.referralcollection.com` (`diverse-data-api@d09eb10 .env.example:86-89`). A live environment or regex may differ; this audit cannot verify it.

Finally, the host's own source calls Referral Collection “a different product” (`diverse-data-api@d09eb10 src/diverse_data_api/iam/transactional_mail.py:34-36`; `…/platform/config.py:64-68`). It has a customer-facing contract, separate brand/domain, bespoke signup/sign-in/reset endpoints, and a dedicated root. On the evidence available, it belongs in a separate deployment unless the maintainer explicitly accepts a shared user namespace, keys, admin plane, database breach radius, OAuth configuration, and operational lifecycle as one Diverse platform. A profile is not a principled way to make an unrelated product separation problem disappear.

### 7.2 `DiverseAPI-postgres`: the cutover regressed a real audience decision

The `postgres` host has one mail composer. `_get_auth_ui_base_url` selects only `OUTLABS_AUTH_UI_URL`/`FRONTEND_URL`; `AGENT_PORTAL_URL` is configured but unused in mail (`DiverseAPI-postgres@postgres src/services/auth/transactional_mail.py:37-40,58-82`; `…/src/core/config.py:141-144`). Every invite, reset, confirmation, and access-granted message therefore points to the admin panel (`…/transactional_mail.py:94-177,180-225,334-336`).

The legacy `main` branch made an explicit per-user decision: agent users received `AGENT_PORTAL_URL`, other users `FRONTEND_URL`, for both reset and email-change verification (`DiverseAPI-postgres@main src/api/routes/users.py:587-618,1208-1214`). The OutlabsAuth cutover preserved the link route (`/recovery/{token}`) but lost the audience branch.

The precise server-side routing predicate should reflect the migrated entity topology:

- the canonical internal root slug is `diverse-internal` (`DiverseAPI-postgres@postgres postgres_migration/scripts/migrate_outlabs_users.py:91-97`);
- internal users are rooted at that `organization`, with departments below it (`…/migrate_outlabs_users.py:480-486,772-804`);
- solo agents have `agent_practice` roots; corporate and lender users have `brokerage` and `lender_company` roots; brokerage-owned agents inherit the brokerage root (`…/migrate_outlabs_users.py:488-509,2083-2133`);
- migrated users are assigned that root directly (`…/migrate_outlabs_users.py:2150-2165`).

The frontend guards corroborate the split. Agent Panel rejects internal `organization`/`internal_org`/`department` types (`agentPanel@postgres app/stores/auth.store.ts:190-205`). Admin Panel rejects `agent_practice`, `brokerage`, `lender_company`, `franchise`, and `region` (`DiverseAdminPanel@origin/postgres app/stores/auth.store.ts:200-212`).

A robust resolver should therefore:

1. route canonical root slug `diverse-internal` to Admin Panel;
2. route the explicit external root types above to Agent Panel;
3. apply an explicit home-profile policy for superusers rather than copying the frontends' bypass;
4. reject/null-route `root_entity_id=None`, `diverse-general`, or unknown types instead of guessing.

Type `organization` alone is insufficient because the migration's fallback `diverse-general` is also an organization (`…/migrate_outlabs_users.py:504-509`).

Migration cannot be completed by adding a resolver alone. Both panels accept reset tokens in `/recovery/{token}` (`agentPanel@postgres app/pages/recovery/[token].vue:168-179`; `DiverseAdminPanel@origin/postgres app/pages/recovery/[token].vue:76-86`). Admin Panel supports invitation tokens at `/accept-invite?token=…` (`DiverseAdminPanel@origin/postgres app/pages/accept-invite.vue:65-74`), but Agent Panel has no accept-invite route. Agent invitations cannot be routed there until that frontend route exists or the workflow deliberately uses Admin Panel for setup and Agent Panel after login.

Tracked CORS is substantially better than mail routing: local defaults include both ports, and the environment examples include admin and portal origins for playground/beta/staging/production (`DiverseAPI-postgres@postgres src/core/config.py:103-138`; `…/.env.example:22-27`). Live values remain unverified.

### 7.3 OutlabsAuthUI: reusable deployment, not a multi-profile runtime

OutlabsAuthUI supports one runtime-selected API base, auth prefix, and brand configuration. It merges build environment, `/app-config.json`, and inline runtime config, and production refuses an invalid/missing configuration (`OutlabsAuthUI@main src/lib/runtime-config.ts:3-19,106-155,183-202`). Every request is routed to that one base/prefix (`OutlabsAuthUI@main src/lib/api/config.ts:7-27`).

This is a good “one build artifact, many deployments/backends” model. It is not evidence that one browser runtime selects among multiple profiles.

Its actual auth-route contracts are:

| Flow | Route and token convention |
|---|---|
| Invite | `/auth/accept-invite?token=…` (`OutlabsAuthUI@main src/app/router/routes/auth/accept-invite.tsx:6-12`) |
| Reset | `/auth/reset-password?token=…` (`…/auth/reset-password.tsx:6-12`) |
| Magic link | `/auth/magic-link?token=…&redirect=…` (`…/auth/magic-link.tsx:6-13`) |
| Access code | `/auth/access-code?mode=…&redirect=…`; the user types the delivered code (`…/auth/access-code.tsx:6-13`) |
| OAuth callback | access and refresh tokens in the URL fragment (`OutlabsAuthUI@main src/features/auth/components/oauth-callback-page.tsx:11-29`) |

### 7.4 `qdarte-intake`: three origins, two unrelated magic-link systems, one fixed library landing app

`qdarte-intake` embeds one SimpleRBAC and mounts one library auth surface (`qdarte-intake@main apps/api/qdarte_intake/auth.py:43-105`; `…/main.py:88-100`). SimpleRBAC supplies no durable root discriminator.

The host has two distinct “magic link” systems. The bespoke outreach/claim system serves public `subir`/`socios` flows; the OutlabsAuth magic-link hook is for library users. The library flow is disabled by default and, when enabled, monkey-patches `user_service.on_after_magic_link_requested` (`qdarte-intake@main apps/api/qdarte_intake/auth.py:69-103`).

That hook builds every email landing page from one process-wide `MAGIC_LINK_EMAIL_BASE_URL`, defaulting to `https://admin.qdarte.com`, while preserving the caller's `redirect_url` as a query parameter (`qdarte-intake@main apps/api/qdarte_intake/auth_user_service.py:41-64,67-98`; `…/config.py:338-346`). It can redirect after authentication to a different same-platform page, but it cannot choose different landing UI/brand per recipient or request without changing process configuration.

The tracked CORS model explicitly combines `public_base_url` with configured extra origins (`qdarte-intake@main apps/api/qdarte_intake/main.py:69-80`), and the example lists `subir`, `socios`, and `admin` (`…/.env.example:13-19`). That covers the intended shape if production follows the example. The current `apps/web` route tree has no OutlabsAuth `/auth/magic-link` landing page; that route belongs to the separately deployed OutlabsAuthUI at `admin.qdarte.com`. Routing a library magic link directly to `socios.qdarte.com` would therefore be a dead link until that surface implements the route.

This host is the clearest proof that profile resolution needs two inputs: `subir` is anonymous and has no auth profile; an interactive request from `admin` or future authenticated `socios` can name its registered profile, while server-originated invitations need a host policy based on role/membership/business context. Root entity cannot solve it.

### 7.5 `qdarteAPI`: minimal consumer, no destination seam mounted

`qdarteAPI` creates one SimpleRBAC (`qdarteAPI@main app/auth.py:222-231`) and intentionally mounts only session, self-service user, and API-key routers (`qdarteAPI@main app/domains/auth/api/routes.py:1-12,24-47`). No transactional mail/messaging service or library magic/access/OAuth route was found. Its other “magic link” client calls qdarte-intake's bespoke outreach bridge and is unrelated.

Its production CORS list is entirely environment-driven; tracked defaults cover only local development (`qdarteAPI@main app/config.py:14-21,211-227,448-455`; `…/app/main.py:99-105`). It is not currently a multi-frontend auth adopter, but profiles should remain optional so this integration stays small.

### 7.6 `creditos-del-norte-api`: future adopter for which root is likely the wrong selector

At `main`, this is an undeployed skeleton with one EnterpriseRBAC mount and one configured admin origin (`creditos-del-norte-api@main README.md:3-18`; `…/src/creditos_del_norte_api/iam/auth.py:17-29`; `…/platform/config.py:35-40`). It has no mail or challenge messaging integration.

The intended hierarchy is platform root → franchise → client (`creditos-del-norte-api@main README.md:16-18`). In such a single entity tree, platform operators, franchise admins, and clients may all have the same `root_entity_id`. A future admin frontend and `mi.creditosdelnorte.ar` client portal therefore cannot route by root. The resolver will need role/membership scope or an explicit home-profile attribute, plus the requested profile for interactive flows. This is a concrete reason not to hard-code root-based semantics in the library.

## 8. Token-placement and route compatibility

The library defines the HTTP token exchange (`token` in JSON for invite/reset/magic verification), but it does not define how a host puts a token into a frontend URL. `DefaultAuthMailComposer` delegates that entirely to a `Callable[[str], str]`. Actual frontends disagree:

| Frontend | Invite | Reset | Magic/access |
|---|---|---|---|
| OutlabsAuthUI | query `?token=` | query `?token=` | magic query token; access code typed |
| DiverseAdminPanel | query `?token=` | path `/recovery/{token}` | not found |
| agentPanel | **route absent** | path `/recovery/{token}` | not found |
| Referral Collection | **route absent** | query `?token=` | not found |
| qdarte `apps/web` | no library auth landing routes found | none | bespoke `/l/{token}` is unrelated |

This is not theoretical. `d09eb10` documents that the old `/auth/reset-password/<token>` links were dead because both relevant React frontends expected `?token=`, and the bug went unnoticed because no environment had a mail provider configured (`diverse-data-api@d09eb10 src/diverse_data_api/iam/transactional_mail.py:75-83`).

A profile must therefore declare typed route templates per supported flow, and construction/startup validation should reject a profile that is selected for a flow it does not support. A free-form base URL plus assumed common routes is insufficient.

## 9. Separation guarantees and the honest boundary

| Property | Frontend profiles can guarantee | They cannot guarantee by themselves |
|---|---|---|
| Link/landing routing | Registered origin, route template, token placement, canonical post-auth target | That the frontend actually implements its declared route without contract tests |
| Branding | App name, sender/reply-to choice, template/theme keys, support contact | Independent legal identity or mail-domain reputation unless separately configured |
| Redirect safety | Scheme/origin/path allowlist and server-normalized `next_url` | Safety of arbitrary host callbacks that ignore the resolved profile |
| Browser origin handling | One source of required frontend origins; startup validation/helper | Automatic correctness of host CORS middleware, reverse proxies, CSP, cookies, or DNS |
| Data isolation | Nothing beyond selecting UI; resolver can reject an inappropriate profile | Tenant isolation. RBAC/ABAC/entity filters must enforce every API request |
| Credential/token isolation | `app_id` claim, refresh-session binding, optional API policy | Independent signing keys, issuer, user namespace, OAuth accounts, or breach radius |
| Operations | Per-profile metrics and audit labels | Independent deploy, outage, migration, retention, incident, or admin lifecycle |

A shared deployment is appropriate when the frontends are presentations of one platform and intentionally share identity, security administration, data authorization, credentials, and operational fate. Separate deployments are required when one of those is meant to be independent. This boundary should be an explicit library design statement, not an implication left to examples.

## 10. Design options

### Option A — pass intent/context to URL builders

Change the built-in builders from token-only/no-argument callables to something like `Callable[[InviteMailIntent], str]`, `Callable[[ForgotPasswordMailIntent], str]`, and `Callable[[AccessGrantedMailIntent], str]`.

**Advantages**

- Smallest library change that fixes the immediate mail limitation.
- Reuses the context already present in the intent.
- Lets `diverse-data-api` and `DiverseAPI-postgres` avoid overriding all service methods.
- No SQL migration.

**Blast radius and migration**

- Breaking constructor/type change for hosts importing `DefaultAuthMailComposer`; the two audited direct consumers are the two Diverse backends.
- A compatibility adapter could inspect callable arity, but alpha status favors a clean break and explicit migration.
- qdarte's monkey-patched magic hook, OAuth, challenges, CORS, and frontend route contracts are unaffected.

**Security and guarantees**

- Can improve routing and branding if every host implements them correctly.
- Does not validate redirects, create registered destinations, bind OAuth state, or establish a common failure policy.
- Passing raw request/metadata to a URL builder can make open redirects easier if the library still provides no allowlist.

**Verdict:** useful internal API cleanup, but not an adequate architecture.

### Option B — host-declared app profiles plus a host resolver

Introduce immutable profiles at auth construction and an async resolver returning a profile key from a typed flow context. Profiles own registered origin(s), supported route templates, branding/template keys, redirect policy, and OAuth success/error paths. The resolver can use trusted host data; request-originated flows also carry a requested registered profile.

**Advantages**

- One concept spans mail, messaging, challenge verification, OAuth, and future verification.
- Fits one platform with N first-party interfaces.
- Keeps domain-specific audience policy in the host without letting it manufacture arbitrary URLs.
- No application SQL table is required.
- Supports root-based Diverse routing, role-based Créditos routing, and request-profile qdarte routing.

**Blast radius and migration**

- Additive for single-profile consumers if a default profile can be declared compactly.
- Existing mail builders/composers need adapters or a breaking cleanup.
- Challenge storage needs `app_id` and canonical return-target fields.
- OAuth state/cookie/route behavior must change.
- Each frontend needs a declared flow capability and route-contract test.

**Security and failure behavior**

- Registered destinations and server normalization materially improve redirect safety.
- A resolver must return a key, never a URL.
- Unknown/mismatched profile and resolver exceptions must fail closed internally. Anonymous request endpoints can retain opaque 202/204 responses while recording “token not delivered/profile unresolved.”
- A declared default is valid only for truly unambiguous contexts, never as an exception fallback.
- It provides no data or hard credential isolation unless separate enforcement is added.

**Verdict:** best long-term core, with the strengthening in §11.

### Option C — first-class persisted application/client registry

Add an SQL `Application`/OAuth-client-like model with CRUD, redirect URIs, branding, secrets/public-client type, grants, and perhaps user/application assignments.

**Advantages**

- Dynamic administration and auditability.
- Natural foundation for third-party clients, confidential clients, consent, client credentials, and per-client revocation.
- Could support stronger token policy when combined with issuer/resource-server enforcement.

**Blast radius and migration**

- New auth tables/migrations, admin APIs, permissions, bootstrap data, UI, caching, and operational ownership.
- Every existing deployment needs seeded application records before auth flows work.
- OAuth, mail, tokens, sessions, and all clients become coupled to a much larger abstraction.

**Security and failure behavior**

- A database registry is not automatically safer; writable redirect URIs and dynamic branding create a high-value control plane.
- Browser SPAs are public clients and cannot protect a client secret.
- Availability of the application table becomes part of every login/delivery flow.

**Architecture fit**

- Appropriate if OutlabsAuth intends to become an identity provider for independently managed/third-party applications.
- Too much machinery for the stated one-platform/first-party-frontends requirement and risks silently expanding into multi-product SaaS tenancy.

**Verdict:** do not build now. Design profile identifiers so a future persisted client registry can coexist without pretending they are the same concept.

### Option D — do nothing and bless host-side routing

Document the `AudienceRoutingAuthMailService` subclass pattern and leave other seams host-owned.

**Advantages**

- Zero library migration.
- Maximum host flexibility.

**Costs and failure modes**

- New flows are wrong by default until every host remembers to override them.
- Concurrency, fallback, database-query, route-shape, and branding policy are reimplemented.
- OAuth remains broken for same-provider multi-mount.
- Redirect safety remains frontend-dependent.
- SimpleRBAC and same-root multi-interface deployments have no recommended answer.

**Verdict:** reject. It directly contradicts the requirement that multiple first-party frontends be designed in rather than bolted on.

### Option E — separate deployments

This is not a competing library feature; it is the required boundary option. It has the largest operational cost but is the only option here that truly separates user namespaces, databases, issuers/keys, OAuth applications, administration, incidents, and release lifecycle.

**Verdict:** mandatory guidance for unrelated products; likely the correct destination for Referral Collection.

## 11. Recommendation

Adopt Option B, but make it a flow-wide contract rather than a mail-only profile selector.

### 11.1 Public shape

Define a stable, immutable, construction-time registry conceptually like:

```python
FrontendProfile(
    id="agent-portal",
    public_origins=("https://portal.meetdiverse.com",),
    brand=AuthBrand(...),
    routes=AuthFlowRoutes(
        login="/login",
        password_reset="/recovery/{token}",
        invite=None,  # unsupported until implemented
        magic_link="/auth/magic-link?token={token}",
        oauth_callback="/auth/oauth/callback",
    ),
    redirect_policy=RedirectPolicy(...),
)
```

The exact types may differ, but important invariants are:

- IDs are stable, unique, non-secret identifiers.
- Origins are absolute HTTPS outside explicitly local development.
- Routes are typed by flow and validated; unsupported is explicit.
- A profile, not the resolver, owns URL construction and branding.
- Host resolvers return only a registered ID.
- Registry configuration is immutable after startup.

### 11.2 Resolution inputs

Use a typed `FrontendResolutionContext` containing:

- flow kind;
- recipient/user ID and normalized recipient;
- `root_entity_id` when present;
- actor ID and target entity when relevant;
- requested profile ID for frontend-originated operations;
- normalized request origin/base as evidence, not authority;
- existing typed metadata;
- whether the operation is interactive, actor-initiated, or system-initiated.

The library should not load arbitrary host models. The host resolver may perform domain queries, preferably using a supplied request/UoW context rather than opening an unrelated session. Resolution should happen once; the resolved profile ID should be copied into the intent/challenge/state/audit record.

### 11.3 Flow rules

- **Invite/access granted:** actor/API command may name a profile; resolver validates it against the target user/entity. No supported route means fail before sending.
- **Forgot password:** request may name a registered profile. Resolver decides whether that profile is valid for the user. Outward response stays opaque; internal unresolved/delivery state is observable.
- **Reset confirmation:** use the profile bound to the reset token/request. If legacy/unbound, use a declared neutral security-notice profile with no navigation link, not an arbitrary brand fallback.
- **Magic/access code:** request names profile and relative return target. Validate, normalize, and persist both. Delivery receives the profile. Verification returns canonical `next_url`.
- **Phone verification:** no destination today, but profile still controls brand/channel template.
- **Email verification:** when implemented, use the same profile-bound challenge/intent path.
- **OAuth login/association:** one callback per host/provider. State and persisted binding include profile ID and a unique flow nonce; callback consumes state then resolves the registered success/error target.

### 11.4 Failure policy

Do not copy the `diverse-data-api` “exception means console” fallback.

- Unknown profile, unsupported flow, resolver error, or user/profile mismatch: fail closed internally and emit structured audit/metric data.
- Enumeration-resistant endpoints: still answer the caller generically, but do not silently send a wrong-brand link.
- Post-change security confirmation: a separately configured neutral, link-free fallback notification may be sent.
- Single-profile compatibility: a host may declare exactly one explicit default; exceptions do not turn into default selection.
- Cache only immutable profiles and safe resolver results; never mutate a shared composer per request.

### 11.5 Token/session semantics

Keep `aud` as the API/resource audience. Add the selected profile as `app_id` or OAuth-style `azp` in access/refresh session records and tokens, and bind refresh rotation to it. This provides traceability and enables an API to require an allowed app where justified.

Do not claim that this isolates bearer credentials. In a default shared-platform deployment, a bearer token accepted by the one API remains usable from any client that obtains it; CORS is not a bearer-token security boundary. If a host requires a token issued for one frontend never to authorize another frontend/API trust domain, it must configure explicit server-side app policy, distinct resource audiences/keys, or—preferably for unrelated products—separate deployments.

### 11.6 CORS and browser security

Expose the union of registered profile origins to the host and provide a startup validation/helper, but do not silently mutate FastAPI middleware. Hosts own proxy/CORS/cookie/CSP configuration. Documentation must state:

- profile redirect origins and CORS allowlists are separate controls that should agree;
- CORS does not stop non-browser token use;
- `Origin` is not a user/app authorization credential;
- production redirect targets require HTTPS;
- wildcard credentialed CORS is incompatible with this security model.

### 11.7 Migration order

1. Add profile types, resolver contract, and explicit single-profile default.
2. Change built-in mail builders/composer to consume resolved profile + full intent.
3. Add `profile_id` to mail/messaging intents and populate default metadata correctly.
4. Add profile/return-target binding to challenges; validate redirects and return `next_url`.
5. Make OAuth profile-aware through state, cookie, callback, and success/error resolution; add concurrent multi-profile tests.
6. Add `app_id`/`azp` to session/token issuance and refresh records.
7. Migrate each host only after its target frontend implements the declared flow routes.
8. Add cross-repository contract tests for every profile/flow combination.

The alpha version should prefer explicit breaking changes over callable-arity magic or indefinitely supporting raw unvalidated `redirect_url`.

## 12. Independent verdict

**Recommendation: app profiles + host resolver, agree in principle only if implemented as the single destination context for mail, challenges, OAuth, and session provenance.**

The central design constraint is that a profile is a presentation/client within one security realm, not a tenant. The library should make the supported separation strong and testable, and make the unsupported separation impossible to misunderstand.

---

# Part B — Critique of the first audit

Part A above was already written and hashed before I opened `docs/MULTI_FRONTEND_SUPPORT.md`, DD-059, or the related vault entries. The pre-quarantine snapshot was SHA-256 `344c88c30e04655ca9af5048129004fc96f0cc50de284f743843b7bfbdf00464`. The only later Part A edit converted four Markdown trailing-space line breaks to blank lines during the final whitespace check; no finding or recommendation text changed.

The first-audit material and my independent audit converge on the central diagnosis and broad profile/resolver direction. They diverge materially on failure policy, OAuth architecture, token semantics, the Referral Collection boundary, and how complete the proposed “profile” abstraction actually is.

## B1. Factual check

### Confirmed

The following load-bearing first-audit findings reproduced:

- The default mail builders are token-only/no-context even though the abstract composer receives complete intents (`outlabsAuth@main outlabs_auth/mail/composer.py:18-42,45-64`).
- `ComposedAuthMailService` owns one composer and dispatches every mail flow through it (`outlabsAuth@main outlabs_auth/mail/service.py:17-42`).
- The library drops `root_entity_id` when normalizing a recipient and fails to populate the default invite metadata keys (`outlabsAuth@main outlabs_auth/services/user.py:340-420,1607-1616`; `…/routers/auth.py:350-362,723-759`).
- `request_base_url` is the API origin, not a frontend origin, and normal forgot/invite hooks are called without `request` (`outlabsAuth@main outlabs_auth/services/user.py:1629-1633`; `…/routers/auth.py:360-362,758-759`). The first audit caught this more explicitly than Part A.
- Same-provider duplicate OAuth mounts have non-unique callback route names and provider/flow-only cookies (`outlabsAuth@main outlabs_auth/routers/oauth.py:150-183`; `…/routers/oauth_state_store.py:18-22,48-56`).
- `get_oauth_router` is not re-exported from `outlabs_auth.routers` (`outlabsAuth@main outlabs_auth/routers/__init__.py:7-35`). Part A missed this API-quality issue.
- The legacy Diverse backend selected reset/email-verification frontends per user, while the Postgres cutover uses one admin base (`DiverseAPI-postgres@main src/api/routes/users.py:602-618,1208-1214`; `DiverseAPI-postgres@postgres src/services/auth/transactional_mail.py:58-82`).
- The first audit correctly caught the RC `/auth/sign-in` versus shared `/auth/login` mismatch and absent RC invite page; Part A recorded the invite gap but missed the login-path mismatch (`diverse-referral-collection@main src/app/router/routes/`, explicit tree inspection).
- The first audit correctly identified that Agent Panel lacks an accept-invite route and that migration must not pretend otherwise (`agentPanel@postgres app/pages/`, explicit tree inspection).

### Incorrect, overstated, or not reproducible

1. **Duplicate OpenAPI operation IDs are not reproduced.** The first audit says same-provider duplicate mounts leave “duplicate OpenAPI operation ids” (`outlabsAuth@working-tree docs/MULTI_FRONTEND_SUPPORT.md:77`). A focused in-process probe against the audited library generated distinct IDs because the prefixes create distinct paths:

   - `authorize_ui_a_oauth_google_authorize_get`
   - `oauth_google_callback_ui_a_oauth_google_callback_get`
   - `authorize_ui_b_oauth_google_authorize_get`
   - `oauth_google_callback_ui_b_oauth_google_callback_get`

   Route reversal still resolved `oauth:google.callback` to the first mount, so the main defect is real; the OpenAPI subclaim is not.

2. **The qdarte invite/welcome evidence is not present at the state of record.** The first audit claims qdarte-intake sends OutlabsAuth invites to `{socios}/aceptar-invitacion?token=`, welcome mail to `{socios}/panel/login`, and hard-codes an invite TTL (`outlabsAuth@working-tree docs/MULTI_FRONTEND_SUPPORT.md:109-111`). Repository-wide searches at `qdarte-intake@main` found no `aceptar-invitacion`, library invitation-email implementation, or welcome-email implementation. What exists is:

   - a fixed-base OutlabsAuth magic-link hook (`qdarte-intake@main apps/api/qdarte_intake/auth_user_service.py:41-64,67-98`);
   - a separate custom owner-login magic-link system that builds `/l/owner/{token}` and mails it through a job (`qdarte-intake@main apps/api/qdarte_intake/routes/owner.py:93-123`; `…/workers/handlers.py:195-219`).

   The architectural lesson—qdarte owns parallel custom destination logic—is valid, but the specific claimed invite/welcome flows conflate planned or custom auth with the library integration.

3. **“Both Diverse panels ship `/verify-email/:token`” is wrong.** The statement appears at `outlabsAuth@working-tree docs/MULTI_FRONTEND_SUPPORT.md:69`. Agent Panel has `app/pages/verify-email/[token].vue`; no verify-email route was found anywhere in `DiverseAdminPanel@origin/postgres`. The larger finding that the library's email-verification delivery flow is incomplete remains correct.

4. **“Every URL-producing seam is fixed at wiring time” is an overstatement.** The first audit says this in its problem statement (`outlabsAuth@working-tree docs/MULTI_FRONTEND_SUPPORT.md:21`) and then correctly documents the per-request challenge seam later. Magic/access delivery receives the caller's `redirect_url` per request (`outlabsAuth@main outlabs_auth/services/user.py:185-245`). The actual diagnosis is inconsistency, not universal construction-time binding.

5. **The Diverse internal predicate cannot safely be only `root entity type → panel`.** The first audit recommends mirroring the frontend type blocklists (`outlabsAuth@working-tree docs/MULTI_FRONTEND_SUPPORT.md:102-107`). The migration creates both canonical `diverse-internal` and fallback `diverse-general` as `organization` roots (`DiverseAPI-postgres@postgres postgres_migration/scripts/migrate_outlabs_users.py:480-509`). Routing every `organization` to Admin Panel would classify fallback/unknown users as internal. The trusted predicate should use the canonical internal root slug, explicit external root types, and fail unresolved for null/general/unknown; superusers need an explicit home-profile policy.

6. **The proposal overstates “additive/no import-surface break” and “deletes per-send DB lookups.”** DD-059 calls profiles additive and says the workaround's queries disappear (`outlabsAuth@working-tree docs/DESIGN_DECISIONS.md:3748-3750`). Yet its Phase 1 requires loading root slug/type, which is not on the recipient and can require an entity query (`…/DESIGN_DECISIONS.md:3759`). Challenge persistence and refresh-session binding also require migrations if implemented correctly. More importantly, `DiverseAPI-postgres` does not use `ComposedAuthMailService`; it owns a custom `LoggedAuthMailService` (`DiverseAPI-postgres@postgres src/services/auth/transactional_mail.py:180-225,334-336`). Adding routing only to `ComposedAuthMailService` does not migrate that consumer without a rewrite or a lower-level reusable selector.

7. **The vault describes an adopted design while the decision record is Proposed.** DD-059 is explicitly “Proposed” (`outlabsAuth@working-tree docs/DESIGN_DECISIONS.md:3736-3740`), while `outlabsAuth Tasks.md:28-29` says “Design adopted” and the overview says the same at `outlabsAuth Overview.md:97`, even while noting the second audit is in flight. This is a governance/status inconsistency, not a code defect; reconciliation should occur before those entries are marked adopted.

## B2. Coverage check

### Material gaps in the first audit

1. **It saw the RC facade but missed that it sends no reset mail.** The audit notes `getattr(auth.hooks, ...)` and assumes service-layer routing will cover facade calls (`outlabsAuth@working-tree docs/MULTI_FRONTEND_SUPPORT.md:100`). At `d09eb10`, the custom endpoint generates and commits the reset token, then looks for `auth.hooks.on_after_forgot_password` (`diverse-data-api@d09eb10 src/diverse_data_api/domains/lead_audit_portal/api.py:207-219`). The library exposes `auth.user_service` hooks, not `auth.hooks`; no such property was found. The current flow silently sends nothing. App profiles inside `ComposedAuthMailService` do not repair a caller that never invokes that service.

2. **It did not trace challenge redirects through verification.** It correctly identifies the unvalidated pass-through, but stops at storage/delivery. The stored redirect is not returned by magic/access verification; both endpoints return only `LoginResponse` tokens (`outlabsAuth@main outlabs_auth/routers/auth.py:473-509,616-676`). OutlabsAuthUI follows its own URL-query copy (`OutlabsAuthUI@main src/features/auth/components/magic-link-page.tsx:110-124`; `…/access-code-page.tsx:300-309`). Merely “dropping” a disallowed redirect before storage, as Phase 3 proposes, leaves two inconsistent copies and no server-owned post-auth destination.

3. **It did not inventory the unused access-granted production path.** The helper and intent exist (`outlabsAuth@main outlabs_auth/services/user.py:404-421`), but no library production call site was found. A proposal that promises routing for every mail flow should either wire the lifecycle or label it host-only.

4. **OAuth account association is listed but not carried through the repair.** `oauth_associate.py` has the same route-name, fixed-success-URL, and provider/flow cookie problem (`outlabsAuth@main outlabs_auth/routers/oauth_associate.py:65-104,121-143,153-182,258-263,316-323`). DD-059 Phase 3 discusses only `get_oauth_router` and a login double-mount test (`outlabsAuth@working-tree docs/DESIGN_DECISIONS.md:3761`).

5. **It missed the global access/refresh-token semantics in the current library.** One process-wide `jwt_audience` means the same bearer is accepted across frontends on the mount (`outlabsAuth@main outlabs_auth/core/config.py:55-61`). This is essential to the honest separation table. The first audit introduces Phase 4 later, but its initial guarantees blur data separation, sign-in routing, and credentials.

6. **It did not test the Créditos topology against its resolver helpers.** The planned platform → franchise → client hierarchy means root identity/type can be identical across admin and customer users (`creditos-del-norte-api@main README.md:16-18`). That future adopter may require role/membership/home-profile policy, so a pure resolver over pre-enriched root fields is insufficient.

7. **The AppProfile type is mail-first rather than flow-wide.** Its fields are app name, base URL, mail paths, and support email (`outlabsAuth@working-tree docs/MULTI_FRONTEND_SUPPORT.md:173-198`). Challenge routing is left to the host, OAuth is repaired separately through router prefixes, and session provenance arrives in Phase 4. That is a mail profile with later attachments, not yet the single designed-in frontend concept the architecture intent asks for.

### Useful first-audit findings Part A missed

For reconciliation, the first audit improved the independent pass in these places:

- `request_base_url` is not just insufficient; normal forgot/invite routers fail to thread `request`, so it is `None` on the key mail paths (`outlabsAuth@working-tree docs/MULTI_FRONTEND_SUPPORT.md:58`).
- `get_oauth_router` is missing from the public router exports (`…/MULTI_FRONTEND_SUPPORT.md:70`).
- RC's login route is `/auth/sign-in`, not the workaround's `/auth/login` (`…/MULTI_FRONTEND_SUPPORT.md:98`).
- Agent Panel does have a legacy `/verify-email/[token]` page even though the library has no corresponding delivery flow; my Part A stopped at the missing library seam.
- The first audit more explicitly connected invite ordering to root pinning: membership is added before `on_after_invite`, so an entity-scoped invite can have a root by send time (`outlabsAuth@main outlabs_auth/routers/auth.py:738-759`).

## B3. Design verdict

### App profiles + host resolver: right core, incomplete shape

**Verdict: agree with changes.**

The profile/resolver combination is the right core for static first-party frontends. A SQL OAuth-client registry would add dynamic administration, migration, and security-control-plane burden that none of the current consumers needs. Root entity must remain resolver input rather than library semantics.

However, DD-059's current `AppProfile` is too mail-centric. The profile should be a flow-wide `FrontendProfile` from the first release, with:

- one or more registered public origins;
- typed support for invite, reset, login, magic, access-code, email-verification, OAuth success/error, and association routes;
- explicit unsupported-flow values;
- branding/template/sender policy;
- redirect-path normalization policy;
- OAuth/state mount identity;
- session `app_id`/authorized-party identity.

Mail composer selection should consume this resolved object, not define the abstraction. Challenge and OAuth code should consume the same resolution result rather than merely being told to reuse a host function.

The resolver should be allowed to be async. Diverse can resolve cheaply from root context, but Créditos may need membership/role scope, and a general host policy should not be forced into preloading every possible domain fact onto public library intents. Resolution should happen once in the existing request/UoW where possible, then persist the profile key.

### Resolver failure: disagree with default fallback

The first audit explicitly endorses “resolver failure → default profile” (`outlabsAuth@working-tree docs/MULTI_FRONTEND_SUPPORT.md:91,97,201`; `…/DESIGN_DECISIONS.md:3750,3760`). I disagree.

A database or resolver failure is not evidence that the user belongs to the default app. Falling back creates valid, wrong-brand links and makes outages corrupt routing silently. For password-reset and magic-link request endpoints, preserve the opaque outward 204/202 response but fail the internal delivery, log/metric the reason, and do not send. For post-change security notices, a separately declared neutral link-free notification is a reasonable fallback. A default profile is valid only when the context is genuinely unambiguous, not when classification throws.

### Redirect hardening: agree with stronger changes

An optional `allowed_redirect_url_origins` whose default preserves arbitrary strings and whose rejection behavior is “drop and log” is too weak for an alpha breaking-change window (`outlabsAuth@working-tree docs/MULTI_FRONTEND_SUPPORT.md:205-209`). Profiles should accept a relative return path or normalize an absolute URL into the selected profile's allowed origins at request time. Unknown profile or invalid target should make delivery fail internally. Persist profile + canonical target, and return canonical `next_url` after verification.

### OAuth: disagree with one-router-per-frontend as the long-term model

Prefix-aware names fix reverse routing but not the provider/flow cookie collision that the first audit itself identified (`outlabsAuth@working-tree docs/MULTI_FRONTEND_SUPPORT.md:76-79,205-209`). Explicit redirect URLs also do not bind a profile into state. The recommended test can pass sequentially while concurrent same-provider flows still clobber each other.

Prefer one provider callback per host/provider:

1. authorize receives a registered profile ID;
2. signed and persisted state binds profile ID plus a unique nonce;
3. cookie/state identity includes profile/mount or otherwise supports concurrent flows;
4. callback consumes state and selects the registered success/error destination.

If duplicate physical mounts remain supported, the same fixes must apply to login **and association**, and tests must cover concurrency, reverse routing, cookies, state, success, and error.

### Token audience and sign-in gating

**Do not use a per-profile JWT `aud` by default.** In JWT/OAuth semantics, `aud` identifies the resource/API that accepts the token; the frontend/public client is the authorized party. One FastAPI resource server can correctly have one audience while several frontends initiate sessions.

**Do add `app_id` or OAuth-style `azp` now**, bind it to the refresh/session record, propagate it through every mint/rotation path, and offer mandatory dependency policy for app-specific endpoint families. Alpha is the cheap time to establish provenance.

The Phase-4 claim that mint-time gating moves the frontend guards fully into the library is too strong (`outlabsAuth@working-tree docs/DESIGN_DECISIONS.md:3763,3770`). A public SPA cannot authenticate its `app` selector. An agent can request `app=portal`, receive a valid shared-API token, and present that token outside the portal. If resource-side client checks are optional, the token remains usable anywhere the shared API accepts it. The proposal honestly acknowledges public-client limitations in the long form (`outlabsAuth@working-tree docs/MULTI_FRONTEND_SUPPORT.md:218-219`) but overstates the consequence in DD-059.

There are three honest levels:

1. **Routing/UX:** profile selection and frontend guards. No credential isolation.
2. **Shared-platform policy:** `azp/app_id` bound to the session plus mandatory server checks on app-specific APIs. Still one issuer/key/user realm.
3. **Credential-domain isolation:** distinct audience/issuer/key/user or OAuth client trust boundary. Use separate deployments or a deliberate identity-provider architecture.

If “agent credentials must never work in the admin security domain” is literal rather than UX shorthand, level 2 must be fully enforced or the two domains need separate deployments/BFFs. A token claim with opt-in enforcement is insufficient.

### Platform/product boundary and Referral Collection

The written rule “one platform, N frontends; unrelated products get separate deployments” is correct (`outlabsAuth@working-tree docs/DESIGN_DECISIONS.md:3764`). Referral Collection is placed on the wrong side of it.

The host source calls it “a different product” and gives it a separate customer-facing destination (`diverse-data-api@d09eb10 src/diverse_data_api/iam/transactional_mail.py:34-38`; `…/platform/config.py:64-68`). It has bespoke signup/sign-in/reset endpoints and no shared invite UI. Treating it as the “outer edge” of supported profiles (`outlabsAuth@working-tree docs/MULTI_FRONTEND_SUPPORT.md:35`) weakens the boundary exactly where it should be clearest.

My recommendation is a separate auth deployment for Referral Collection unless the maintainer explicitly decides that RC is part of one Diverse identity/security/operations realm and accepts the shared keys, users, database, admin plane, OAuth identity, and incident radius. A temporary profile can mitigate mail routing during migration, but it should be labeled transitional, not the flagship validation of the model.

## B4. Migration realism

### `diverse-data-api`

**Proposed migration as written: does not work.**

- The actual RC reset request never reaches `user_service` or the composed mail service because it probes nonexistent `auth.hooks` (`diverse-data-api@d09eb10 src/diverse_data_api/domains/lead_audit_portal/api.py:207-219`).
- RC has no accept-invite route and uses `/auth/sign-in`, which the first audit does catch.
- RC reset expects `?token=` and calls the custom portal reset endpoint (`diverse-referral-collection@main src/app/router/routes/auth.reset-password.tsx:7-22`; `…/features/auth/api/reset-password.ts:18-25`).
- Tracked CORS omits the RC production/staging origin (`diverse-data-api@d09eb10 .env.example:86-89`).
- If the long-term boundary is honored, the target should be separate deployment rather than deleting the workaround in favor of a permanent shared profile.

### `DiverseAPI-postgres`

**Proposed migration: viable only with additional work.**

- `route_by_root_entity_type` needs canonical internal-slug and unresolved-user handling; type alone misclassifies `diverse-general`.
- `LoggedAuthMailService` is custom and does not receive the proposed new `ComposedAuthMailService` selector automatically (`DiverseAPI-postgres@postgres src/services/auth/transactional_mail.py:180-225`).
- Agent reset links can work at `/recovery/{token}`, but agent invites cannot until Agent Panel adds a route or setup deliberately remains on Admin Panel.
- Superusers, null roots, and unknown/fallback roots need an explicit home-profile policy.
- Mail routing and sign-in authorization should share a classification result, but not necessarily one oversimplified root-type function.

### `qdarte-intake`

**“None required” is compatible but does not validate the design.**

Leaving the host's fixed-base monkey patch and separate custom owner magic-link system untouched means the promised first-class multi-frontend concept is not actually adopted there (`qdarte-intake@main apps/api/qdarte_intake/auth.py:92-103`; `…/auth_user_service.py:41-64`; `…/routes/owner.py:93-123`). `socios.qdarte.com` also lacks the OutlabsAuthUI magic-link route today. Treat qdarte as a later migration/contract-test case, not proof that the Phase-2 mail profiles cover three origins.

### `creditos-del-norte-api`

**The greenfield label is fair; the suggested root helpers are not enough.**

Its platform → franchise → client hierarchy can put several user classes under one root (`creditos-del-norte-api@main README.md:16-18`). Before adding a customer portal profile, define whether role, scoped membership, explicit home app, or request context controls routing. This is a good acceptance test for an async general resolver.

### Frontend contract migration

Profiles must be validated against frontend capabilities before host rollout:

- query versus path token placement;
- invite/reset/magic/OAuth routes actually present;
- backend endpoint namespace used by the page;
- post-auth return contract;
- CORS origin and CSP/cookie assumptions.

Static route declarations plus cross-repository contract fixtures are more realistic than assuming common paths. The first audit's testing obligations move in this direction, but should include the RC facade, OAuth association/concurrency, canonical `next_url`, unknown/null resolver cases, and every custom mail service.

## B5. Verdict per major decision point

| Decision point | Verdict | Required change |
|---|---|---|
| Multi-frontend is a first-class one-platform concept | **Agree** | Document the shared identity/key/data/operations boundary prominently |
| Unrelated products use separate deployments | **Agree** | Move Referral Collection to the separate-deployment side or label shared use transitional |
| Static profiles instead of SQL client registry now | **Agree** | Use stable IDs and leave a clean future bridge to persisted clients |
| Host-supplied resolver | **Agree with changes** | Async-capable, returns registered key only, runs once with trusted context |
| Root entity is input, not universal key | **Agree** | Do not assume root fields alone are sufficient |
| Enrich intents | **Agree with changes** | Add resolved `profile_id`; avoid eagerly copying an open-ended host domain model into every intent |
| Route templates per profile | **Agree** | Make them typed across every auth flow, with unsupported routes explicit |
| Profile selection inside only `ComposedAuthMailService` | **Disagree** | Put resolution below/around all mail services so custom logged services can reuse it |
| Resolver exception/unknown → default | **Disagree** | Fail closed internally; generic outward response; optional neutral link-free notice |
| Optional raw redirect allowlist | **Agree with substantial changes** | Registered profile + canonical relative/allowlisted target; persist and return `next_url` |
| One OAuth router per frontend | **Disagree as long-term core** | One provider callback with profile-bound state, or fully mount-scoped routes/cookies/state including association |
| Add app/client claim now | **Agree** | Prefer `app_id`/`azp`, bind refresh/session, define mandatory enforcement semantics |
| Per-profile JWT audience now | **Disagree by default** | Keep API `aud`; use authorized-party claim. Separate issuer/audience/deployment when hard credential isolation is required |
| Audience-gated token minting | **Agree with changes** | Do not claim security separation without mandatory resource-side checks; public app ID is not authenticated |
| Preserve all hook signatures | **Agree for compatibility** | Also define one canonical service invocation path so custom endpoints cannot probe the wrong object |
| Four additive phases | **Disagree with characterization** | Treat challenge/session schema and consumer rewiring as explicit migrations; prefer one coherent vertical slice |

## B6. Top three risks in the proposal as written

1. **Wrong-profile fallback becomes standardized behavior.** Resolver/database errors would silently produce valid links under the default app, trading visible delivery failure for incorrect security messaging.
2. **OAuth is declared fixed while state remains cross-profile.** Prefix-aware route names do not prevent provider/flow cookie clobbering, do not bind profile in state, and omit association.
3. **Phase 4 can create false confidence in credential separation.** An unauthenticated public-client selector plus a token claim with optional resource checks does not stop an allowed-profile token from being used against the shared API elsewhere.

## B7. Reconciled recommendation

Keep the first audit's central choice—host-declared profiles plus a host resolver—but revise DD-059 before implementation:

1. Define one flow-wide immutable `FrontendProfile`, not a mail profile later reused by convention.
2. Resolve once to a registered key with an async-capable trusted resolver; persist that key through intent, challenge, OAuth state, session, and audit.
3. Fail closed on unresolved/error states; never default because classification failed.
4. Replace raw redirect pass-through with profile-bound canonical return targets and verification-time `next_url`.
5. Use profile-bound single-callback OAuth state, including association and concurrent-flow tests.
6. Add `app_id`/`azp` session provenance now, while keeping API `aud` semantically correct.
7. State that profiles provide routing/branding/origin policy, not tenant or credential isolation.
8. Fix/retire the concrete host paths before calling migrations complete: RC's dead hook call, absent invite routes, Diverse's custom logged service, canonical internal predicate, and CORS gaps.
9. Put Referral Collection on a separate deployment unless the maintainer explicitly reclassifies it as one Diverse security realm.

With those changes, the app-profile/resolver design is the right long-term core. Without them, DD-059 is still a mail-routing improvement with OAuth and token-policy bolt-ons, rather than the rock-solid multi-frontend model requested.
