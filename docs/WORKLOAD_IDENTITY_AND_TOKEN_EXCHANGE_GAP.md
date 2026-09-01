# Workload Identity and Token Exchange Gap

**Status:** Open design gap; recommended direction, not yet an accepted API or release commitment

**Recorded:** 2026-09-01

**Companion TaskQ gap:** [Workload Credential Provider Gap](https://github.com/outlabsio/outlabs-taskq/blob/main/docs/Workload%20Credential%20Provider%20Gap.md)

## Why this is a library gap

OutlabsAuth can authenticate machine callers with integration-principal API keys or stateless
service JWTs. It does not yet give an unattended workload a durable identity that can exchange its
own proof for short-lived access tokens. A service JWT is therefore a pre-minted bearer secret: it
eventually expires, but the workload cannot renew it. Making it very long-lived only moves the
failure farther away while increasing the exposure window.

This became operationally visible in an unattended QDarte worker run. The scheduler remained able
to enqueue work while the worker's service JWT had expired, so work accumulated without a valid
consumer. The consumer now has explicit containment and failure checks, but token rotation in a
consumer is not upstream closure.

## Current credential choices and their limits

| Credential | Useful property | Limitation for unattended workers |
|---|---|---|
| Integration-principal API key | Durable, individually revocable, scoped, optional expiry | Static bearer secret; long-lived secret theft remains useful until revocation; verification and accounting use the API-key runtime path |
| Service JWT | Stateless verification and naturally bounded lifetime | Pre-minted token cannot renew itself; no individual early revocation unless additional state is enabled; embedded claims remain effective until expiry |

Neither is the ideal complete lifecycle. API keys remain a valid compatibility and bootstrap mode,
but "never expires" must not become the default answer to unattended execution.

## Recommended target architecture

Reuse Enterprise integration principals as first-class workload principals, and add an asymmetric
workload credential plus token-exchange flow:

1. An operator creates or selects an integration principal and grants only its required scopes.
2. The workload generates a private/public key pair. The private key stays in the platform's secret
   boundary (for example Keychain/Secure Enclave, KMS, or an equivalent workload secret store).
3. OutlabsAuth stores the public key, key identifier, lifecycle state, and allowed token policy.
4. The workload signs a short-lived client assertion containing issuer, audience, issued/expiry
   times, and a unique replay identifier.
5. A dedicated token endpoint validates the assertion and issues a short-lived access JWT, normally
   5–15 minutes, bounded to the principal's current grants, audience, and environment.
6. The workload refreshes before expiry. Multiple active public keys permit zero-downtime rotation.
7. Disabling the principal or key prevents new issuance immediately; already-issued access tokens
   expire quickly. Higher-assurance deployments may additionally use the existing blacklist or an
   equivalent revocation check.

The durable identity is the integration principal. Public keys prove possession. Access JWTs are
short-lived runtime capabilities, not configuration copied into a worker environment.

## Required lifecycle and security semantics

- Token exchange is explicitly enabled per deployment and fails closed.
- Assertions are audience-bound, very short-lived, replay-protected, and subject to clock-skew
  bounds.
- Issued JWTs carry a stable principal identifier, key identifier, audience, environment, token
  type, and the minimum effective scopes needed by the workload.
- Issuance re-evaluates the principal/key state and current grants; a stored assertion cannot
  preserve revoked authority.
- A principal may have overlapping active keys, with create, activate, retire, revoke, and
  last-used metadata supporting safe rotation.
- Private key material is never accepted for storage by OutlabsAuth and is never logged.
- Exchange successes and failures are auditable without logging assertions or access tokens.
- Rate limits, replay storage, readiness behavior, and unavailable-auth behavior are explicit.
- Human users, personal API keys, browser sessions, and ordinary OAuth flows remain separate from
  workload identity.

## Library boundary

OutlabsAuth owns principal/key enrollment, assertion validation, token issuance, grant evaluation,
revocation semantics, and audit. It must not own a worker loop or TaskQ-specific refresh policy.

TaskQ owns an optional dynamic credential-provider seam for its HTTP clients and workers. A host
may implement that seam with OutlabsAuth token exchange, another identity provider, or a platform
native identity mechanism. Direct-SQL TaskQ deployments remain outside this HTTP credential flow.

## Acceptance criteria before calling the gap closed

- A documented workload-principal and public-key lifecycle exists with explicit migration and
  rollback behavior.
- A workload can run indefinitely without a human copying fresh bearer tokens into configuration.
- Access tokens are short-lived and renewed automatically from proof of possession.
- Principal disable, grant removal, key revocation, key overlap, replay rejection, clock skew, and
  auth-service unavailability have deterministic tested behavior.
- Token audience and environment binding prevent cross-service and cross-environment reuse.
- Exchange and runtime authentication are observable and alertable without exposing secrets.
- At least one real unattended consumer proves renewal, forced rotation, revocation, restart, and
  prolonged auth-outage behavior before broad adoption.

## Non-goals for the first design

- Silently converting existing API keys or service JWTs.
- Making OutlabsAuth a general cloud workload-identity federation product.
- Coupling the token endpoint to TaskQ queue names or worker implementation details.
- Treating consumer-side token rotation or a very long JWT lifetime as architectural completion.
