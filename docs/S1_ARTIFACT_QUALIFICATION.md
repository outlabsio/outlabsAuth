# S1 installed artifact qualification

**Date:** 2026-10-11. **Qualified package source:** `eaa5ff3` on
`codex/auth-security-20261010`. These are **unreleased local candidate artifacts**.
Their embedded `0.1.0a36` identifier is the unchanged historical baseline, not the
published a36 package. Do not publish these files as a36 or use them as consumer
upgrade pins. A new release version requires new immutable artifacts and receipts.

## Immutable inputs

`uv build --no-sources` built an sdist and then its wheel in a scratch directory
outside the checkout/vault. All 233 packaged library files match the qualified
source bytes, including bundled Alembic configuration, migration safety and revision
`20261011_0026`. The wheel contains no tests, repository docs or environment files.

| Artifact | SHA-256 |
| --- | --- |
| `outlabs_auth-0.1.0a36-py3-none-any.whl` | `f02eea0840072c2b1261cbfde6bc973bfe817e52cd1a89b0ea287e733986482f` |
| `outlabs_auth-0.1.0a36.tar.gz` | `c51a2a5c78fd2d7c5bf98ef9433f7ae49b6c35eb15f221db72304c2d38d046e4` |

Build artifacts and detailed logs remain in the operator's scratch workspace;
this receipt retains the durable technical proof. These hashes identify one build,
not a claim of bit-for-bit reproducibility across clocks or build environments.

## Installed acceptance

Each input was installed with its `all` extras in a fresh virtual environment,
from the local immutable file rather than an editable/source install. Tests were
copied to a directory outside the repository containing no `outlabs_auth` source.
Isolated Python invocation (`-I`) and packaged-CLI subprocess assertions establish
that imports resolve from `site-packages`; the CLI tests hash-check their supplied
artifact before installing it into another clean environment.

| Installation | Python / dependencies | Result |
| --- | --- | --- |
| Wheel | Python 3.14.0, fresh resolved dependencies including SQLAlchemy 2.1.4 and asyncpg 0.32.0 | **55 passed**, 35 existing deprecation warnings, 62.22s |
| Sdist | Python 3.12.8, fresh resolved dependencies | **55 passed**, 35 warnings, 43.97s |
| Installed wheel: earlier cache and identifier regressions | Same wheel environment | **94 passed**, 141 warnings, 39.53s |

The 55-case set covers fresh/idempotent packaged migration, legacy schema adoption,
seed/bootstrap CLI, retained populated users, no table rewrite, bounded lock waits,
transaction rollback, retry, same/separate-process runners, failed concurrent-index
validity, head-index refusal, backup-epoch signing-key fencing, shared/local Redis
recovery, privilege/session lifecycle and OAuth association commit races.

The additional 94 installed-wheel cases cover B1 transaction/savepoint publication,
B2 pre-authority snapshot provenance, B3 scheduled activation/expiry/lease retention,
warm zero-SQL budgets, conditioned decisions and frozen deleted identifiers.

The first wheel run found two test assertions that matched duplicate-error wording.
Fresh SQLAlchemy preserves SQLSTATE `23505` but formats that error differently.
The harness now asserts the integrity-error class and PostgreSQL SQLSTATE; the
15 migration cases and then the complete 55-case set pass. No package runtime was
changed for that correction. Source full-suite proof and the forwarding-mock harness
correction are recorded in the [S1 receipt](TENANT_AUTH_SECURITY_PATCH.md).

## Reproduction and admission boundary

Set disposable loopback `TEST_DATABASE_URL` / `TEST_REDIS_URL`, require Redis, and
install the selected hashed artifact with `uv pip install --python <fresh-python>`.
Copy the acceptance tests outside the checkout and supply:

```text
TEST_REDIS_REQUIRED=1
OUTLABS_AUTH_TEST_ARTIFACT=<absolute wheel or sdist path>
OUTLABS_AUTH_TEST_ARTIFACT_SHA256=<matching hash above>
```

Use the installed Python with `-I -m pytest` on the security/migration/cache test
files listed in this receipt. Do not add the source checkout to `PYTHONPATH`.
The test fixtures flush only the selected disposable Redis DB and drop only their
own schemas. Never substitute a consumer database or shared Redis instance.

Installed acceptance does not approve a release, a consumer pin change or old-binary
rollback. The [release guide](PRIVATE_RELEASE.md) requires local qualification and
the publishing-only approval gate for an authorized new tag; consumer staging and
promotion remain separate. [Recovery](AUTH_RECOVERY.md) requires an external
admission record, fresh signing/cache generations and reconstruction of later
revocations. This candidate does not implement a consumer admission controller,
S2 staff grants, S3 durable outbox/replay or qualified namespaces.
