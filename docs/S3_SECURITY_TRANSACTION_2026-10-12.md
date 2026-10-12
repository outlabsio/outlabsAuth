# Explicit host security-containment transactions

Date: 2026-10-12. Unreleased a38 runtime `4617817`; Auth head remains
`20261012_0031`. This receipt extends the
[invitation qualification](S3_INVITATION_RECEIPT_2026-10-12.md). Public a37 remains
the published consumer baseline. No tag, package publication or deployment occurs.

## Contract

Refresh-token reuse must roll back unrelated caller effects and durably revoke
the copied family/replacement proofs before returning refusal. The default
independent configured-engine transaction remains unchanged. A host using an
external transaction journal cannot safely permit an arbitrary raw SDK session
to bypass that journal, or report containment when the SQL fence rejects it.

`AuthService.security_transaction_factory` is an optional callable taking the
rolled-back caller `AsyncSession` and returning an async context manager yielding
the containment session. It can be passed to the service constructor or installed
on `auth.auth_service` after host initialization. The SDK locks the subject,
revokes tokens/advances the durable epoch and calls `commit()` on that yielded
session before raising the reuse refusal. Factory, commit and cancellation
failures propagate. The host owns admission, rollback, durable acknowledgement,
pool capacity and recovery. Reusing an admitted request session is acceptable
only after its failed transaction rolls back and its containment commit is a
real, independently acknowledged transaction.

The core library introduces no consumer, journal schema, startup migration,
automatic retry or default factory override. Hosts must qualify their actual
mounted replay path, unrelated-write rollback, replacement access/refresh denial,
uncertain commit behavior and recovery generation. The implementer contract is
in [Sessions and Audit](../docs-library/05-Sessions-and-Audit.md).

## Source and artifact qualification

- Full PostgreSQL + required real-Redis source invocation: **1,651 passed**,
  one genuine-public-a37 interpreter gate skipped. Supplying that interpreter
  then passes its actual upgrade/immutability test: **1,652 distinct tests covered**.
- Required independent Redis selection: **102 passed**, no skips.
- The changed replay file has **18 passing cases**, including default and supplied
  factory paths with rollback of an unrelated pending permission definition.
- Fresh noneditable wheel and sdist environments outside the source checkout:
  **103 tests each**, no failures/errors/skips, plus each lifecycle-constructor
  qualification. Their suite includes genuine a37 upgrade and the new security
  cases. All **243 installed package files** match the qualified wheel bytes in
  the candidate installation.
- Full Ruff, changed-file Black and Auth-service MyPy pass. Full Black has 132
  unrelated existing files requiring formatting; they are not changed here.
- Handbook `23d92dd`: lint, typecheck and static build pass.

Exact wheel SHA-256:
`3336501b7d9dc28e8634d26059225e64e2fe3e57b7b6608ab7257539b30cc170`.
Exact sdist SHA-256:
`ac08cd4906a301589437a9b71dc51c4249ecf692e4b0da6e023ed4ac051a4954`.
Both artifacts are local candidates, not public package or consumer-adoption proof.

## Handoff

Review this optional transaction seam with the complete a38 change set before
publication. Consumers retain their separate migration, exact-artifact admission,
restricted writer, cache, delivery and recovery acceptance gates. The host-side
complete-image storage/performance protocol is not supplied or certified by this
library. Same-email identities remain deferred as recorded in the plan; this
change does not alter tenant identity or staff delegation semantics.
