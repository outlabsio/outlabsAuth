# Auth a37 release receipt

**Published:** 2026-10-11. **Version:** `0.1.0a37`.
**PR:** [#33](https://github.com/outlabsio/outlabsAuth/pull/33).
**Accepted merge and tag:** `bf927276428da4126b1c4c62f2a0564c2060062d`, `v0.1.0a37`.
**Publishing-only run:** [38133672796](https://github.com/outlabsio/outlabsAuth/actions/runs/38133672796), completed successfully.
**Public release:** [PyPI a37](https://pypi.org/project/outlabs-auth/0.1.0a37/).

## Exact public artifacts

| Artifact | SHA-256 |
| --- | --- |
| `outlabs_auth-0.1.0a37-py3-none-any.whl` | `4c557989cf318248b593a8edc913e86f3136eaa0df27bb993e84a5a9b26682e0` |
| `outlabs_auth-0.1.0a37.tar.gz` | `1c95c04846fdda6565ce2f9e770108fc38bda625fbbc1a6ca33c1193c5a826aa` |

Both public files were downloaded and hashed after publication. Their bytes match
both the exact workflow outputs and the locally qualified accepted-merge build.
The wheel and sdist each byte-match all 233 packaged library files in the accepted
merge. Historical candidate hashes are not these release hashes.

## Qualification

- Three independent cache, account/session/OAuth and migration/recovery reviewers
  are green after all eight reproduced publication blockers were corrected;
  [findings and boundaries](S1_REVIEW_A37.md) retain the rationale.
- Full local PostgreSQL 16 / required Redis 7: **1540 passed**, no failures/skips,
  516 warnings, 455.12s. Independent Redis gate: **102 passed**, no failures/skips,
  1438 deselected, 371 warnings, 50.38s.
- Fresh installed wheel, Python 3.14: **178 passed**, 207 warnings, 97.42s.
  Fresh installed sdist, Python 3.12: **84 passed**, 58 warnings, 65.82s.
  Tests ran outside the checkout using `python -I`, with imports verified from
  site-packages. Packaged CLI tests also require the exact input artifact/hash.
- Enterprise HTTP: **62/62** plus admin/ABAC smoke. Metadata and packaging/bootstrap:
  **15 passed**; final documentation/metadata check: **12 passed**.
- All ten warm key/token paths: zero SQL and failures, serial and concurrency 10;
  p95 meets the existing local 10ms ceiling. The corrected benchmark resets each
  synthetic request boundary; [numeric evidence](S1_PERFORMANCE_QUALIFICATION.md)
  preserves the rejected harness run and historical comparison.
- Ruff, changed Python formatting and four selected infrastructure type modules
  pass. The wider targeted type surface retains 13 inherited errors, with none new.
  Handbook changes were ported into an isolated docs-site checkout and lint,
  typecheck and static build pass; no site deployment is implied.

The unique pending publishing environment was verified as `pypi`; its tag/run SHA
matched the accepted merge and qualified package hashes. Explicit maintainer
publication delegation authorized its approval. Hosted jobs built/published only;
local tests and independent review supplied acceptance. Owned disposable services
were removed after qualification.

## Consumer admission remains separate

Auth migration head is `20261011_0026`, adding two nullable security-state columns.
Do not infer consumer schema, train compatibility or deployment from publication.
Resolve public manifests/locks, qualify each actual TaskQ pair, inventory validators
and writers, migrate out of process and rerun consumer gates in authorized staging.

Refresh replay deliberately aborts the caller unit of work and independently
commits containment. Configured-engine sessions are qualified; externally held
connections, connection-local search paths and single-connection pools need their
own host qualification. External restore admission, signing/cache generation,
later-revocation reconstruction, partial writer partitions without a durable outbox
and production capacity/RPO/RTO remain host obligations; see [recovery](AUTH_RECOVERY.md).
S2 staff grants, S3 removal history/owned replay and namespace stages are separate;
this release does not adopt proposed DD-062 or activate the unwired prototype.
