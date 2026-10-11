# Auth a37 S1 release candidate

**Date:** 2026-10-11. **Status:** independently reviewed; final local qualification and publication in progress.
**Latest runtime:** `90de105`; test-double corrections `d6cdebf` do not alter runtime.
All three reviewers are green after eight additional reproduced gaps were closed;
see [independent publication review](S1_REVIEW_A37.md). Final accepted-merge artifacts
and public hashes will be recorded below after qualification/publication. Historical
`f00eb25` inputs/results remain below and do not qualify the corrected runtime.
**Version:** `0.1.0a37`. **Auth head:** `20261011_0026`.

This is one release for all eight S1 baseline corrections, bounded migration/index
safety and Redis recovery fencing. The [implementation receipt](TENANT_AUTH_SECURITY_PATCH.md),
[recovery contract](AUTH_RECOVERY.md) and [performance qualification](S1_PERFORMANCE_QUALIFICATION.md)
retain the rationale and limits. The unwired staff-grant prototype remains unchanged;
S2 grants, S3 history/replay and identity namespaces are separate work.

## Final independent review and local source acceptance

Runtime `90de105`, test-only corrections `d6cdebf`, and fresh-request benchmark
harness `dff04f6` are accepted. Cache, account/session/OAuth and migration/recovery
reviewers are independently green. Their eight initial release blockers and the
explicit unqualified host modes are retained in [S1_REVIEW_A37.md](S1_REVIEW_A37.md).
No runtime changes followed those reviews.

| Gate | Final result |
| --- | --- |
| Full local suite, owned PostgreSQL 16 and required Redis 7 | 1540 passed, 516 warnings, no failures/skips, 455.12s |
| Independent required-Redis suite | 102 passed, 1438 deselected, 371 warnings, 50.38s |
| Enterprise HTTP | 62/62 assertions plus admin/ABAC smoke |
| Metadata and packaging/bootstrap | Metadata check and 15 cases pass |
| Warm keys/tokens, 100 samples after 20 warmups, concurrency 1 and 10 | All ten scenarios zero SQL/zero failures; p95 below 10ms local ceiling |
| Ruff and changed Python formatting | Pass |
| Selected new infrastructure types | Four core modules pass; wider targeted surface retains 13 inherited errors and no new errors |

The full suite ran from clean `d6cdebf`; later edits affect the benchmark and
handbook/maintainer receipts, without changing library runtime or collected tests.
Installed wheel/sdist tests must still qualify the exact accepted-merge artifacts;
the protected publisher must qualify its exact outputs or prove identical hashes.
Public release/train/consumer adoption are independently recorded gates.

## Historical pre-review candidate inputs

`uv build --no-sources` built the sdist and then its wheel from clean `f00eb25`.
Every one of the wheel's 233 packaged library files byte-matches that source.
Only `_version.py` changed under `outlabs_auth/` since runtime `eaa5ff3`; earlier
numeric latency measurements remain applicable observations, not production SLOs.

| Artifact | SHA-256 |
| --- | --- |
| `outlabs_auth-0.1.0a37-py3-none-any.whl` | `65723d935465084d485f2801f394b58bf575d035523f5beaca80da298040386b` |
| `outlabs_auth-0.1.0a37.tar.gz` | `e428359b86b4dc449f8a8111da8044c33c7eeefb77e111a54915d86dc5cba71f` |

These identify this local build. They are not public-index hashes or downstream
lock receipts. The earlier a36-labelled candidate artifacts remain historical
qualification evidence and must never replace published a36.

## Historical pre-review local acceptance

| Gate | Result |
| --- | --- |
| Complete source suite, real PostgreSQL 16 and required Redis 7 | 1511 passed, 485 existing warnings, no failures/skips, 621.87s |
| Separate real-Redis contract suite | 93 passed, 1418 deselected, 344 existing warnings, 40.46s |
| Fresh installed wheel, Python 3.14.0 | 149 security/migration/cache cases passed, 176 warnings, 119.23s |
| Fresh installed sdist, Python 3.12.8 | 55 security/migration/recovery cases passed, 35 warnings, 60.67s |
| Owned Enterprise HTTP example | 62/62 assertions plus admin/ABAC smoke |
| Metadata and packaging | Release helper check and 12 packaging/document tests passed |
| Repository Ruff / changed version-file formatting | Passed |
| Release-tool baseline and candidate train preflight | 39 cases each passed; TaskQ a41 unchanged |

Installed tests run outside the source checkout with `python -I`; imports resolve
from `site-packages`. Packaged-CLI tests require the supplied immutable artifact
and matching SHA-256 before installing it into another fresh environment. The
149-case wheel set combines the 55 migration/recovery/lifecycle cases and 94
transaction, time, snapshot, warm-query and deleted-identifier regressions listed
in [the original artifact receipt](S1_ARTIFACT_QUALIFICATION.md).

The train preflight uses current release-tool source `abc3023`, plus a correction
to its historical-head assertion: the parser is checked against Alembic's installed
history instead of hard-coding head `20260802_0025`. A scratch-only train overlay
expects Auth a37/head 0026 with accepted TaskQ a41. Its canonical manifest, lock and
certified train still describe published a36. This proves candidate composition;
it does not publish or certify a new train. Consumer identities, source inventory
and host acceptance receipts stay in their private repositories.

## Reproduction

Use owned disposable loopback databases and distinct Redis databases. Never use
consumer env files or shared cache instances. The source gates are:

```bash
uv run python scripts/release_version.py check
uv run --extra all python -m pytest -q
uv run --extra all python -m pytest -m redis -q
uv run --extra all python scripts/run_enterprise_example_smoke.py
```

Set `TEST_DATABASE_URL`, `TEST_REDIS_URL`, `TEST_REDIS_REQUIRED=1`; use a separate
owned `DATABASE_URL`, `REDIS_URL`, signing fixture and free port for HTTP acceptance.
For installed gates, copy only tests/config outside the checkout, install the
hashed wheel or sdist with its extras into a fresh environment, and provide
`OUTLABS_AUTH_TEST_ARTIFACT` and `OUTLABS_AUTH_TEST_ARTIFACT_SHA256` as documented
in the original artifact receipt. Do not add the checkout to `PYTHONPATH`.

## Remaining release and admission gates

1. Independent cache, account/session/OAuth and migration/recovery reviews are
   green. Publication is explicitly authorized separately from consumer deployment.
   Final full local and exact accepted-merge artifact qualification remain required.
2. After authorized merge, verify the accepted source/metadata bytes, build and
   qualify the exact publication artifacts at that merge commit, tag that commit,
   and approve the protected `pypi` publishing environment only under the explicit
   publication delegation, after verifying its unique pending deployment and run SHA.
   Record the public wheel/sdist hashes; do not infer them from these local hashes.
3. Resolve a published release train from the public index and qualify each actual
   consumer's unchanged or independently approved TaskQ version. A candidate
   compatibility pass does not make a mixed pair match an older certified train.
4. Regenerate consumer manifests/locks from the public index, pass the private pin
   audit and release-artifact checks, migrate Auth out of process, and rerun the
   full consumer and positive/negative auth gates in authorized staging before
   production promotion. Inventory every validator and authority writer; drain
   and replace old validators before relying on epoch/cache barriers. Nullable
   schema compatibility alone does not qualify a mixed old/new security rollout.
5. Approve and enforce external restore admission, signing/cache generations,
   later-revocation reconstruction and production budgets per host. The local
   backup-epoch test is not a full production restore/RPO/RTO or durable outbox.

Hosted CI is not a test gate. The publishing-only protected environment is the
manual publication step described in [the maintainer release guide](PRIVATE_RELEASE.md).
