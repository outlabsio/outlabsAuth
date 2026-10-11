# Independent a37 publication review

**Date:** 2026-10-11. **PR:** [#33](https://github.com/outlabsio/outlabsAuth/pull/33).
Three independent reviewers examined authority caching, account/session/OAuth
security, and migration/recovery/publication. The initial review blocked release;
the following reproduced gaps were corrected before final local qualification.

| Finding | Correction and retained proof |
| --- | --- |
| A retained ORM user bypassed epoch revocation in both bearer validators | Both authority reads populate existing user state, without a second validator query. |
| A stale profile writer changed a deleted account's reserved email | Profile mutation locks and refreshes the user before checking deletion or changing identifiers. |
| Login/recovery challenges survived deletion and restore | Both lifecycle boundaries retire unused challenges and clear reset/invite/email-verification secrets. Issuers and consumers refresh and lock the user first; magic-link owner discovery is followed by locked challenge revalidation. |
| HTTP refresh-replay denial rolled back revocation | Reuse aborts the caller transaction, then independently commits only session revocation and the security epoch before refusing. A failed containment transaction propagates as a failure; it cannot claim successful revocation. |
| Legacy superusers with NULL protection remained mutable in the scope escape hatch | The guard checks current and historical platform classification, including effective legacy privileges. Mutation locks the target before classification. |
| Target type was read before its decision counter | Decision counters precede entity context and all policy reads. |
| Request/ORM policy graphs were retagged with newer counters | Request publication retains earliest observations; missing scope provenance suppresses publication. Authoritative ORM relationship loads refresh existing instances. This covers a late target scope and a reused session after request reset. |
| A retained API-key/owner object bypassed committed revocation | Credential verification explicitly refreshes the row; owner/principal/anchor runtime authority reads refresh too. Warm snapshot hits retain their zero-SQL path. |

Reproductions are retained as executable tests in
[`test_s1_review_security_boundaries.py`](../tests/integration/test_s1_review_security_boundaries.py)
and [`test_s1_review_cache_provenance.py`](../tests/integration/test_s1_review_cache_provenance.py).
The cache races use both memory and real Redis; challenge retirement covers magic
links, email access codes, WhatsApp/SMS OTP, password reset and phone verification.
The refresh tests exercise mounted HTTP middleware and independently prove that
an unrelated uncommitted write rolls back while containment survives.

## Boundary of acceptance

The committed refresh-reuse boundary deliberately aborts the caller unit of work.
Ordinary configured-engine sessions are qualified. Externally held connections,
connection-local schema/search-path overrides and single-connection pools are not
qualified for this independent containment checkout; hosts must provide an owner
transaction boundary and sufficient connection capacity before adopting this path.
The package does not silently fall back to committing unrelated caller work.

The existing recovery obligations remain: external restore admission, fresh
signing/cache generations, reconstruction of later key revocations, and the
partial-writer-partition publication gap without a durable outbox. Production
budgets and consumer/package/train adoption are separate gates. S2/S3 and the
unwired administrative-grant prototype are unchanged.

Final review outcomes, full local and exact installed-artifact receipts are recorded
in the [release receipt](S1_RELEASE_CANDIDATE_A37.md). Hosted jobs build/publish only;
local tests and independent review are the acceptance gates.
