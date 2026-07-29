# Second Audit Brief — Multi-Frontend Support in outlabs-auth

**Date**: 2026-07-29
**You are**: an independent second auditor. A first audit and design proposal already exist in this repo. Your value is independence: re-derive the facts yourself, form your own recommendation, and only then read and attack the existing design. Findings from both audits will be reconciled by the maintainer before anything is implemented.

**Quarantine rule — read this first.** Do NOT open `docs/MULTI_FRONTEND_SUPPORT.md`, the DD-059 entry at the end of `docs/DESIGN_DECISIONS.md`, or the DD-059-related entries in the vault (`~/Documents/lifeOS/Projects/Business/Outlabs/outlabsAuth/`) until you have finished Part A and written your own findings and recommendation. Part B is where you read them. Everything else in `docs/` is fair game and predates this work.

## Mission

Audit how the `outlabs-auth` library (this repo, PyPI `outlabs-auth`, 0.1.0a24, alpha) supports — or fails to support — **multiple frontends served by one FastAPI host off a single library mount**, across every seam where the library decides or delegates "where does this user land": transactional mail (invite, password reset, confirmations, access granted), magic links, access codes/OTP, OAuth redirects, and anything else you find. Then design the fix, with options and trade-offs, and deliver a recommendation.

## Architecture intent (from the maintainer — this frames the whole exercise)

- The system was **not** built to be truly multi-tenant in the multi-platform sense — running several unrelated SaaS products off one deployment is **not the goal** and should not silently become the goal.
- What IS required, first-class and long-term: **multiple first-party frontends running off the same system**. This must be a designed-in concept — rock solid, not an afterthought, not a bolt-on, not a per-host hack.
- "We can get some separation there, but it needs to be done in the right way." Part of your job is to say precisely **what kinds of separation** (link/landing routing, branding, data isolation, credential/token isolation, CORS/origin handling) a multi-frontend concept should and should not promise, and where the honest boundary is beyond which the answer must be "separate deployments".
- Hard requirement (Diverse, stated by the maintainer): agent users and internal staff share one user table but belong to separate organisations, and **a frontend that does not serve a user's domain must be able to reject that user's sign-in** — enforced server-side, not by frontend JavaScript. Both modes must be expressible: partitioned frontends that reject off-audience sign-ins, and shared frontends serving the same users interchangeably ("it needs to work both ways"). Treat the current state of this enforcement across the stacks as an audit target in its own right.
- Weigh everything for the long term. Backward compatibility matters less than getting the shape right: the library is alpha (0.1.0aN) and breaking changes are still cheap. Flag where the *cheapest* fix and the *right* fix diverge.

## Repos and coordinates

All under `~/Documents/projects/`. **Ground rules: read-only everywhere.** Do not checkout, switch branches, edit, or commit in any repo. `git fetch` is allowed. Inspect non-checked-out branches with `git show origin/<branch>:<path>` and `git ls-tree`. Several repos have untracked `.env` files containing live credentials — never quote environment values in your report.

| Repo | State of record | Notes |
|---|---|---|
| `outlabsAuth` | `main` @ a979661 | The library. Working tree has unrelated modified docs plus the quarantined first-audit files — ignore both until Part B. |
| `diverse-data-api` | `origin/main` @ d09eb10 | Checked out on an unrelated fix branch — audit `origin/main` via `git show` where they differ. One mount at `/iam`, two frontends: the OutlabsAuthUI admin console (auth-data.meetdiverse.com) and Referral Collection (staging.referralcollection.com). Commit d09eb10 ("Fix dead reset links and route auth mail per product") is the host-side workaround and a primary exhibit. |
| `DiverseAPI-postgres` | branch `postgres` @ e6d652f6 | Pins outlabs-auth 0.1.0a23. One mount, two frontends: DiverseAdminPanel (console) + agentPanel (agent portal). Also compare the **legacy `main` branch's** construction of auth-mail links (`git show main:src/api/routes/users.py`, search `AGENT_PORTAL_URL`) against the `postgres` branch's mail wiring — form your own view of what the cutover changed. |
| `agentPanel` | branch `postgres` | The `/iam` integration exists only on this branch. Note which auth routes exist, and how reset/invite tokens are read (path segment vs query). |
| `DiverseAdminPanel` | `origin/postgres` (local checkout is on `staging`) | Same questions. Use `git show origin/postgres:<path>`. |
| `diverse-referral-collection` | `main` | The Referral Collection SPA. Same questions; also note which backend endpoints it actually calls. |
| `OutlabsAuthUI` | `main` | The shared admin console: one build, many backends. Understand its deploy-time configuration model. |
| `qdarteAPI`, `qdarte-intake` | `main` | Additional consumers. qdarte-intake serves three frontend origins (subir/socios/admin.qdarte.com) — study how it builds auth-flow URLs and what it does or does not use from the library's mail seam. qdarteAPI is a minimal consumer. |
| `creditos-del-norte-api` | `main` | EnterpriseRBAC "franchise multi-tenant" consumer, early stage. Assess as a future multi-frontend adopter. |

## Part A — independent audit

### A1. Claims to verify (starting hypotheses — do not trust them, re-derive; they may be wrong or incomplete)

1. There is no first-class application/client/frontend concept: `AuthConfig` (`outlabs_auth/core/config.py`) has no frontend URL, no app registry, no per-client redirect allowlist; there is no `application` SQL model.
2. The mail seam is `outlabs_auth/mail/composer.py`: `DefaultAuthMailComposer` takes `TokenUrlBuilder = Callable[[str], str]` builders that receive ONLY the token, so a link cannot vary per recipient. Check what context the composer interface itself receives, and what context the library actually has in hand at each point where it builds a mail intent (`outlabs_auth/services/user.py`) versus what it puts on the intent.
3. `outlabs_auth/mail/service.py` `ComposedAuthMailService` holds one composer for all send methods, so per-user routing means overriding all of them.
4. The OAuth seam (`outlabs_auth/routers/oauth.py` `get_oauth_router`) fixes `success_redirect_url` / `error_redirect_url` at construction. Determine whether mounting the router more than once (same provider, different prefixes) is actually supported: examine route naming, `url_for` usage, the state-cookie scheme (`routers/oauth_state_store.py`), OpenAPI ids, and what the test suite does and does not cover.
5. `outlabs_auth/services/membership.py` `add_member` pins `user.root_entity_id` on first membership and rejects cross-tree membership. Work out what this means for multi-frontend routing: for each audited host, determine what the *actual* audience discriminator would have to be (root entity identity? something else?), including hosts whose users have no root entity at all (SimpleRBAC presets; invitees created without an entity).

### A2. Additional questions to answer with evidence

- Inventory EVERY seam that decides or delegates a user-facing destination, including ones the list above omits (email verification, the challenge/messaging seam in `outlabs_auth/messaging/` + `services/user.py`, hooks, anything else). For each: who owns the decision (library/host), when it binds (construction / process / per-request), and what context is available at the binding point.
- The magic-link and access-code request schemas (`outlabs_auth/schemas/auth.py`) accept a `redirect_url` from the caller. Trace its full lifecycle (validation? storage? where it resurfaces?) and assess the security posture of that parameter as-is, and under any design you propose.
- The default composer reads several `intent.metadata` keys (e.g. entity/inviter/role context). Establish which of them any library call site actually populates.
- Establish the token-placement conventions (query string vs path segment) actually expected by each of the five frontends, and whether the library states any contract about it. Cross-check against the history of dead-link bugs in the hosts (commit messages are evidence).
- For the DiverseAPI-postgres stack specifically: map the entity topology (which roots admins vs agents live under — seeds, provisioning code, and the frontends' own post-login guards are all evidence) and state precisely what server-side predicate would route mail to the correct panel.
- CORS/origin configuration across hosts: does each host's allowlist actually cover its frontends?
- Enumerate every path that mints platform credentials (password login, passwordless verifies, OAuth callback, invite acceptance, refresh, anything else) and assess: where a per-frontend sign-in policy could be enforced, what can and cannot be guaranteed for public SPA clients (no client secrets exist), and what each frontend does about off-audience logins today (their post-login guards are evidence).
- Anything you find that the questions above did not anticipate. Depart from this list wherever the evidence leads; if you conclude one of this brief's own framing assumptions is wrong, say so explicitly.

### A3. Design options (before reading Part B material)

Produce your own option set with real trade-offs — at minimum: (a) passing intent/context to the URL builders; (b) a per-audience app-profile + host-supplied resolver arrangement; (c) a first-class application/client registry, OAuth-provider style; (d) do nothing and bless the host-side pattern. For each: blast radius across the audited consumers (use their actual import surfaces), migration story, security posture (especially `redirect_url` and any client-supplied signal), long-term fit with the architecture intent above, and failure modes when the audience decision itself errors. State which separation guarantees (routing / branding / data / credential) each option does and does not provide. Then commit to a recommendation.

## Part B — critique of the first audit (only after Part A is written)

Now read `docs/MULTI_FRONTEND_SUPPORT.md` and DD-059 in `docs/DESIGN_DECISIONS.md`. Deliver a structured critique:

1. **Factual check**: any claim in the first audit that is wrong, overstated, or that you could not reproduce (cite your evidence).
2. **Coverage check**: seams, hosts, or failure modes the first audit missed — and anything YOUR Part A missed that it caught (say so honestly; the reconciliation needs both).
3. **Design verdict**: is app-profiles + host resolver the right long-term core, or does the stated architecture intent justify a stronger concept? Is anything in the phased plan an afterthought/bolt-on in disguise? Is the "one platform, N frontends; products get separate deployments" boundary drawn in the right place — and is the Referral Collection case on the right side of it? Judge the audience-gated authentication design specifically: is the mint-time enforcement model sound (spoofing/trust model for public SPAs, refresh, invite auto-login, coverage of every minting path), and is "accepted audiences per profile" the right shape for both partitioned and shared modes?
4. **Migration realism**: would the proposed consumer migrations actually work as described, given what you saw in the hosts (including frontend route gaps)?
5. **Verdict per major decision point**: agree / agree-with-changes / disagree, with reasons — plus your top 3 risks in the proposal as written.

## Deliverable

One Markdown report: your seam inventory (table), your findings with `repo@branch file:line` evidence for every claim (verbatim snippets for load-bearing ones, explicit "not found" statements where relevant), your option analysis and recommendation, then the Part B critique. Write it to `~/Documents/projects/outlabsAuth/docs/MULTI_FRONTEND_SECOND_AUDIT.md` if your runtime can write files; otherwise return it as text. Do not modify anything else. Audit + design + document only — do NOT implement.
